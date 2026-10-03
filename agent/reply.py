#!/usr/bin/env python3
"""Reply lane. Runs in GitHub Actions on every push to inbox/. For each unprocessed message:
continue the active quiz, start one if the user texted 'quiz', or explain how to start.
Marks each inbox file processed so nothing is answered twice."""

import re

import conversation
import paper_quiz
from common import INBOX, ROOT, call_claude, send_message

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
QUIZ_TRIGGER = "quiz"


def parse(text):
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm_text, body = m.groups()
    fields = {}
    for line in fm_text.splitlines():
        k, sep, v = line.partition(":")
        if sep:
            fields[k.strip()] = v.strip()
    return fields, body


def write(path, fields, body):
    fm = "\n".join(f"{k}: {v}" for k, v in fields.items())
    path.write_text(f"---\n{fm}\n---\n\n{body.strip()}\n", encoding="utf-8")


def start_quiz(chat_id):
    paper = paper_quiz.next_with_status("sent", last=True)
    if paper is None:
        return "No paper is waiting for a quiz -- either none sent yet, or all already understood."

    try:
        paper_text = paper_quiz.fetch_pdf_text(paper["url"])
    except paper_quiz.NoExtractableTextError:
        paper_quiz.set_status(paper["title"], "no-text-layer")
        return f"'{paper['title']}' has no readable text layer (probably an old scan), so I can't quiz it honestly. Skipped."
    except Exception as e:
        return f"Couldn't load the PDF ({type(e).__name__}). Try again later."

    state = conversation.start(chat_id, "paper-quiz", extra={"paper": paper})
    conversation.append(state, "user", "quiz")
    response = call_claude(state["messages"], system=paper_quiz.system_prompt(paper, paper_text))
    conversation.append(state, "assistant", response)
    conversation.save(chat_id, state)
    return response


def continue_quiz(chat_id, user_text):
    state = conversation.load(chat_id)
    paper = state["paper"]
    conversation.append(state, "user", user_text)

    try:
        paper_text = paper_quiz.fetch_pdf_text(paper["url"])
    except Exception:
        paper_text = "(PDF text unavailable on this turn -- rely on the earlier conversation.)"

    response = call_claude(state["messages"], system=paper_quiz.system_prompt(paper, paper_text))

    if paper_quiz.FINALIZE_MARKER in response:
        reply_text, summary = paper_quiz.split_finalized(response)
        path = paper_quiz.write_learning(paper, summary)
        paper_quiz.set_status(paper["title"], "understood")
        conversation.close(chat_id)
        return f"{reply_text}\n\n(Saved: {path.relative_to(ROOT)})"

    conversation.append(state, "assistant", response)
    conversation.save(chat_id, state)
    return response


def main():
    if not INBOX.exists():
        print("No inbox/ directory -- nothing to do.")
        return

    for path in sorted(INBOX.glob("paperator-*.md")):
        fields, body = parse(path.read_text(encoding="utf-8"))
        if fields.get("status") != "unprocessed":
            continue

        print(f"Processing {path.name}")
        chat_id = fields.get("chat-id")
        user_text = body.strip()

        try:
            if conversation.load(chat_id) is not None:
                answer = continue_quiz(chat_id, user_text)
            elif QUIZ_TRIGGER in user_text.lower():
                answer = start_quiz(chat_id)
            else:
                answer = "Text 'quiz' when you're ready to be asked about today's paper."
            send_message(chat_id, answer)
            fields["status"] = "replied"
        except Exception as e:
            # Never fail silently: record the error on the message and tell the user.
            fields["status"] = "error"
            fields["error"] = f"{type(e).__name__}: {str(e)[:800]}"
            print(f"  -> ERROR: {fields['error']}")
            try:
                send_message(chat_id, "Something went wrong on my side -- check the Actions log.")
            except Exception as e2:
                print(f"  -> also failed to send error notice: {e2}")

        write(path, fields, body)


if __name__ == "__main__":
    main()
