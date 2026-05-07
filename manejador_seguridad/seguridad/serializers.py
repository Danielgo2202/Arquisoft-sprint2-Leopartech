from rest_framework import serializers
from .models import EventoSeguridad, RegistroAuditoria


class RegistroAuditoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistroAuditoria
        fields = ['id', 'descripcion', 'creado_en']


class EventoSeguridadSerializer(serializers.ModelSerializer):
    registros = RegistroAuditoriaSerializer(many=True, read_only=True)

    class Meta:
        model = EventoSeguridad
        fields = [
            'id', 'tipo', 'endpoint', 'metodo', 'ip_origen',
            'empresa_id_token', 'empresa_id_recurso', 'bloqueado',
            'evidencia', 'creado_en', 'registros',
        ]
