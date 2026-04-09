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

echo "Starting Celery worker (manejador_reportes)..."
exec celery -A manejador_reportes.celery worker \
    --loglevel=info \
    --concurrency="${CELERY_WORKER_CONCURRENCY:-8}" \
    --queues=celery,analisis,reportes \
    --hostname=worker@%h
