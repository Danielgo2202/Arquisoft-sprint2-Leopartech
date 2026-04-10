#!/bin/bash
set -e

echo "Waiting for PostgreSQL..."
until python -c "
import os, psycopg2
try:
    psycopg2.connect(
        dbname=os.environ.get('DATABASE_NAME','reportes_db'),
        user=os.environ.get('DATABASE_USER','admin'),
        password=os.environ.get('DATABASE_PASSWORD','admin123'),
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

echo "Loading seeds..."
if [ -f "/seeds/seed_reports.sql" ]; then
    python manage.py dbshell < /seeds/seed_reports.sql || true
fi

echo "Starting gunicorn..."
exec gunicorn manejador_reportes.wsgi:application \
    --bind 0.0.0.0:8003 \
    --workers "${GUNICORN_WORKERS:-4}" \
    --threads "${GUNICORN_THREADS:-2}" \
    --timeout "${GUNICORN_TIMEOUT:-30}" \
    --access-logfile - \
    --error-logfile - \
    --log-level info
