#!/usr/bin/env bash
# Post-deploy smoke test. Usage: scripts/smoke_test.sh https://provisionit-esg.provisionit-esg.workers.dev
#
# Waits for the API container to wake (the first request after a deploy can
# take a few minutes), then checks the things a broken deploy would break:
# the site loads, the API answers, sign-in is enforced, and the scoring
# matrices are the expected versions. Read-only: it creates nothing.
set -euo pipefail
BASE="${1:?usage: smoke_test.sh <site url>}"
BASE="${BASE%/}"

echo "Waiting for $BASE/api/health ..."
for i in $(seq 1 40); do
  if health=$(curl -fsS --max-time 20 "$BASE/api/health" 2>/dev/null); then break; fi
  health=""; sleep 10
done
[ -n "$health" ] || { echo "::error::API did not answer within about 7 minutes"; exit 1; }
echo "$health"

check() { if eval "$2"; then echo "  pass  $1"; else echo "::error::smoke test failed: $1"; exit 1; fi; }
field() { python3 -c "import json,sys; print(json.load(sys.stdin)$1)" <<< "$health"; }

check "API reports ok"                    '[ "$(field "[\"status\"]")" = "ok" ]'
check "sign-in is required"               '[ "$(field "[\"authRequired\"]")" = "True" ]'
check "governance matrix is final"        '[ "$(field "[\"pillars\"][0][\"draft\"]")" = "False" ]'
check "three pillars are served"          '[ "$(field "[\"pillars\"].__len__()")" = "3" ]'
# Download the whole page first: piping curl into grep -q fails under pipefail
# when grep stops reading early (curl: (23) Failure writing output).
check "the website loads"                 'home=$(curl -fsS --max-time 20 "$BASE/") && grep -q "Provision IT" <<< "$home"'
check "protected API refuses no token"    '[ "$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/assessments")" = "401" ]'
check "unknown request token is a 404"    '[ "$(curl -s -o /dev/null -w "%{http_code}" "$BASE/respond/not-a-real-token-123456")" = "404" ]'

echo "Language model configured: $(field "[\"llmConfigured\"]")   Email configured: $(field "[\"smtpConfigured\"]")"
echo "Smoke test passed."
