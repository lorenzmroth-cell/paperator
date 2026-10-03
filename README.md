# Paperator

A Telegram bot that sends you one research paper every morning and, when you're ready, **quizzes
you on it** — grounded in the actual PDF text, graded honestly, and saved as a learning note
once you've genuinely understood it.

Downloading a paper isn't reading it, and reading isn't understanding. Paperator closes that gap.

## How it works

```
 Telegram ──webhook──▶ Cloudflare Worker ──GitHub API──▶ inbox/*.md (commit)
                                                              │
                                                     push triggers Actions
                                                              ▼
 Telegram ◀──reply────────────── agent/reply.py ◀── Claude API + PDF text
```

- **No server.** A ~100-line Cloudflare Worker is the only always-on piece. It does no
  reasoning — it just writes each incoming message as a markdown file into `inbox/`.
- **GitHub Actions is the runtime.** The commit to `inbox/` triggers a workflow that runs the
  Python agent, calls Claude, replies on Telegram and commits state back.
- **The repo is the database.** Reading list, conversation state and learning notes are plain
  markdown/JSON in git — inspectable, diffable, editable by hand.
- **Daily cron** sends the next unsent paper from `data/reading-list.md` as a PDF.

### Flow
1. 06:00 — bot sends today's paper (`unsent` → `sent`).
2. You read it whenever. Text `quiz` when ready.
3. The agent downloads the PDF, extracts the text (`pypdf`) and asks 2–3 questions at a time,
   mixing multiple choice and open questions.
4. Wrong or skimmed answers get corrected against the actual text.
5. Once the core claim, method and findings are covered, it writes
   `data/learnings/<paper>.md` and marks the paper `understood`.

Scanned PDFs without a text layer are detected and skipped rather than quizzed on hallucinated
content.

## Setup (≈20 min)

1. **Fork / copy this repo** (can be private).
2. **Create a bot** with [@BotFather](https://t.me/BotFather), note the token. Send it one
   message, then get your chat id from `https://api.telegram.org/bot<TOKEN>/getUpdates`.
3. **Repo secrets** (Settings → Secrets → Actions):
   - `ANTHROPIC_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
4. **Deploy the worker**
   ```bash
   cd worker
   npm install
   # set REPO_OWNER / REPO_NAME in wrangler.toml
   npx wrangler secret put GITHUB_TOKEN             # fine-grained PAT, contents:write on this repo
   npx wrangler secret put TELEGRAM_BOT_TOKEN
   npx wrangler secret put TELEGRAM_WEBHOOK_SECRET  # any random string
   npx wrangler deploy
   ```
5. **Register the webhook**
   ```bash
   WORKER_URL=https://paperator-gateway.<you>.workers.dev WEBHOOK_SECRET=<same string> ./scripts/set_webhook.sh
   ```
6. **Fill `data/reading-list.md`** with papers (free PDF links only) and trigger the
   *daily paper* workflow manually to test.

## Repo layout

```
worker/          Cloudflare Worker: Telegram webhook → inbox/ commit
agent/
  reply.py       routes each inbox message (start / continue quiz)
  paper_quiz.py  reading list, PDF extraction, quiz prompt, learning notes
  conversation.py  multi-turn state persisted as JSON in git
  send_daily_paper.py  morning cron entry point
  common.py      config + Claude / Telegram helpers (stdlib only)
data/            reading list + generated learning notes
.github/workflows/  reply (on push to inbox/) + daily paper (cron)
```

## Customizing
- Model: set `ANTHROPIC_MODEL` in the workflow env.
- Quiz style: edit `system_prompt()` in `agent/paper_quiz.py`.
- Schedule: edit the cron in `.github/workflows/daily-paper.yml` (UTC).

## License
MIT
