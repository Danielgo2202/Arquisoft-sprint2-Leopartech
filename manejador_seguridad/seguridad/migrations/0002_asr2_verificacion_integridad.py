from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('seguridad', '0001_initial'),
    ]

    operations = [
        # Add INTEGRIDAD_TLS choice to EventoSeguridad.tipo
        migrations.AlterField(
            model_name='eventoseguridad',
            name='tipo',
            field=models.CharField(
                choices=[
                    ('acceso_no_autorizado', 'Acceso no autorizado'),
                    ('acceso_cruzado_tenant', 'Acceso cruzado entre tenants'),
                    ('token_invalido', 'Token inválido'),
                    ('integridad_tls', 'Verificación TLS/Integridad'),
                ],
                db_index=True,
                max_length=30,
            ),
        ),
        # Create new VerificacionIntegridad table for ASR2
        migrations.CreateModel(
            name='VerificacionIntegridad',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('endpoint', models.CharField(max_length=500)),
                ('metodo', models.CharField(max_length=10)),
                ('protocolo', models.CharField(max_length=10)),
                ('ip_origen', models.GenericIPAddressField(blank=True, null=True)),
                ('resultado', models.CharField(
                    choices=[
                        ('aceptado', 'Solicitud aceptada (HTTPS)'),
                        ('rechazado', 'Solicitud rechazada (HTTP sin cifrado)'),
                        ('redirigido', 'Redirigido a HTTPS'),
                        ('integridad_ok', 'Hash de integridad válido'),
                        ('integridad_fallo', 'Hash de integridad inválido'),
                    ],
                    max_length=20,
                )),
                ('tls_version', models.CharField(blank=True, default='', max_length=20)),
                ('cipher_suite', models.CharField(blank=True, default='', max_length=100)),
                ('evidencia', models.JSONField(default=dict)),
                ('creado_en', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                'db_table': 'verificaciones_integridad',
                'ordering': ['-creado_en'],
            },
        ),
    ]
