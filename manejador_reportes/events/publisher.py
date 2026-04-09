import json
import logging
import pika
from django.conf import settings

logger = logging.getLogger(__name__)


def publish_event(routing_key: str, body: dict):
    """
    Synchronous RabbitMQ publish. Used by POST /events/batch.
    For non-blocking behaviour, call from a Celery task or background thread.
    """
    try:
        params = pika.URLParameters(settings.RABBITMQ_URL)
        params.connection_attempts = 3
        params.retry_delay = 1
        connection = pika.BlockingConnection(params)
        channel = connection.channel()

        channel.exchange_declare(
            exchange=settings.RABBITMQ_EXCHANGE,
            exchange_type='topic',
            durable=True,
        )

        channel.basic_publish(
            exchange=settings.RABBITMQ_EXCHANGE,
            routing_key=routing_key,
            body=json.dumps(body, default=str),
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type='application/json',
                app_id='manejador_reportes',
            ),
        )
        connection.close()
        logger.info("Published to %s: %s", routing_key, body.get('tipo', ''))
    except Exception:
        logger.exception("Failed to publish event: routing_key=%s", routing_key)
        raise


def routing_key_for_event(tipo: str) -> str:
    """Maps event type to RabbitMQ routing key."""
    mapping = {
        'proyecto_creado': 'proyecto.creado',
        'proyecto_actualizado': 'proyecto.actualizado',
        'analisis_completado': 'analisis.completado',
        'reporte_generado': 'reporte.generado',
        'reporte_solicitado': 'reporte.solicitado',
        'recurso_infrautilizado': 'recurso.infrautilizado',
        'alerta_presupuesto': 'alerta.presupuesto',
    }
    return mapping.get(tipo, f"evento.{tipo}")
