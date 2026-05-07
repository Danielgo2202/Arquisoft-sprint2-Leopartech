#!/bin/bash
set -e

echo "Waiting for PostgreSQL..."
until python -c "
import os, psycopg2
try:
    psycopg2.connect(
        dbname=os.environ.get('DATABASE_NAME','seguridad_db'),
        user=os.environ.get('DATABASE_USER','postgres'),
        password=os.environ.get('DATABASE_PASSWORD','postgres'),
        host=os.environ.get('DATABASE_HOST','localhost'),
        port=os.environ.get('DATABASE_PORT','5432')
    )
    print('PostgreSQL ready')
except Exception as e:
    print(f'PostgreSQL not ready: {e}')
    exit(1)
"; do
    sleep 2
done

echo "Running migrations..."
python manage.py migrate --noinput

echo "Seeding auth users (local JWT mode)..."
python manage.py seed_auth_users || true

echo "Starting gunicorn..."
exec gunicorn manejador_autenticacion.wsgi:application \
    --bind 0.0.0.0:8004 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --threads "${GUNICORN_THREADS:-2}" \
    --timeout "${GUNICORN_TIMEOUT:-30}" \
    --access-logfile - \
    --error-logfile - \
    --log-level info
