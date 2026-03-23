#!/bin/bash
set -e

# Only run migrations and collectstatic for the web service (gunicorn)
if echo "$@" | grep -q "gunicorn"; then
    python manage.py makemigrations accounts contacts pipeline campaigns tasks api signatures --noinput
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput
fi

exec "$@"
