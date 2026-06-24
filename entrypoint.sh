#!/usr/bin/env sh
set -eu

mkdir -p /app/instance /app/storage

# On a fresh DB (no alembic_version): create full schema + stamp at head
# so that flask db upgrade is a no-op (all tables already exist).
#
# On an existing DB: skip create_all and let flask db upgrade apply pending
# migrations normally. Calling create_all on an existing DB would pre-create
# tables that the pending migration also tries to create → DuplicateTable error.
python - <<'PY'
from run import app
from app.extensions import db
import sqlalchemy as sa

with app.app_context():
    if not sa.inspect(db.engine).has_table('alembic_version'):
        db.create_all()
        from flask_migrate import stamp
        stamp()
PY

flask db upgrade

# Compile translation catalogs (.po → .mo)
pybabel compile -d app/translations || true

exec gunicorn --bind 0.0.0.0:${APP_PORT:-8080} --workers 2 "run:app"
