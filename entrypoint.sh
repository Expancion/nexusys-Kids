#!/usr/bin/env sh
set -eu

mkdir -p /app/instance /app/storage

# Create all tables (idempotent).
# On a fresh DB this builds the full schema; on an existing DB it's a no-op.
python - <<'PY'
from run import app
from app.extensions import db
import sqlalchemy as sa

with app.app_context():
    db.create_all()
    # If alembic has never tracked this DB, stamp it as head so that
    # flask db upgrade doesn't try to re-create already-existing tables.
    if not sa.inspect(db.engine).has_table('alembic_version'):
        from flask_migrate import stamp
        stamp()
PY

# Apply any pending migrations (no-op when already at head).
flask db upgrade

exec gunicorn --bind 0.0.0.0:${APP_PORT:-8080} --workers 2 "run:app"
