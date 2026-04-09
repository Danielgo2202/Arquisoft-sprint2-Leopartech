import uuid
from django.db import models


class Empresa(models.Model):
    """
    A client company registered on the BITE.co platform.
    Bounded context: Gestión de Usuarios (architecture.md §5.1)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombre = models.CharField(max_length=255, db_index=True)
    nit = models.CharField(max_length=50, unique=True)
    activa = models.BooleanField(default=True, db_index=True)
    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'empresas'
        indexes = [
            models.Index(fields=['nit'], name='empresas_nit_idx'),
            models.Index(fields=['activa'], name='empresas_activa_idx'),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.nit})"


class Proyecto(models.Model):
    """
    A project within a company, linked to cloud accounts and a budget.
    Bounded context: Gestión de Usuarios (architecture.md §5.1)
    """
    class Estado(models.TextChoices):
        ACTIVO = 'ACTIVO', 'Activo'
        INACTIVO = 'INACTIVO', 'Inactivo'
        ARCHIVADO = 'ARCHIVADO', 'Archivado'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombre = models.CharField(max_length=255)
    descripcion = models.TextField(blank=True, default='')
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.PROTECT,
        related_name='proyectos',
        db_index=True,
    )
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.ACTIVO,
        db_index=True,
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'proyectos'
        indexes = [
            models.Index(fields=['empresa', 'estado'], name='proyectos_empresa_estado_idx'),
            models.Index(fields=['creado_en'], name='proyectos_creado_en_idx'),
        ]

    def __str__(self):
        return self.nombre


class CuentaCloudRef(models.Model):
    """
    Local reference to a CuentaCloud managed by Resource Service.
    Stores the ID only; validation is done via Redis cache / Resource Service API.
    Bounded context: Cloud (architecture.md §5.3) - cross-service reference
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    proyecto = models.ForeignKey(
        Proyecto,
        on_delete=models.CASCADE,
        related_name='cuentas_cloud',
    )
    cuenta_cloud_id = models.UUIDField(db_index=True)
    activa = models.BooleanField(default=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'cuentas_cloud_ref'
        unique_together = [['proyecto', 'cuenta_cloud_id']]
        indexes = [
            models.Index(fields=['cuenta_cloud_id'], name='cuenta_ref_cloud_id_idx'),
        ]

    def __str__(self):
        return f"CuentaCloud {self.cuenta_cloud_id} → Proyecto {self.proyecto_id}"


class Presupuesto(models.Model):
    """
    Budget defined for a project.
    Bounded context: Gestión de Usuarios (architecture.md §5.1)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    proyecto = models.OneToOneField(
        Proyecto,
        on_delete=models.CASCADE,
        related_name='presupuesto',
    )
    monto_mensual = models.DecimalField(max_digits=15, decimal_places=2)
    moneda = models.CharField(max_length=3, default='USD')
    alerta_porcentaje = models.PositiveSmallIntegerField(default=80)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'presupuestos'

    def __str__(self):
        return f"Presupuesto {self.proyecto.nombre}: {self.monto_mensual} {self.moneda}"
