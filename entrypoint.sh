#!/usr/bin/env sh
set -eu

mkdir -p /app/instance /app/storage

flask db upgrade

exec gunicorn --bind 0.0.0.0:${APP_PORT:-8080} --workers 2 "run:app"
