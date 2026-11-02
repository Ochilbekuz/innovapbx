#!/bin/sh
# Innova PBX — API konteyneri entrypoint: migratsiya -> DB sozlamalari (GUC) -> ilova.
set -eu

echo "[entrypoint] alembic upgrade head"
alembic upgrade head

echo "[entrypoint] bootstrap_db_settings (innova.key GUC)"
python -m app.db.bootstrap

echo "[entrypoint] start: $*"
exec "$@"
