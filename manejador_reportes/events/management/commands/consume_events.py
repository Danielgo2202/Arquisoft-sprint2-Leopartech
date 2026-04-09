"""
Management command: python manage.py consume_events

Runs a persistent pika consumer that:
  1. Subscribes to RabbitMQ queues (bite.proyectos, bite.analisis, bite.reportes)
  2. For each message, dispatches the appropriate Celery task
  3. Acknowledges the message only after successful Celery enqueue

This implements the Procesador de Eventos component (architecture.md §2.2).
The Celery worker (entrypoint_worker.sh) processes the tasks in the background,
enabling horizontal scaling via the auto-scaling Worker Pool (architecture.md §4.1).
"""
import json
import logging
import signal
import sys
import pika
from django.core.management.base import BaseCommand
from django.conf import settings

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Consumes events from RabbitMQ and dispatches Celery tasks (Procesador de Eventos)'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._connection = None
        self._channel = None
        self._should_stop = False

    def handle(self, *args, **options):
        signal.signal(signal.SIGTERM, self._graceful_shutdown)
        signal.signal(signal.SIGINT, self._graceful_shutdown)

        self.stdout.write(self.style.SUCCESS('Starting event consumer...'))
        self._connect_and_consume()

    def _connect_and_consume(self):
        params = pika.URLParameters(settings.RABBITMQ_URL)
        params.connection_attempts = 5
        params.retry_delay = 3
        params.heartbeat = 60
        params.blocked_connection_timeout = 300

        while not self._should_stop:
            try:
                self._connection = pika.BlockingConnection(params)
                self._channel = self._connection.channel()
                self._setup_topology()
                self.stdout.write(self.style.SUCCESS('Connected to RabbitMQ. Waiting for events...'))
                self._channel.start_consuming()
            except pika.exceptions.AMQPConnectionError as exc:
                logger.warning("AMQP connection lost: %s. Reconnecting in 5 s...", exc)
                import time
                time.sleep(5)
            except KeyboardInterrupt:
                break

        self._safe_close()

    def _setup_topology(self):
        channel = self._channel
        exchange = settings.RABBITMQ_EXCHANGE

        # Declare durable topic exchange
        channel.exchange_declare(exchange=exchange, exchange_type='topic', durable=True)

        # Queue: proyectos (routing key: proyecto.*)
        channel.queue_declare(queue=settings.RABBITMQ_QUEUE_PROYECTOS, durable=True)
        channel.queue_bind(
            exchange=exchange,
            queue=settings.RABBITMQ_QUEUE_PROYECTOS,
            routing_key='proyecto.*',
        )

        # Queue: analisis (routing key: analisis.*)
        channel.queue_declare(queue=settings.RABBITMQ_QUEUE_ANALISIS, durable=True)
        channel.queue_bind(
            exchange=exchange,
            queue=settings.RABBITMQ_QUEUE_ANALISIS,
            routing_key='analisis.*',
        )

        # Queue: reportes (routing key: reporte.*)
        channel.queue_declare(queue=settings.RABBITMQ_QUEUE_REPORTES, durable=True)
        channel.queue_bind(
            exchange=exchange,
            queue=settings.RABBITMQ_QUEUE_REPORTES,
            routing_key='reporte.*',
        )

        # Fair dispatch: don't send more than one message at a time to a worker
        channel.basic_qos(prefetch_count=10)

        # Register consumers
        channel.basic_consume(
            queue=settings.RABBITMQ_QUEUE_PROYECTOS,
            on_message_callback=self._on_message,
        )
        channel.basic_consume(
            queue=settings.RABBITMQ_QUEUE_ANALISIS,
            on_message_callback=self._on_message,
        )
        channel.basic_consume(
            queue=settings.RABBITMQ_QUEUE_REPORTES,
            on_message_callback=self._on_message,
        )

    def _on_message(self, channel, method, properties, body):
        routing_key = method.routing_key
        try:
            event_data = json.loads(body)
            logger.info(
                "Event received",
                extra={'routing_key': routing_key, 'tipo': event_data.get('evento', '')}
            )

            self._dispatch_to_celery(routing_key, event_data)
            channel.basic_ack(delivery_tag=method.delivery_tag)

        except json.JSONDecodeError:
            logger.error("Invalid JSON payload on %s: %s", routing_key, body[:200])
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception:
            logger.exception("Error dispatching event from %s", routing_key)
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def _dispatch_to_celery(self, routing_key: str, event_data: dict):
        """Routes each event to the correct Celery task."""
        from events.tasks import (
            procesar_proyecto_creado,
            generar_reporte,
            procesar_evento_batch,
        )

        if routing_key == 'proyecto.creado':
            procesar_proyecto_creado.apply_async(args=[event_data])
        elif routing_key == 'reporte.solicitado':
            generar_reporte.apply_async(
                args=[event_data.get('data', {})],
                queue='reportes',
            )
        elif routing_key.startswith('analisis.'):
            # Generic analysis events
            procesar_evento_batch.apply_async(args=[event_data])
        else:
            logger.info("No handler registered for routing_key: %s", routing_key)

    def _graceful_shutdown(self, signum, frame):
        self.stdout.write(self.style.WARNING('Shutdown signal received. Stopping consumer...'))
        self._should_stop = True
        if self._channel and self._channel.is_open:
            self._channel.stop_consuming()
        self._safe_close()
        sys.exit(0)

    def _safe_close(self):
        try:
            if self._connection and self._connection.is_open:
                self._connection.close()
        except Exception:
            pass
