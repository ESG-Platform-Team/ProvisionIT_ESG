#!/usr/bin/env bash
# One command demo. Starts the offline fixture company, the API and the
# frontend, opens the browser, and stops everything on Ctrl-C.
#
#   ./demo.sh            start
#   ./demo.sh --reset    wipe saved runs, requests and outbox first
#   ./demo.sh --live     also load backend/.env (Gemini key, SMTP settings)
#
# Ports: frontend 8001, API 8080, fixture company 8123.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
RESET=false
LIVE=false
for arg in "$@"; do
  case "$arg" in
    --reset) RESET=true ;;
    --live) LIVE=true ;;
    *) echo "Unknown option $arg"; exit 1 ;;
  esac
done

for port in 8001 8080 8123; do
  if lsof -ti tcp:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $port is in use. Free it with:  kill \$(lsof -ti tcp:$port -sTCP:LISTEN)"
    exit 1
  fi
done

cd "$BACKEND"
if [ ! -d .venv ]; then
  echo "Creating backend/.venv"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q --disable-pip-version-check -r requirements.txt

if $RESET; then
  echo "Resetting saved runs, requests and outbox"
  rm -rf data/platform.db data/mail data/responses
fi

if $LIVE && [ -f .env ]; then
  # Read KEY=VALUE lines literally, so values with spaces or <> are safe.
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    case "$line" in ''|\#*) continue ;; esac
    key="${line%%=*}"
    value="${line#*=}"
    value="${value%\"}"; value="${value#\"}"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] && export "$key=$value"
  done < .env
else
  unset GEMINI_API_KEY SMTP_HOST
fi

PIDS=()
cleanup() {
  echo
  echo "Stopping demo"
  for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT INT TERM

(cd "$BACKEND/fixture-site" && exec python3 -m http.server 8123 >/dev/null 2>&1) &
PIDS+=($!)
uvicorn app.main:app --port 8080 --log-level warning &
PIDS+=($!)
# The frontend is served with caching off, so a browser can never show an
# older copy of the page after an update.
(cd "$FRONTEND" && exec python3 -c '
import http.server, socketserver
class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()
    def log_message(self, *a):
        pass
socketserver.TCPServer.allow_reuse_address = True
http.server.ThreadingHTTPServer(("", 8001), H).serve_forever()
' >/dev/null 2>&1) &
PIDS+=($!)

for _ in $(seq 1 30); do
  curl -s localhost:8080/api/health >/dev/null 2>&1 && break
  sleep 0.5
done

echo
echo "  Frontend        http://localhost:8001"
echo "  API             http://localhost:8080/docs"
echo "  Fixture company http://localhost:8123   (search TST)"
echo "  Email outbox    $BACKEND/data/mail"
if [ -n "${GEMINI_API_KEY:-}" ]; then echo "  Reader          Gemini"; else echo "  Reader          keyword matching (no API key loaded)"; fi
if [ -n "${SMTP_HOST:-}" ]; then echo "  Email           SMTP via $SMTP_HOST"; else echo "  Email           outbox only, nothing is sent"; fi
echo
echo "  Ctrl-C to stop"

if [ "$(uname)" = "Darwin" ]; then open "http://localhost:8001/?v=$(date +%s)" || true; fi
wait
