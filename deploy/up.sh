#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -f .env.staging ]]; then
  echo "Missing .env.staging — copy deploy/staging.env.example and fill secrets." >&2
  exit 1
fi
docker compose -f docker-compose.staging.yml --env-file .env.staging up -d --build
