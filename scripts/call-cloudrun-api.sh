#!/usr/bin/env bash
set -euo pipefail

SERVICE_URL="${1:-}"
shift || true
IMPERSONATE_SERVICE_ACCOUNT="${IMPERSONATE_SERVICE_ACCOUNT:-}"

if [[ -z "$SERVICE_URL" ]]; then
  echo "Usage: $0 <service-url> [path] [curl args...]"
  exit 1
fi

PATH_SUFFIX="${1:-/api/health}"
if [[ $# -gt 0 ]]; then
  shift
fi

if [[ -n "$IMPERSONATE_SERVICE_ACCOUNT" ]]; then
  TOKEN="$(gcloud auth print-identity-token --audiences="$SERVICE_URL" --impersonate-service-account="$IMPERSONATE_SERVICE_ACCOUNT")"
else
  TOKEN="$(gcloud auth print-identity-token --audiences="$SERVICE_URL")"
fi
curl -sS "${SERVICE_URL}${PATH_SUFFIX}" -H "Authorization: Bearer ${TOKEN}" "$@"
