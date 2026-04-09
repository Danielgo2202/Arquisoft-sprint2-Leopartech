import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Empresa',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('nombre', models.CharField(db_index=True, max_length=255)),
                ('nit', models.CharField(max_length=50, unique=True)),
                ('activa', models.BooleanField(db_index=True, default=True)),
                ('creada_en', models.DateTimeField(auto_now_add=True)),
                ('actualizada_en', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'empresas'},
        ),
        migrations.AddIndex(
            model_name='empresa',
            index=models.Index(fields=['nit'], name='empresas_nit_idx'),
        ),
        migrations.AddIndex(
            model_name='empresa',
            index=models.Index(fields=['activa'], name='empresas_activa_idx'),
        ),
        migrations.CreateModel(
            name='Proyecto',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('nombre', models.CharField(max_length=255)),
                ('descripcion', models.TextField(blank=True, default='')),
                ('empresa', models.ForeignKey(
                    db_index=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='proyectos',
                    to='projects.empresa',
                )),
                ('estado', models.CharField(
                    choices=[('ACTIVO', 'Activo'), ('INACTIVO', 'Inactivo'), ('ARCHIVADO', 'Archivado')],
                    db_index=True,
                    default='ACTIVO',
                    max_length=20,
                )),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'proyectos'},
        ),
        migrations.AddIndex(
            model_name='proyecto',
            index=models.Index(fields=['empresa', 'estado'], name='proyectos_empresa_estado_idx'),
        ),
        migrations.AddIndex(
            model_name='proyecto',
            index=models.Index(fields=['creado_en'], name='proyectos_creado_en_idx'),
        ),
        migrations.CreateModel(
            name='CuentaCloudRef',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('proyecto', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='cuentas_cloud',
                    to='projects.proyecto',
                )),
                ('cuenta_cloud_id', models.UUIDField(db_index=True)),
                ('activa', models.BooleanField(default=True)),
                ('creada_en', models.DateTimeField(auto_now_add=True)),
            ],
            options={'db_table': 'cuentas_cloud_ref'},
        ),
        migrations.AlterUniqueTogether(
            name='cuentacloudref',
            unique_together={('proyecto', 'cuenta_cloud_id')},
        ),
        migrations.AddIndex(
            model_name='cuentacloudref',
            index=models.Index(fields=['cuenta_cloud_id'], name='cuenta_ref_cloud_id_idx'),
        ),
        migrations.CreateModel(
            name='Presupuesto',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('proyecto', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='presupuesto',
                    to='projects.proyecto',
                )),
                ('monto_mensual', models.DecimalField(decimal_places=2, max_digits=15)),
                ('moneda', models.CharField(default='USD', max_length=3)),
                ('alerta_porcentaje', models.PositiveSmallIntegerField(default=80)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'presupuestos'},
        ),
    ]
