import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='EventoEntrante',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('evento_id', models.CharField(db_index=True, max_length=255, unique=True)),
                ('tipo_evento', models.CharField(db_index=True, max_length=100)),
                ('payload', models.JSONField()),
                ('procesado', models.BooleanField(db_index=True, default=False)),
                ('procesado_en', models.DateTimeField(blank=True, null=True)),
                ('recibido_en', models.DateTimeField(auto_now_add=True)),
            ],
            options={'db_table': 'eventos_entrantes'},
        ),
        migrations.AddIndex(
            model_name='eventoEntrante',
            index=models.Index(fields=['evento_id'], name='evento_id_idx'),
        ),
        migrations.AddIndex(
            model_name='eventoEntrante',
            index=models.Index(fields=['tipo_evento', 'procesado'], name='evento_tipo_procesado_idx'),
        ),
        migrations.CreateModel(
            name='Analisis',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('nombre', models.CharField(max_length=255)),
                ('proyecto_id', models.UUIDField(db_index=True)),
                ('empresa_id', models.UUIDField(db_index=True)),
                ('tipo', models.CharField(
                    choices=[('COSTO', 'Análisis de Costos'), ('CAPACIDAD', 'Análisis de Capacidad'),
                             ('OPTIMIZACION', 'Optimización de Recursos'), ('DESPERDICIO', 'Identificación de Desperdicio')],
                    db_index=True, max_length=20,
                )),
                ('estado', models.CharField(
                    choices=[('PENDIENTE', 'Pendiente'), ('EN_PROCESO', 'En Proceso'),
                             ('COMPLETADO', 'Completado'), ('FALLIDO', 'Fallido')],
                    db_index=True, default='PENDIENTE', max_length=20,
                )),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'analisis'},
        ),
        migrations.AddIndex(
            model_name='analisis',
            index=models.Index(fields=['proyecto_id', 'estado'], name='analisis_proyecto_estado_idx'),
        ),
        migrations.AddIndex(
            model_name='analisis',
            index=models.Index(fields=['empresa_id', 'tipo'], name='analisis_empresa_tipo_idx'),
        ),
        migrations.CreateModel(
            name='EjecucionAnalisis',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('analisis', models.ForeignKey(
                    db_index=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ejecuciones',
                    to='events.analisis',
                )),
                ('estado', models.CharField(
                    choices=[('PENDIENTE', 'Pendiente'), ('EN_PROCESO', 'En Proceso'),
                             ('COMPLETADO', 'Completado'), ('FALLIDO', 'Fallido')],
                    db_index=True, default='PENDIENTE', max_length=20,
                )),
                ('celery_task_id', models.CharField(blank=True, db_index=True, max_length=255, null=True)),
                ('iniciado_en', models.DateTimeField(auto_now_add=True)),
                ('completado_en', models.DateTimeField(blank=True, null=True)),
                ('duracion_ms', models.PositiveIntegerField(blank=True, null=True)),
                ('resultado', models.JSONField(blank=True, null=True)),
                ('error', models.TextField(blank=True, null=True)),
            ],
            options={'db_table': 'ejecuciones_analisis'},
        ),
        migrations.AddIndex(
            model_name='ejecucionanalisis',
            index=models.Index(fields=['analisis', 'estado'], name='ejecucion_analisis_estado_idx'),
        ),
        migrations.CreateModel(
            name='Reporte',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('nombre', models.CharField(max_length=255)),
                ('tipo', models.CharField(
                    choices=[('MENSUAL', 'Reporte Mensual'), ('ANUAL', 'Reporte Anual'),
                             ('PROYECTO', 'Reporte por Proyecto'), ('AREA', 'Reporte por Área')],
                    db_index=True, max_length=20,
                )),
                ('proyecto_id', models.UUIDField(db_index=True)),
                ('empresa_id', models.UUIDField(db_index=True)),
                ('periodo_inicio', models.DateField(db_index=True)),
                ('periodo_fin', models.DateField()),
                ('datos', models.JSONField(default=dict)),
                ('generado_en', models.DateTimeField(auto_now_add=True)),
            ],
            options={'db_table': 'reportes'},
        ),
        migrations.AddIndex(
            model_name='reporte',
            index=models.Index(
                fields=['empresa_id', 'tipo', 'periodo_inicio'],
                name='rep_emp_tipo_per_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='reporte',
            index=models.Index(fields=['proyecto_id', 'periodo_inicio'], name='reportes_proyecto_periodo_idx'),
        ),
        migrations.CreateModel(
            name='Alerta',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('analisis', models.ForeignKey(
                    blank=True, db_index=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='alertas', to='events.analisis',
                )),
                ('reporte', models.ForeignKey(
                    blank=True, db_index=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='alertas', to='events.reporte',
                )),
                ('tipo', models.CharField(
                    choices=[('PRESUPUESTO', 'Exceso de Presupuesto'), ('ANOMALIA', 'Anomalía de Consumo'),
                             ('RECURSO_INFRAUTILIZADO', 'Recurso Infrautilizado'), ('PICO_CONSUMO', 'Pico de Consumo')],
                    db_index=True, max_length=30,
                )),
                ('mensaje', models.TextField()),
                ('severidad', models.CharField(
                    choices=[('BAJA', 'Baja'), ('MEDIA', 'Media'), ('ALTA', 'Alta'), ('CRITICA', 'Crítica')],
                    db_index=True, max_length=10,
                )),
                ('resuelta', models.BooleanField(db_index=True, default=False)),
                ('creada_en', models.DateTimeField(auto_now_add=True)),
            ],
            options={'db_table': 'alertas'},
        ),
        migrations.AddIndex(
            model_name='alerta',
            index=models.Index(fields=['tipo', 'severidad', 'resuelta'], name='alertas_tipo_severidad_idx'),
        ),
        migrations.CreateModel(
            name='OportunidadAhorro',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('analisis', models.ForeignKey(
                    db_index=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='oportunidades_ahorro',
                    to='events.analisis',
                )),
                ('recurso_cloud_id', models.UUIDField(db_index=True)),
                ('descripcion', models.TextField()),
                ('ahorro_estimado', models.DecimalField(decimal_places=2, max_digits=15)),
                ('moneda', models.CharField(default='USD', max_length=3)),
                ('estado', models.CharField(
                    choices=[('IDENTIFICADA', 'Identificada'), ('EN_REVISION', 'En Revisión'),
                             ('IMPLEMENTADA', 'Implementada'), ('DESCARTADA', 'Descartada')],
                    db_index=True, default='IDENTIFICADA', max_length=15,
                )),
                ('creada_en', models.DateTimeField(auto_now_add=True)),
                ('actualizada_en', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'oportunidades_ahorro'},
        ),
        migrations.AddIndex(
            model_name='oportunidadahorro',
            index=models.Index(fields=['analisis', 'estado'], name='oport_analiz_estado_idx'),
        ),
        migrations.CreateModel(
            name='Notificacion',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('oportunidad_ahorro', models.ForeignKey(
                    blank=True, db_index=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='notificaciones', to='events.oportunidadahorro',
                )),
                ('ejecucion_analisis', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='notificaciones', to='events.ejecucionanalisis',
                )),
                ('usuario_id', models.UUIDField(db_index=True)),
                ('email_destino', models.EmailField()),
                ('tipo', models.CharField(
                    choices=[('EMAIL', 'Email'), ('PUSH', 'Push Notification'), ('WEBHOOK', 'Webhook')],
                    default='EMAIL', max_length=10,
                )),
                ('asunto', models.CharField(max_length=255)),
                ('cuerpo', models.TextField()),
                ('enviada', models.BooleanField(db_index=True, default=False)),
                ('enviada_en', models.DateTimeField(blank=True, null=True)),
                ('creada_en', models.DateTimeField(auto_now_add=True)),
            ],
            options={'db_table': 'notificaciones'},
        ),
        migrations.AddIndex(
            model_name='notificacion',
            index=models.Index(fields=['usuario_id', 'enviada'], name='notif_usr_enviada_idx'),
        ),
    ]
