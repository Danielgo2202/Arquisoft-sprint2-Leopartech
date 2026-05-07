import uuid
from django.db import models


class EventoSeguridad(models.Model):
    """
    Records every blocked or suspicious security event (ASR2 + ASR3).
    100% of unauthorized requests must be logged here with evidence.
    """
    class Tipo(models.TextChoices):
        ACCESO_NO_AUTORIZADO = 'acceso_no_autorizado', 'Acceso no autorizado'
        ACCESO_CRUZADO_TENANT = 'acceso_cruzado_tenant', 'Acceso cruzado entre tenants'
        TOKEN_INVALIDO = 'token_invalido', 'Token inválido'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tipo = models.CharField(max_length=30, choices=Tipo.choices, db_index=True)
    endpoint = models.CharField(max_length=500)
    metodo = models.CharField(max_length=10)
    ip_origen = models.GenericIPAddressField(null=True, blank=True)
    empresa_id_token = models.UUIDField(null=True, blank=True, db_index=True)
    empresa_id_recurso = models.UUIDField(null=True, blank=True)
    bloqueado = models.BooleanField(default=True)
    evidencia = models.JSONField(default=dict)
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'eventos_seguridad'
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.tipo} @ {self.endpoint} ({self.creado_en})"


class RegistroAuditoria(models.Model):
    """
    Audit trail linked to a security event.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    evento = models.ForeignKey(
        EventoSeguridad,
        on_delete=models.CASCADE,
        related_name='registros',
    )
    descripcion = models.TextField()
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'registros_auditoria'
        ordering = ['-creado_en']

    def __str__(self):
        return f"Auditoria {self.evento_id}: {self.descripcion[:60]}"
