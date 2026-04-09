#!/bin/bash
set -e

echo "Waiting for RabbitMQ..."
until python -c "
import os, pika
try:
    params = pika.URLParameters(os.environ.get('RABBITMQ_URL','amqp://guest:guest@rabbitmq:5672/'))
    conn = pika.BlockingConnection(params)
    conn.close()
    print('RabbitMQ ready')
except Exception as e:
    print(f'RabbitMQ not ready: {e}')
    exit(1)
"; do
    sleep 3
done

echo "Waiting for PostgreSQL..."
until python -c "
import os, psycopg2
try:
    psycopg2.connect(
        dbname=os.environ.get('DB_NAME','reportes_db'),
        user=os.environ.get('DB_USER','postgres'),
        password=os.environ.get('DB_PASSWORD',''),
        host=os.environ.get('DB_HOST','localhost'),
        port=os.environ.get('DB_PORT','5432')
    )
except Exception as e:
    print(f'PostgreSQL not ready: {e}')
    exit(1)
"; do
    sleep 2
done

echo "Starting event consumer (manejador_reportes)..."
exec python manage.py consume_events
