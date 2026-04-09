import uuid
from django.db import models


class ProveedorCloud(models.Model):
    """
    A cloud provider (e.g. AWS mandatory, GCP optional).
    Extensible via adapter/plugin pattern (architecture.md §2.3 Extensibility).
    Bounded context: Cloud (architecture.md §5.3)
    """
    class Tipo(models.TextChoices):
        AWS = 'AWS', 'Amazon Web Services'
        GCP = 'GCP', 'Google Cloud Platform'
        AZURE = 'AZURE', 'Microsoft Azure'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=10, choices=Tipo.choices, unique=True, db_index=True)
    activo = models.BooleanField(default=True, db_index=True)
    configuracion = models.JSONField(default=dict, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'proveedores_cloud'
        indexes = [
            models.Index(fields=['tipo'], name='proveedores_tipo_idx'),
            models.Index(fields=['activo'], name='proveedores_activo_idx'),
        ]

    def __str__(self):
        return self.nombre


class CuentaCloud(models.Model):
    """
    A cloud account linked to a project and a provider.
    Source of truth for account validation used by Project Service.
    Bounded context: Cloud (architecture.md §5.3)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombre = models.CharField(max_length=255)
    proveedor = models.ForeignKey(
        ProveedorCloud,
        on_delete=models.PROTECT,
        related_name='cuentas',
        db_index=True,
    )
    proyecto_id = models.UUIDField(db_index=True)
    account_external_id = models.CharField(
        max_length=100,
        help_text="AWS Account ID or GCP Project ID"
    )
    region = models.CharField(max_length=50, default='us-east-1')
    activa = models.BooleanField(default=True, db_index=True)
    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'cuentas_cloud'
        indexes = [
            models.Index(fields=['proyecto_id'], name='cuentas_proyecto_idx'),
            models.Index(fields=['activa'], name='cuentas_activa_idx'),
            models.Index(fields=['proveedor', 'activa'], name='cuentas_proveedor_activa_idx'),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.proveedor.tipo})"


class RecursoCloud(models.Model):
    """
    A specific cloud resource (EC2 instance, S3 bucket, RDS, etc.) within an account.
    Bounded context: Cloud (architecture.md §5.3)
    """
    class TipoRecurso(models.TextChoices):
        EC2 = 'EC2', 'EC2 Instance'
        S3 = 'S3', 'S3 Bucket'
        RDS = 'RDS', 'RDS Database'
        LAMBDA = 'LAMBDA', 'Lambda Function'
        EKS = 'EKS', 'EKS Cluster'
        VPC = 'VPC', 'VPC'
        OTRO = 'OTRO', 'Otro'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cuenta = models.ForeignKey(
        CuentaCloud,
        on_delete=models.CASCADE,
        related_name='recursos',
        db_index=True,
    )
    nombre = models.CharField(max_length=255, db_index=True)
    tipo = models.CharField(max_length=20, choices=TipoRecurso.choices, db_index=True)
    region = models.CharField(max_length=50)
    resource_external_id = models.CharField(
        max_length=200,
        help_text="AWS ARN or GCP resource ID"
    )
    etiquetas = models.JSONField(default=dict, blank=True)
    activo = models.BooleanField(default=True, db_index=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'recursos_cloud'
        indexes = [
            models.Index(fields=['cuenta', 'activo'], name='recursos_cuenta_activo_idx'),
            models.Index(fields=['tipo', 'activo'], name='recursos_tipo_activo_idx'),
            models.Index(fields=['region'], name='recursos_region_idx'),
        ]

    def __str__(self):
        return f"{self.tipo}: {self.nombre}"


class MetricaConsumo(models.Model):
    """
    A consumption metric (cost, compute) recorded for a cloud resource.
    Used for monthly reporting (≤100 ms SLA via Redis cache).
    Bounded context: Cloud (architecture.md §5.3)
    """
    class TipoMetrica(models.TextChoices):
        COSTO = 'COSTO', 'Costo ($)'
        CPU = 'CPU', 'CPU Hours'
        MEMORIA = 'MEMORIA', 'Memory GB-Hours'
        ALMACENAMIENTO = 'ALMACENAMIENTO', 'Storage GB'
        TRANSFERENCIA = 'TRANSFERENCIA', 'Data Transfer GB'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recurso = models.ForeignKey(
        RecursoCloud,
        on_delete=models.CASCADE,
        related_name='metricas',
        db_index=True,
    )
    tipo_metrica = models.CharField(max_length=20, choices=TipoMetrica.choices, db_index=True)
    periodo_inicio = models.DateField(db_index=True)
    periodo_fin = models.DateField()
    valor = models.DecimalField(max_digits=20, decimal_places=6)
    costo = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    moneda = models.CharField(max_length=3, default='USD')
    registrada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'metricas_consumo'
        indexes = [
            models.Index(fields=['recurso', 'tipo_metrica', 'periodo_inicio'],
                         name='met_rec_tipo_per_idx'),
            models.Index(fields=['periodo_inicio', 'periodo_fin'],
                         name='metricas_periodo_idx'),
        ]

    def __str__(self):
        return f"{self.tipo_metrica} {self.recurso.nombre}: {self.valor} ({self.periodo_inicio})"
