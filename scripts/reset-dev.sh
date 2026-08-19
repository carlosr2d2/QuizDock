#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose exec api python scripts/reset_dev_db.py --yes "$@"
