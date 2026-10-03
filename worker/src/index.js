// Paperator gateway -- the "dumb transport" edge worker.
//
// Job: receive a Telegram webhook, write the message raw into inbox/ of this repo via the
// GitHub Contents API, and acknowledge. No reasoning here -- the push to inbox/ triggers a
// GitHub Actions workflow that does the actual work (see agent/reply.py).

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

async function githubPutFile(env, path, contentText, message) {
  const url = `https://api.github.com/repos/${env.REPO_OWNER}/${env.REPO_NAME}/contents/${path}`;
  const res = await fetch(url, {
    method: "PUT",
    headers: {
      "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
      "Accept": "application/vnd.github+json",
      "User-Agent": "paperator-gateway",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message,
      content: btoa(unescape(encodeURIComponent(contentText))),
      branch: env.REPO_BRANCH || "main",
    }),
  });
  if (!res.ok) {
    throw new Error(`GitHub write failed: ${res.status} ${await res.text()}`);
  }
  return res.json();
}

async function handleUpdate(update, env) {
  const chatId = update.message?.chat?.id;
  const text = update.message?.text || update.message?.caption || "(no text)";

  const record = [
    "---",
    `captured: ${new Date().toISOString()}`,
    "source: paperator",
    `chat-id: ${chatId}`,
    "status: unprocessed",
    "---",
    "",
    text,
    "",
  ].join("\n");

  await githubPutFile(env, `inbox/paperator-${todayISO()}-${Date.now()}.md`, record, "Paperator capture");
  return { chatId };
}

async function telegramReply(env, chatId, text) {
  if (!chatId) return;
  await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text }),
  });
}

export default {
  async fetch(request, env, ctx) {
    if (request.method !== "POST") {
      return new Response("ok", { status: 200 });
    }

    // Only accept calls that carry the secret configured in setWebhook.
    if (request.headers.get("X-Telegram-Bot-Api-Secret-Token") !== env.TELEGRAM_WEBHOOK_SECRET) {
      return new Response("unauthorized", { status: 401 });
    }

    let update;
    try {
      update = await request.json();
    } catch (e) {
      return new Response("bad request", { status: 400 });
    }

    try {
      const { chatId } = await handleUpdate(update, env);
      ctx.waitUntil(telegramReply(env, chatId, "✅ received."));
    } catch (err) {
      // Still return 200 so Telegram doesn't retry-storm; the failure shows up in `wrangler tail`.
      console.error("handleUpdate failed:", err);
    }

    return new Response("ok", { status: 200 });
  },
};
