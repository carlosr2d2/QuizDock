Set-Location $PSScriptRoot\..
docker compose exec api python scripts/reset_dev_db.py --yes @args
