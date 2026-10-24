#!/usr/bin/env bash
# Fails if a credential has been committed. Runs in CI on every pull request.
#
# Checks the files git tracks (not the working folder), so a local backend/.env
# that is correctly ignored never trips it. Placeholders in .env.example and the
# documentation are allowed; real-looking values are not.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

fail=0
report() { echo "::error file=$1::$2"; fail=1; }

# 1. Files that must never be committed.
while IFS= read -r f; do
  case "$f" in
    *.env|.env|*/.env|*.pem|*.key|*/.jwt_secret|*/data/platform.db) report "$f" "this file type must not be committed" ;;
  esac
done < <(git ls-files)

# 2. Credential patterns inside tracked text files.
patterns=(
  'AIza[0-9A-Za-z_-]{35}'                                  # Google / Gemini API key
  '-----BEGIN [A-Z ]*PRIVATE KEY-----'                     # private keys
  'postgres(ql)?://[^:/ "]+:[^@ "<]{8,}@[^ "]*neon\.tech' # a Neon URL with a real password
  'SMTP_PASSWORD=[^< "$][^ "]{7,}'                         # an SMTP password written into a file
)
for p in "${patterns[@]}"; do
  # Documented placeholders (user:password@, <your-key>, example values) are allowed.
  if hits=$(git grep -nIE -e "$p" -- . ':!scripts/check_secrets.sh' 2>/dev/null \
            | grep -vE ':password@|<[a-z-]+>|example|EXAMPLE'); then
    while IFS= read -r h; do report "${h%%:*}" "possible secret matching /$p/"; done <<< "$hits"
  fi
done

if [ "$fail" -eq 0 ]; then echo "No committed secrets found."; fi
exit "$fail"
