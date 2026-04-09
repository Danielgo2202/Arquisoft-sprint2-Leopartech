import uuid
from django.db import models


class EventoEntrante(models.Model):
    """
    Tracks every incoming event for idempotency.
    Prevents duplicate processing when events are redelivered.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    evento_id = models.CharField(max_length=255, unique=True, db_index=True)
    tipo_evento = models.CharField(max_length=100, db_index=True)
    payload = models.JSONField()
    procesado = models.BooleanField(default=False, db_index=True)
    procesado_en = models.DateTimeField(null=True, blank=True)
    recibido_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'eventos_entrantes'
        indexes = [
            models.Index(fields=['evento_id'], name='evento_id_idx'),
            models.Index(fields=['tipo_evento', 'procesado'], name='evento_tipo_procesado_idx'),
        ]

    def __str__(self):
        return f"{self.tipo_evento} – {self.evento_id}"


class Analisis(models.Model):
    """
    A cost or capacity analysis scoped to a project.
    Bounded context: Análisis y Reportes (architecture.md §5.4)
    """
    class Tipo(models.TextChoices):
        COSTO = 'COSTO', 'Análisis de Costos'
        CAPACIDAD = 'CAPACIDAD', 'Análisis de Capacidad'
        OPTIMIZACION = 'OPTIMIZACION', 'Optimización de Recursos'
        DESPERDICIO = 'DESPERDICIO', 'Identificación de Desperdicio'

    class Estado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        EN_PROCESO = 'EN_PROCESO', 'En Proceso'
        COMPLETADO = 'COMPLETADO', 'Completado'
        FALLIDO = 'FALLIDO', 'Fallido'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombre = models.CharField(max_length=255)
    proyecto_id = models.UUIDField(db_index=True)
    empresa_id = models.UUIDField(db_index=True)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, db_index=True)
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.PENDIENTE, db_index=True
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'analisis'
        indexes = [
            models.Index(fields=['proyecto_id', 'estado'], name='analisis_proyecto_estado_idx'),
            models.Index(fields=['empresa_id', 'tipo'], name='analisis_empresa_tipo_idx'),
        ]

    def __str__(self):
        return f"{self.tipo}: {self.nombre}"


class EjecucionAnalisis(models.Model):
    """
    A single execution instance of an analysis (sync or async).
    Long-running executions (> 2 s) are delegated to Celery workers.
    Bounded context: Análisis y Reportes (architecture.md §5.4)
    """
    class Estado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        EN_PROCESO = 'EN_PROCESO', 'En Proceso'
        COMPLETADO = 'COMPLETADO', 'Completado'
        FALLIDO = 'FALLIDO', 'Fallido'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    analisis = models.ForeignKey(
        Analisis, on_delete=models.CASCADE, related_name='ejecuciones', db_index=True
    )
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.PENDIENTE, db_index=True
    )
    celery_task_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    iniciado_en = models.DateTimeField(auto_now_add=True)
    completado_en = models.DateTimeField(null=True, blank=True)
    duracion_ms = models.PositiveIntegerField(null=True, blank=True)
    resultado = models.JSONField(null=True, blank=True)
    error = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'ejecuciones_analisis'
        indexes = [
            models.Index(fields=['analisis', 'estado'], name='ejecucion_analisis_estado_idx'),
        ]

    def __str__(self):
        return f"Ejecución {self.id} – {self.estado}"


class Reporte(models.Model):
    """
    A generated report (e.g., monthly spending by client/area/project).
    Target: generated in ≤ 100 ms from cached data (architecture.md §6 Performance).
    Bounded context: Análisis y Reportes (architecture.md §5.4)
    """
    class Tipo(models.TextChoices):
        MENSUAL = 'MENSUAL', 'Reporte Mensual'
        ANUAL = 'ANUAL', 'Reporte Anual'
        PROYECTO = 'PROYECTO', 'Reporte por Proyecto'
        AREA = 'AREA', 'Reporte por Área'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombre = models.CharField(max_length=255)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, db_index=True)
    proyecto_id = models.UUIDField(db_index=True)
    empresa_id = models.UUIDField(db_index=True)
    periodo_inicio = models.DateField(db_index=True)
    periodo_fin = models.DateField()
    datos = models.JSONField(default=dict)
    generado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'reportes'
        indexes = [
            models.Index(fields=['empresa_id', 'tipo', 'periodo_inicio'],
                         name='rep_emp_tipo_per_idx'),
            models.Index(fields=['proyecto_id', 'periodo_inicio'],
                         name='reportes_proyecto_periodo_idx'),
        ]

    def __str__(self):
        return f"{self.tipo} {self.nombre} ({self.periodo_inicio})"


class Alerta(models.Model):
    """
    An alert triggered when cost thresholds or anomalies are detected.
    Bounded context: Análisis y Reportes (architecture.md §5.4)
    """
    class Tipo(models.TextChoices):
        PRESUPUESTO = 'PRESUPUESTO', 'Exceso de Presupuesto'
        ANOMALIA = 'ANOMALIA', 'Anomalía de Consumo'
        RECURSO_INFRAUTILIZADO = 'RECURSO_INFRAUTILIZADO', 'Recurso Infrautilizado'
        PICO_CONSUMO = 'PICO_CONSUMO', 'Pico de Consumo'

    class Severidad(models.TextChoices):
        BAJA = 'BAJA', 'Baja'
        MEDIA = 'MEDIA', 'Media'
        ALTA = 'ALTA', 'Alta'
        CRITICA = 'CRITICA', 'Crítica'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    analisis = models.ForeignKey(
        Analisis, on_delete=models.CASCADE, related_name='alertas',
        null=True, blank=True, db_index=True,
    )
    reporte = models.ForeignKey(
        Reporte, on_delete=models.CASCADE, related_name='alertas',
        null=True, blank=True, db_index=True,
    )
    tipo = models.CharField(max_length=30, choices=Tipo.choices, db_index=True)
    mensaje = models.TextField()
    severidad = models.CharField(max_length=10, choices=Severidad.choices, db_index=True)
    resuelta = models.BooleanField(default=False, db_index=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'alertas'
        indexes = [
            models.Index(fields=['tipo', 'severidad', 'resuelta'],
                         name='alertas_tipo_severidad_idx'),
        ]

    def __str__(self):
        return f"{self.severidad} – {self.tipo}: {self.mensaje[:50]}"


class OportunidadAhorro(models.Model):
    """
    An identified waste pattern or underutilized resource opportunity.
    Bounded context: Análisis y Reportes (architecture.md §5.4)
    """
    class Estado(models.TextChoices):
        IDENTIFICADA = 'IDENTIFICADA', 'Identificada'
        EN_REVISION = 'EN_REVISION', 'En Revisión'
        IMPLEMENTADA = 'IMPLEMENTADA', 'Implementada'
        DESCARTADA = 'DESCARTADA', 'Descartada'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    analisis = models.ForeignKey(
        Analisis, on_delete=models.CASCADE, related_name='oportunidades_ahorro', db_index=True
    )
    recurso_cloud_id = models.UUIDField(db_index=True)
    descripcion = models.TextField()
    ahorro_estimado = models.DecimalField(max_digits=15, decimal_places=2)
    moneda = models.CharField(max_length=3, default='USD')
    estado = models.CharField(
        max_length=15, choices=Estado.choices, default=Estado.IDENTIFICADA, db_index=True
    )
    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'oportunidades_ahorro'
        indexes = [
            models.Index(fields=['analisis', 'estado'], name='oport_analiz_estado_idx'),
        ]

    def __str__(self):
        return f"Ahorro ${self.ahorro_estimado} {self.moneda}: {self.descripcion[:50]}"


class Notificacion(models.Model):
    """
    A notification sent to users (email on async analysis completion > 2 s).
    Bounded context: Análisis y Reportes (architecture.md §5.4)
    """
    class Tipo(models.TextChoices):
        EMAIL = 'EMAIL', 'Email'
        PUSH = 'PUSH', 'Push Notification'
        WEBHOOK = 'WEBHOOK', 'Webhook'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    oportunidad_ahorro = models.ForeignKey(
        OportunidadAhorro, on_delete=models.SET_NULL,
        related_name='notificaciones', null=True, blank=True, db_index=True,
    )
    ejecucion_analisis = models.ForeignKey(
        EjecucionAnalisis, on_delete=models.SET_NULL,
        related_name='notificaciones', null=True, blank=True,
    )
    usuario_id = models.UUIDField(db_index=True)
    email_destino = models.EmailField()
    tipo = models.CharField(max_length=10, choices=Tipo.choices, default=Tipo.EMAIL)
    asunto = models.CharField(max_length=255)
    cuerpo = models.TextField()
    enviada = models.BooleanField(default=False, db_index=True)
    enviada_en = models.DateTimeField(null=True, blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notificaciones'
        indexes = [
            models.Index(fields=['usuario_id', 'enviada'], name='notif_usr_enviada_idx'),
        ]

    def __str__(self):
        return f"{self.tipo} → {self.email_destino}: {self.asunto}"
