#!/bin/sh
# Container entrypoint. Starts the offline fixture company (TST) inside the
# container so the demo company still works in the cloud, then the API.
set -e
python -m http.server 8123 --bind 127.0.0.1 --directory fixture-site >/dev/null 2>&1 &
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}" \
  --proxy-headers --forwarded-allow-ips='*'
