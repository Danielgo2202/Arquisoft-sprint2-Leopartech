from rest_framework import serializers
from .models import (
    EventoEntrante, Analisis, EjecucionAnalisis, Reporte,
    Alerta, OportunidadAhorro, Notificacion,
)


class EventoEntranteSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventoEntrante
        fields = ['id', 'evento_id', 'tipo_evento', 'procesado', 'recibido_en']
        read_only_fields = fields


class SingleEventSerializer(serializers.Serializer):
    """Schema for a single event in the batch."""
    tipo = serializers.CharField(max_length=100)
    version = serializers.CharField(max_length=10, default='1.0')
    source = serializers.CharField(max_length=100, required=False, default='external')
    data = serializers.JSONField()
    evento_id = serializers.CharField(
        max_length=255,
        required=False,
        help_text="Optional idempotency key. Auto-generated if not provided.",
    )


class BatchEventSerializer(serializers.Serializer):
    """
    Schema for POST /events/batch.
    Accepts 1–200 events per request.
    """
    events = serializers.ListField(
        child=SingleEventSerializer(),
        min_length=1,
        max_length=200,
        error_messages={
            'min_length': 'Al menos 1 evento requerido.',
            'max_length': 'Máximo 200 eventos por lote.',
        },
    )


class AnalisisSerializer(serializers.ModelSerializer):
    class Meta:
        model = Analisis
        fields = [
            'id', 'nombre', 'proyecto_id', 'empresa_id',
            'tipo', 'estado', 'creado_en', 'actualizado_en',
        ]
        read_only_fields = ['id', 'creado_en', 'actualizado_en']


class EjecucionAnalisisSerializer(serializers.ModelSerializer):
    class Meta:
        model = EjecucionAnalisis
        fields = [
            'id', 'analisis', 'estado', 'celery_task_id',
            'iniciado_en', 'completado_en', 'duracion_ms',
            'resultado', 'error',
        ]
        read_only_fields = fields


class ReporteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reporte
        fields = [
            'id', 'nombre', 'tipo', 'proyecto_id', 'empresa_id',
            'periodo_inicio', 'periodo_fin', 'datos', 'generado_en',
        ]
        read_only_fields = fields


class AlertaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alerta
        fields = ['id', 'tipo', 'mensaje', 'severidad', 'resuelta', 'creada_en']
        read_only_fields = fields


class OportunidadAhorroSerializer(serializers.ModelSerializer):
    class Meta:
        model = OportunidadAhorro
        fields = [
            'id', 'analisis', 'recurso_cloud_id', 'descripcion',
            'ahorro_estimado', 'moneda', 'estado', 'creada_en',
        ]
        read_only_fields = ['id', 'creada_en']
