"""The paper-quiz logic. Picks the next unsent paper from data/reading-list.md, fetches the
actual PDF text so questions are grounded in the real content (not just the title), and once
the reader has demonstrated understanding, writes a short learning note to data/learnings/.

The idea: downloading a paper isn't learning it. The quiz is what turns it into a validated
learning.
"""

import io
import re
import urllib.request
from datetime import date

from common import DATA_DIR

FINALIZE_MARKER = "[PAPER_UNDERSTOOD]"
READING_LIST = DATA_DIR / "reading-list.md"
LEARNINGS_DIR = DATA_DIR / "learnings"

# Full papers can be huge; this covers abstract, intro and most of a typical body while
# keeping cost and context sane. Appendices of long papers may get cut -- known limitation.
MAX_PAPER_CHARS = 20000

# Columns: Title | Authors | Year | Category | URL | Status | Date sent
COL_STATUS, COL_DATE = 5, 6


class NoExtractableTextError(Exception):
    """The PDF loaded fine but has essentially no machine-readable text (e.g. an old scan)."""


def parse_rows():
    if not READING_LIST.exists():
        return []
    rows = []
    for line in READING_LIST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|") or set(line.replace("|", "").strip()) <= {"-", " "}:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 7 or cells[0].lower() == "title":
            continue
        rows.append(cells)
    return rows


def _as_paper(row):
    return {"title": row[0], "authors": row[1], "year": row[2], "category": row[3], "url": row[4]}


def next_with_status(status, last=False):
    matches = [r for r in parse_rows() if r[COL_STATUS].lower() == status]
    if not matches:
        return None
    return _as_paper(matches[-1] if last else matches[0])


def set_status(title, new_status, new_date=None):
    lines = []
    for line in READING_LIST.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.strip().startswith("|") and len(cells) >= 7 and cells[0] == title:
            cells[COL_STATUS] = new_status
            cells[COL_DATE] = new_date or cells[COL_DATE]
            line = "| " + " | ".join(cells) + " |"
        lines.append(line)
    READING_LIST.write_text("\n".join(lines) + "\n", encoding="utf-8")


def fetch_pdf_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (paperator-bot)"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        pdf_bytes = resp.read()

    from pypdf import PdfReader  # installed as a workflow step

    reader = PdfReader(io.BytesIO(pdf_bytes))
    full_text = "\n".join(page.extract_text() or "" for page in reader.pages)

    # Quizzing on a scan with no text layer would mean grading against content nobody read.
    # An honest failure beats a hallucinated quiz.
    if len(full_text.strip()) < 500:
        raise NoExtractableTextError(f"only {len(full_text.strip())} chars extracted -- likely a scan without OCR")

    return full_text[:MAX_PAPER_CHARS]


def system_prompt(paper, paper_text):
    return (
        "You are a personal learning coach quizzing the user over Telegram on a paper they "
        f"were sent to read today: \"{paper['title']}\" ({paper['authors']}, {paper['year']}).\n\n"
        "Extracted paper text (may be truncated):\n---\n"
        f"{paper_text}\n---\n\n"
        "Your job:\n"
        "1. Test genuine understanding, not recall of the title. Mix multiple-choice and open "
        "questions. Ask 2-3 at a time -- this is a phone chat.\n"
        "2. Grade answers against the actual paper text above. If an answer is wrong or shows "
        "skimming, say so directly and explain the real answer.\n"
        "3. Cover the paper's core claim, method and finding before finishing.\n"
        "4. Once the user shows a reasonable grasp of the core ideas, close with a short honest "
        f"assessment, then on its own line write exactly: {FINALIZE_MARKER}\n"
        "   followed by:\n"
        "   understood: <yes/partially>\n"
        "   core_claim: <one sentence>\n"
        "   got_right: <short phrase>\n"
        "   missed: <short phrase, or 'nothing significant'>\n"
        "   Never write the marker before the user has engaged with the real content."
    )


def split_finalized(response_text):
    before, _, after = response_text.partition(FINALIZE_MARKER)
    return before.strip(), after.strip()


def write_learning(paper, summary_text):
    LEARNINGS_DIR.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", paper["title"].lower()).strip("-")[:80]
    path = LEARNINGS_DIR / f"{slug}.md"
    path.write_text(
        "---\n"
        f"title: {paper['title']}\n"
        f"authors: {paper['authors']}\n"
        f"year: {paper['year']}\n"
        f"category: {paper['category']}\n"
        f"url: {paper['url']}\n"
        f"quizzed: {date.today().isoformat()}\n"
        "---\n\n"
        f"# {paper['title']}\n\n{summary_text}\n",
        encoding="utf-8",
    )
    return path
