#!/bin/sh
set -e

python manage.py migrate --noinput 2>/dev/null || true

python manage.py run_qcluster &
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:7860 \
    --timeout 300 \
    --workers 1 \
    --preload
