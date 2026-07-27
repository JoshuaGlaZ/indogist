#!/bin/sh
set -e

python -m alembic upgrade head || true

exec uvicorn app.main:app --host 0.0.0.0 --port 7860 --workers 1
