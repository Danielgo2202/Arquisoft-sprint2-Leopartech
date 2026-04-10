#!/bin/bash
set -e

echo "Waiting for RabbitMQ..."
until python -c "
import os, pika
try:
    params = pika.URLParameters(os.environ.get('RABBITMQ_URL','amqp://bite:bite_pass@rabbitmq:5672/bite_vhost'))
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
        dbname=os.environ.get('DATABASE_NAME','reportes_db'),
        user=os.environ.get('DATABASE_USER','admin'),
        password=os.environ.get('DATABASE_PASSWORD','admin123'),
        host=os.environ.get('DATABASE_HOST','localhost'),
        port=os.environ.get('DATABASE_PORT','5432')
    )
except Exception as e:
    print(f'PostgreSQL not ready: {e}')
    exit(1)
"; do
    sleep 2
done

echo "Starting event consumer (manejador_reportes)..."
exec python manage.py consume_events
