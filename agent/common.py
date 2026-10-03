"""Shared config and thin API helpers (Anthropic Messages API + Telegram Bot API), stdlib only."""

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

# agent/ lives directly under the repo root.
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
INBOX = ROOT / "inbox"

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")


def call_claude(messages, system=None, max_tokens=1500):
    body = {"model": MODEL, "max_tokens": max_tokens, "messages": messages}
    if system:
        body["system"] = system
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Anthropic API HTTP {e.code}: {e.read().decode(errors='replace')[:1500]}") from e

    # Don't assume content[0] is text -- other block types can come first.
    for block in result.get("content", []):
        if block.get("type") == "text":
            return block["text"]
    raise RuntimeError(f"No text block in Claude response: {json.dumps(result)[:1500]}")


def telegram(method, payload):
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/{method}",
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=30)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Telegram API HTTP {e.code}: {e.read().decode(errors='replace')[:800]}") from e


def send_message(chat_id, text):
    telegram("sendMessage", {"chat_id": chat_id, "text": text})
