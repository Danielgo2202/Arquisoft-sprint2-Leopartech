import uuid
import logging
from django.db import transaction
from django.utils import timezone

from .models import EventoEntrante, Analisis, EjecucionAnalisis, Reporte, Alerta

logger = logging.getLogger(__name__)


class IdempotencyService:
    """
    Prevents duplicate event processing using EventoEntrante as a dedup log.
    """

    @staticmethod
    def is_already_processed(evento_id: str) -> bool:
        return EventoEntrante.objects.filter(
            evento_id=evento_id, procesado=True
        ).exists()

    @staticmethod
    def register_received(evento_id: str, tipo_evento: str, payload: dict) -> EventoEntrante:
        evento, created = EventoEntrante.objects.get_or_create(
            evento_id=evento_id,
            defaults={
                'tipo_evento': tipo_evento,
                'payload': payload,
            },
        )
        return evento, created

    @staticmethod
    def mark_processed(evento_id: str):
        EventoEntrante.objects.filter(evento_id=evento_id).update(
            procesado=True,
            procesado_en=timezone.now(),
        )


class AnalisisService:
    """
    Manages Analisis creation and execution lifecycle.
    Executions > 2 s are delegated to Celery (architecture.md §2.2 AMQP).
    """

    @staticmethod
    def crear_analisis_para_proyecto(proyecto_id: str, empresa_id: str) -> Analisis:
        with transaction.atomic():
            analisis = Analisis.objects.create(
                nombre=f"Análisis inicial – proyecto {proyecto_id}",
                proyecto_id=proyecto_id,
                empresa_id=empresa_id,
                tipo=Analisis.Tipo.COSTO,
                estado=Analisis.Estado.PENDIENTE,
            )
        logger.info("Analisis created: %s for proyecto %s", analisis.id, proyecto_id)
        return analisis

    @staticmethod
    def iniciar_ejecucion(analisis: Analisis, celery_task_id: str = None) -> EjecucionAnalisis:
        with transaction.atomic():
            ejecucion = EjecucionAnalisis.objects.create(
                analisis=analisis,
                estado=EjecucionAnalisis.Estado.EN_PROCESO,
                celery_task_id=celery_task_id,
            )
            Analisis.objects.filter(id=analisis.id).update(
                estado=Analisis.Estado.EN_PROCESO
            )
        return ejecucion

    @staticmethod
    def completar_ejecucion(ejecucion: EjecucionAnalisis, resultado: dict, duracion_ms: int):
        now = timezone.now()
        with transaction.atomic():
            EjecucionAnalisis.objects.filter(id=ejecucion.id).update(
                estado=EjecucionAnalisis.Estado.COMPLETADO,
                completado_en=now,
                duracion_ms=duracion_ms,
                resultado=resultado,
            )
            Analisis.objects.filter(id=ejecucion.analisis_id).update(
                estado=Analisis.Estado.COMPLETADO,
            )
        logger.info(
            "EjecucionAnalisis completed: %s in %d ms", ejecucion.id, duracion_ms
        )

    @staticmethod
    def fallar_ejecucion(ejecucion: EjecucionAnalisis, error: str):
        with transaction.atomic():
            EjecucionAnalisis.objects.filter(id=ejecucion.id).update(
                estado=EjecucionAnalisis.Estado.FALLIDO,
                completado_en=timezone.now(),
                error=error,
            )
            Analisis.objects.filter(id=ejecucion.analisis_id).update(
                estado=Analisis.Estado.FALLIDO,
            )
        logger.error("EjecucionAnalisis failed: %s – %s", ejecucion.id, error)


class ReporteService:
    """
    Generates monthly reports.
    Target: ≤ 100 ms using pre-aggregated data (architecture.md §4.2 Latency).
    """

    @staticmethod
    def generar_reporte_mensual(
        proyecto_id: str,
        empresa_id: str,
        periodo_inicio,
        periodo_fin,
        datos_consumo: dict,
    ) -> Reporte:
        nombre = f"Reporte Mensual {periodo_inicio.strftime('%Y-%m')}"
        with transaction.atomic():
            reporte, _ = Reporte.objects.get_or_create(
                proyecto_id=proyecto_id,
                tipo=Reporte.Tipo.MENSUAL,
                periodo_inicio=periodo_inicio,
                periodo_fin=periodo_fin,
                defaults={
                    'nombre': nombre,
                    'empresa_id': empresa_id,
                    'datos': datos_consumo,
                },
            )
        logger.info("Reporte generado: %s para proyecto %s", reporte.id, proyecto_id)
        return reporte

    @staticmethod
    def crear_alerta_presupuesto(
        analisis: Analisis,
        mensaje: str,
        severidad: str = Alerta.Severidad.ALTA,
    ) -> Alerta:
        return Alerta.objects.create(
            analisis=analisis,
            tipo=Alerta.Tipo.PRESUPUESTO,
            mensaje=mensaje,
            severidad=severidad,
        )
