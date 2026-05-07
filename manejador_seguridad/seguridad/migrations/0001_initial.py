import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name='EventoSeguridad',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('tipo', models.CharField(
                    choices=[
                        ('acceso_no_autorizado', 'Acceso no autorizado'),
                        ('acceso_cruzado_tenant', 'Acceso cruzado entre tenants'),
                        ('token_invalido', 'Token inválido'),
                    ],
                    max_length=30,
                    db_index=True,
                )),
                ('endpoint', models.CharField(max_length=500)),
                ('metodo', models.CharField(max_length=10)),
                ('ip_origen', models.GenericIPAddressField(blank=True, null=True)),
                ('empresa_id_token', models.UUIDField(blank=True, db_index=True, null=True)),
                ('empresa_id_recurso', models.UUIDField(blank=True, null=True)),
                ('bloqueado', models.BooleanField(default=True)),
                ('evidencia', models.JSONField(default=dict)),
                ('creado_en', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={'db_table': 'eventos_seguridad', 'ordering': ['-creado_en']},
        ),
        migrations.CreateModel(
            name='RegistroAuditoria',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('evento', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='registros',
                    to='seguridad.eventoseguridad',
                )),
                ('descripcion', models.TextField()),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
            ],
            options={'db_table': 'registros_auditoria', 'ordering': ['-creado_en']},
        ),
    ]
