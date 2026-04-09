import json
import logging
import threading
import pika
from django.conf import settings

logger = logging.getLogger(__name__)


def _publish_to_rabbitmq(exchange: str, routing_key: str, body: dict):
    """
    Internal: publishes a single event to RabbitMQ.
    Runs in a background daemon thread (non-blocking for the HTTP request).
    Uses persistent delivery (delivery_mode=2) for durability.
    """
    try:
        params = pika.URLParameters(settings.RABBITMQ_URL)
        params.connection_attempts = 3
        params.retry_delay = 1
        connection = pika.BlockingConnection(params)
        channel = connection.channel()

        # Topic exchange so Event Service can route by routing key pattern
        channel.exchange_declare(
            exchange=exchange,
            exchange_type='topic',
            durable=True,
        )

        channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=json.dumps(body, default=str),
            properties=pika.BasicProperties(
                delivery_mode=2,          # persistent message
                content_type='application/json',
                app_id='manejador_usuarios',
            ),
        )
        connection.close()
        logger.info(
            "Event published",
            extra={'exchange': exchange, 'routing_key': routing_key}
        )
    except Exception:
        logger.exception(
            "Failed to publish event to RabbitMQ",
            extra={'exchange': exchange, 'routing_key': routing_key}
        )


class ProyectoEventPublisher:
    """
    Publishes domain events for the Proyecto bounded context.
    All publishes are fire-and-forget (background thread) to keep POST /projects
    returning HTTP 201 in ≤100 ms (architecture.md §4.2 latency requirement).
    """

    @staticmethod
    def publish_proyecto_creado(proyecto) -> None:
        """
        Event: proyecto.creado
        Published after a Proyecto is persisted in PostgreSQL.
        Consumed by Procesador de Eventos (manejador_reportes) to trigger analysis.
        """
        event_payload = {
            'evento': 'proyecto_creado',
            'version': '1.0',
            'source': 'manejador_usuarios',
            'data': {
                'proyecto_id': str(proyecto.id),
                'nombre': proyecto.nombre,
                'empresa_id': str(proyecto.empresa_id),
                'estado': proyecto.estado,
                'cuentas_cloud': [
                    str(c.cuenta_cloud_id)
                    for c in proyecto.cuentas_cloud.all()
                ],
                'creado_en': proyecto.creado_en.isoformat(),
            },
        }

        thread = threading.Thread(
            target=_publish_to_rabbitmq,
            args=(
                settings.RABBITMQ_EXCHANGE,
                settings.RABBITMQ_ROUTING_KEY_PROJECT,
                event_payload,
            ),
            daemon=True,
            name=f"publisher-proyecto-{proyecto.id}",
        )
        thread.start()
        logger.info("Background publish started for proyecto %s", proyecto.id)
