import uuid
import time
import logging
from datetime import date
from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from .services import IdempotencyService, AnalisisService, ReporteService
from .models import Analisis, EjecucionAnalisis, OportunidadAhorro, Notificacion

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name='events.tasks.procesar_proyecto_creado',
    max_retries=3,
    default_retry_delay=10,
    acks_late=True,
)
def procesar_proyecto_creado(self, event_data: dict):
    """
    Celery task: handles proyecto_creado event from Project Service.
    Creates an Analisis and schedules cost analysis execution.
    Called by pika consumer (management/commands/consume_events.py).
    """
    evento_id = event_data.get('data', {}).get('proyecto_id', str(uuid.uuid4()))
    tipo_evento = 'proyecto_creado'

    try:
        # Idempotency check
        if IdempotencyService.is_already_processed(evento_id):
            logger.info("Duplicate event skipped: %s", evento_id)
            return {'status': 'skipped', 'reason': 'already_processed'}

        evento, created = IdempotencyService.register_received(
            evento_id, tipo_evento, event_data
        )

        data = event_data.get('data', {})
        proyecto_id = data.get('proyecto_id')
        empresa_id = data.get('empresa_id')

        if not proyecto_id or not empresa_id:
            logger.error("Missing proyecto_id or empresa_id in event: %s", event_data)
            return {'status': 'error', 'reason': 'missing_fields'}

        # Create analysis for the new project
        analisis = AnalisisService.crear_analisis_para_proyecto(proyecto_id, empresa_id)

        # Schedule actual execution (async, Celery)
        task = ejecutar_analisis.apply_async(
            args=[str(analisis.id)],
            queue='analisis',
        )
        ejecucion = AnalisisService.iniciar_ejecucion(analisis, celery_task_id=task.id)

        IdempotencyService.mark_processed(evento_id)

        logger.info(
            "proyecto_creado processed: analisis=%s task=%s", analisis.id, task.id
        )
        return {'status': 'ok', 'analisis_id': str(analisis.id)}

    except Exception as exc:
        logger.exception("Error processing proyecto_creado event: %s", evento_id)
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name='events.tasks.ejecutar_analisis',
    max_retries=2,
    default_retry_delay=30,
    soft_time_limit=120,
    time_limit=180,
    acks_late=True,
)
def ejecutar_analisis(self, analisis_id: str):
    """
    Celery task: runs the cost analysis for a project.
    If execution takes > 2 s, user is notified by email upon completion
    (architecture.md §5.4 Notificacion + §2.2 background threshold).
    """
    start_time = time.monotonic()

    try:
        analisis = Analisis.objects.select_related().get(id=analisis_id)
        ejecucion = (
            EjecucionAnalisis.objects
            .filter(analisis=analisis, estado=EjecucionAnalisis.Estado.EN_PROCESO)
            .order_by('-iniciado_en')
            .first()
        )

        # Simulate analysis computation
        # In production, this calls Resource Service for consumption data
        resultado = _simulate_cost_analysis(analisis)

        duracion_ms = int((time.monotonic() - start_time) * 1000)

        if ejecucion:
            AnalisisService.completar_ejecucion(ejecucion, resultado, duracion_ms)

        # Generate monthly report
        hoy = date.today()
        from datetime import date as d
        inicio = d(hoy.year, hoy.month, 1)
        fin = hoy
        reporte = ReporteService.generar_reporte_mensual(
            str(analisis.proyecto_id),
            str(analisis.empresa_id),
            inicio,
            fin,
            resultado,
        )

        # If analysis took > 2000 ms, queue email notification
        if duracion_ms > 2000:
            enviar_notificacion.apply_async(
                args=[{
                    'usuario_id': str(analisis.empresa_id),
                    'email_destino': 'admin@bite.co',
                    'asunto': f'Análisis completado – {analisis.nombre}',
                    'cuerpo': (
                        f'El análisis "{analisis.nombre}" para el proyecto '
                        f'{analisis.proyecto_id} ha sido completado en '
                        f'{duracion_ms} ms. Reporte ID: {reporte.id}'
                    ),
                    'ejecucion_id': str(ejecucion.id) if ejecucion else None,
                }],
                queue='celery',
            )
            logger.info(
                "Long-running analysis (%d ms) – email notification queued", duracion_ms
            )

        logger.info("Analysis %s completed in %d ms", analisis_id, duracion_ms)
        return {'status': 'ok', 'analisis_id': analisis_id, 'duracion_ms': duracion_ms}

    except Analisis.DoesNotExist:
        logger.error("Analisis not found: %s", analisis_id)
        return {'status': 'error', 'reason': 'analisis_not_found'}
    except Exception as exc:
        logger.exception("Error executing analisis %s", analisis_id)
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name='events.tasks.generar_reporte',
    max_retries=2,
    default_retry_delay=15,
    acks_late=True,
)
def generar_reporte(self, reporte_params: dict):
    """
    Celery task: explicitly generates a report for given params.
    Called from POST /events/batch with tipo=reporte_solicitado.
    """
    try:
        proyecto_id = reporte_params['proyecto_id']
        empresa_id = reporte_params['empresa_id']
        periodo_inicio = reporte_params.get('periodo_inicio', str(date.today().replace(day=1)))
        periodo_fin = reporte_params.get('periodo_fin', str(date.today()))

        from datetime import date as d
        inicio = d.fromisoformat(periodo_inicio)
        fin = d.fromisoformat(periodo_fin)

        datos = {'generado_por_task': True, 'params': reporte_params}
        reporte = ReporteService.generar_reporte_mensual(
            proyecto_id, empresa_id, inicio, fin, datos
        )
        return {'status': 'ok', 'reporte_id': str(reporte.id)}
    except Exception as exc:
        logger.exception("Error generating reporte")
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name='events.tasks.enviar_notificacion',
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def enviar_notificacion(self, notif_data: dict):
    """
    Celery task: sends email notification.
    Used for async analysis completion (architecture.md §2.2 API Email Provider).
    """
    try:
        usuario_id = notif_data['usuario_id']
        email_destino = notif_data['email_destino']
        asunto = notif_data['asunto']
        cuerpo = notif_data['cuerpo']

        notificacion = Notificacion.objects.create(
            usuario_id=usuario_id,
            email_destino=email_destino,
            tipo=Notificacion.Tipo.EMAIL,
            asunto=asunto,
            cuerpo=cuerpo,
        )

        send_mail(
            subject=asunto,
            message=cuerpo,
            from_email=settings.EMAIL_FROM,
            recipient_list=[email_destino],
            fail_silently=False,
        )

        Notificacion.objects.filter(id=notificacion.id).update(
            enviada=True,
            enviada_en=timezone.now(),
        )
        logger.info("Notification sent to %s: %s", email_destino, asunto)
        return {'status': 'ok', 'notificacion_id': str(notificacion.id)}

    except Exception as exc:
        logger.exception("Error sending notification")
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name='events.tasks.procesar_evento_batch',
    max_retries=2,
    default_retry_delay=5,
    acks_late=True,
)
def procesar_evento_batch(self, event_data: dict):
    """
    Celery task: routes a single event from a batch submission.
    Dispatched by POST /events/batch → EventoBatchView.
    """
    tipo = event_data.get('tipo', '')
    try:
        if tipo == 'proyecto_creado':
            return procesar_proyecto_creado.apply_async(args=[event_data]).id
        elif tipo == 'reporte_solicitado':
            return generar_reporte.apply_async(
                args=[event_data.get('data', {})],
                queue='reportes',
            ).id
        else:
            logger.info("Unknown event type in batch: %s", tipo)
            return {'status': 'skipped', 'tipo': tipo}
    except Exception as exc:
        logger.exception("Error routing batch event: %s", tipo)
        raise self.retry(exc=exc)


# ── Internal helpers ─────────────────────────────────────────────────────────

def _simulate_cost_analysis(analisis: Analisis) -> dict:
    """
    Placeholder for actual cost analysis computation.
    In production, this calls Resource Service API to aggregate MetricaConsumo.
    """
    return {
        'proyecto_id': str(analisis.proyecto_id),
        'empresa_id': str(analisis.empresa_id),
        'tipo': analisis.tipo,
        'costo_total_usd': 0.0,
        'recursos_analizados': 0,
        'recursos_infrautilizados': [],
        'oportunidades_ahorro': [],
        'timestamp': timezone.now().isoformat(),
    }
