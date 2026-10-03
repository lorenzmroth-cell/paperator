#!/usr/bin/env python3
"""Scheduled entry point (morning cron): sends the next unsent paper as a PDF via Telegram and
marks it 'sent'. The user reads during the day and texts 'quiz' when ready."""

import os
from datetime import date

import paper_quiz
from common import send_message, telegram

CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


def main():
    paper = paper_quiz.next_with_status("unsent")
    if paper is None:
        print("No unsent paper left in the reading list.")
        return

    caption = (
        f"{paper['title']} ({paper['authors']}, {paper['year']}) — {paper['category']}\n\n"
        "Read it whenever you find time today. Text 'quiz' when you're ready."
    )
    try:
        # Telegram fetches the URL server-side, so the PDF never passes through this runner.
        telegram("sendDocument", {"chat_id": CHAT_ID, "document": paper["url"], "caption": caption})
    except Exception as e:
        # Some hosts block server-to-server fetches -- fall back to sending the link.
        print(f"sendDocument failed ({e}), sending link instead")
        send_message(CHAT_ID, f"{caption}\n\n{paper['url']}")

    paper_quiz.set_status(paper["title"], "sent", date.today().isoformat())
    print(f"Sent: {paper['title']}")


if __name__ == "__main__":
    main()
