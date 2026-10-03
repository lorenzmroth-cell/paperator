#!/bin/bash
# One-time helper: registers your deployed Worker URL as the Telegram webhook.
# Usage: WORKER_URL=https://paperator-gateway.<you>.workers.dev WEBHOOK_SECRET=... ./scripts/set_webhook.sh
set -e
: "${WORKER_URL:?set WORKER_URL}"
: "${WEBHOOK_SECRET:?set WEBHOOK_SECRET}"

echo -n "Bot token (hidden input): "
read -s TOKEN
echo
TOKEN=$(echo "$TOKEN" | tr -d '[:space:]')

curl -s "https://api.telegram.org/bot${TOKEN}/getMe"; echo
curl -s "https://api.telegram.org/bot${TOKEN}/setWebhook?url=${WORKER_URL}&secret_token=${WEBHOOK_SECRET}"; echo
