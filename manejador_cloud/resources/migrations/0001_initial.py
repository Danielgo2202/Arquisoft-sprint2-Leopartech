import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='ProveedorCloud',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('nombre', models.CharField(max_length=100)),
                ('tipo', models.CharField(
                    choices=[('AWS', 'Amazon Web Services'), ('GCP', 'Google Cloud Platform'), ('AZURE', 'Microsoft Azure')],
                    db_index=True, max_length=10, unique=True,
                )),
                ('activo', models.BooleanField(db_index=True, default=True)),
                ('configuracion', models.JSONField(blank=True, default=dict)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
            ],
            options={'db_table': 'proveedores_cloud'},
        ),
        migrations.AddIndex(
            model_name='proveedorcloud',
            index=models.Index(fields=['tipo'], name='proveedores_tipo_idx'),
        ),
        migrations.AddIndex(
            model_name='proveedorcloud',
            index=models.Index(fields=['activo'], name='proveedores_activo_idx'),
        ),
        migrations.CreateModel(
            name='CuentaCloud',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('nombre', models.CharField(max_length=255)),
                ('proveedor', models.ForeignKey(
                    db_index=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='cuentas',
                    to='resources.proveedorcloud',
                )),
                ('proyecto_id', models.UUIDField(db_index=True)),
                ('account_external_id', models.CharField(max_length=100)),
                ('region', models.CharField(default='us-east-1', max_length=50)),
                ('activa', models.BooleanField(db_index=True, default=True)),
                ('creada_en', models.DateTimeField(auto_now_add=True)),
                ('actualizada_en', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'cuentas_cloud'},
        ),
        migrations.AddIndex(
            model_name='cuentacloud',
            index=models.Index(fields=['proyecto_id'], name='cuentas_proyecto_idx'),
        ),
        migrations.AddIndex(
            model_name='cuentacloud',
            index=models.Index(fields=['activa'], name='cuentas_activa_idx'),
        ),
        migrations.AddIndex(
            model_name='cuentacloud',
            index=models.Index(fields=['proveedor', 'activa'], name='cuentas_proveedor_activa_idx'),
        ),
        migrations.CreateModel(
            name='RecursoCloud',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('cuenta', models.ForeignKey(
                    db_index=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='recursos',
                    to='resources.cuentacloud',
                )),
                ('nombre', models.CharField(db_index=True, max_length=255)),
                ('tipo', models.CharField(
                    choices=[('EC2', 'EC2 Instance'), ('S3', 'S3 Bucket'), ('RDS', 'RDS Database'),
                             ('LAMBDA', 'Lambda Function'), ('EKS', 'EKS Cluster'), ('VPC', 'VPC'), ('OTRO', 'Otro')],
                    db_index=True, max_length=20,
                )),
                ('region', models.CharField(max_length=50)),
                ('resource_external_id', models.CharField(max_length=200)),
                ('etiquetas', models.JSONField(blank=True, default=dict)),
                ('activo', models.BooleanField(db_index=True, default=True)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'recursos_cloud'},
        ),
        migrations.AddIndex(
            model_name='recursocloud',
            index=models.Index(fields=['cuenta', 'activo'], name='recursos_cuenta_activo_idx'),
        ),
        migrations.AddIndex(
            model_name='recursocloud',
            index=models.Index(fields=['tipo', 'activo'], name='recursos_tipo_activo_idx'),
        ),
        migrations.AddIndex(
            model_name='recursocloud',
            index=models.Index(fields=['region'], name='recursos_region_idx'),
        ),
        migrations.CreateModel(
            name='MetricaConsumo',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('recurso', models.ForeignKey(
                    db_index=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='metricas',
                    to='resources.recursocloud',
                )),
                ('tipo_metrica', models.CharField(
                    choices=[('COSTO', 'Costo ($)'), ('CPU', 'CPU Hours'), ('MEMORIA', 'Memory GB-Hours'),
                             ('ALMACENAMIENTO', 'Storage GB'), ('TRANSFERENCIA', 'Data Transfer GB')],
                    db_index=True, max_length=20,
                )),
                ('periodo_inicio', models.DateField(db_index=True)),
                ('periodo_fin', models.DateField()),
                ('valor', models.DecimalField(decimal_places=6, max_digits=20)),
                ('costo', models.DecimalField(decimal_places=4, default=0, max_digits=15)),
                ('moneda', models.CharField(default='USD', max_length=3)),
                ('registrada_en', models.DateTimeField(auto_now_add=True)),
            ],
            options={'db_table': 'metricas_consumo'},
        ),
        migrations.AddIndex(
            model_name='metricaconsumo',
            index=models.Index(
                fields=['recurso', 'tipo_metrica', 'periodo_inicio'],
                name='metricas_recurso_tipo_periodo_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='metricaconsumo',
            index=models.Index(fields=['periodo_inicio', 'periodo_fin'], name='metricas_periodo_idx'),
        ),
    ]
