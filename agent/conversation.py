"""Multi-turn conversation state, persisted in git. GitHub Actions runners are ephemeral, so
the repo itself is the only durable store between workflow runs. One JSON file per chat_id.
"""

import json
from datetime import datetime, timezone

from common import ROOT

STATE_DIR = ROOT / "state" / "conversations"


def _path(chat_id):
    return STATE_DIR / f"{chat_id}.json"


def load(chat_id):
    p = _path(chat_id)
    return json.loads(p.read_text()) if p.exists() else None


def start(chat_id, mode, extra=None):
    state = {"mode": mode, "started": datetime.now(timezone.utc).isoformat(), "messages": []}
    state.update(extra or {})
    save(chat_id, state)
    return state


def append(state, role, content):
    state["messages"].append({"role": role, "content": content})


def save(chat_id, state):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    _path(chat_id).write_text(json.dumps(state, indent=2, ensure_ascii=False))


def close(chat_id):
    _path(chat_id).unlink(missing_ok=True)
