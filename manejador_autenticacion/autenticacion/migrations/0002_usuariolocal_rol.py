from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('autenticacion', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuariolocal',
            name='rol',
            field=models.CharField(
                max_length=50,
                default='ANALYST',
                choices=[('ADMIN', 'Admin'), ('MANAGER', 'Manager'), ('ANALYST', 'Analyst')],
            ),
        ),
    ]
