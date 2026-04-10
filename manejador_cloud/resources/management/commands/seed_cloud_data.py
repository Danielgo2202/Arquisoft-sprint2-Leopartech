"""
Management command: python manage.py seed_initial_data

Seeds the cloud_db with the minimum data required for the experiments:
  - 2  ProveedorCloud records  (AWS, GCP)
  - 5  CuentaCloud records     (active; includes the specific UUIDs used by JMeter)
  - 10 RecursoCloud records    (linked to the seeded accounts)
  - 5  MetricaConsumo records  (linked to the seeded resources)

The CuentaCloud UUIDs 550e8400-e29b-41d4-a716-44665544001{1,2} match the
experiments/data/projects_payload.json used by the ASR16 JMeter latency test.

Idempotent: uses get_or_create for every record, so safe to run on every start.
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand

from resources.models import ProveedorCloud, CuentaCloud, RecursoCloud, MetricaConsumo


# ── Well-known UUIDs used by JMeter projects_payload.json ───────────────────
CUENTA_CLOUD_IDS = [
    uuid.UUID('550e8400-e29b-41d4-a716-446655440011'),  # JMeter payload cuenta 1
    uuid.UUID('550e8400-e29b-41d4-a716-446655440012'),  # JMeter payload cuenta 2
    uuid.UUID('550e8400-e29b-41d4-a716-446655440013'),
    uuid.UUID('550e8400-e29b-41d4-a716-446655440014'),
    uuid.UUID('550e8400-e29b-41d4-a716-446655440015'),
]

# Placeholder proyecto_id for seeded accounts (no FK enforcement cross-service)
SEED_PROYECTO_ID = uuid.UUID('550e8400-e29b-41d4-a716-446655440099')


class Command(BaseCommand):
    help = 'Seeds ProveedorCloud, CuentaCloud, RecursoCloud, MetricaConsumo for experiments'

    def handle(self, *args, **options):
        self.stdout.write('Seeding cloud data...')

        # ── 1. ProveedorCloud ────────────────────────────────────────────────
        aws, _ = ProveedorCloud.objects.get_or_create(
            tipo='AWS',
            defaults={
                'nombre': 'Amazon Web Services',
                'activo': True,
                'configuracion': {'regions': ['us-east-1', 'us-west-2', 'eu-west-1']},
            },
        )
        gcp, _ = ProveedorCloud.objects.get_or_create(
            tipo='GCP',
            defaults={
                'nombre': 'Google Cloud Platform',
                'activo': True,
                'configuracion': {'regions': ['us-central1', 'us-east1', 'europe-west1']},
            },
        )
        self.stdout.write(f'  ProveedorCloud: AWS={aws.id}  GCP={gcp.id}')

        # ── 2. CuentaCloud ───────────────────────────────────────────────────
        cuentas = []
        proveedores = [aws, aws, gcp, aws, gcp]
        for i, cuenta_id in enumerate(CUENTA_CLOUD_IDS):
            proveedor = proveedores[i]
            cuenta, created = CuentaCloud.objects.get_or_create(
                id=cuenta_id,
                defaults={
                    'nombre': f'Cuenta {proveedor.tipo} {i + 1}',
                    'proveedor': proveedor,
                    'proyecto_id': SEED_PROYECTO_ID,
                    'account_external_id': f'{proveedor.tipo.lower()}-seed-{i + 1:04d}',
                    'region': 'us-east-1' if proveedor.tipo == 'AWS' else 'us-central1',
                    'activa': True,
                },
            )
            cuentas.append(cuenta)
            status = 'created' if created else 'exists'
            self.stdout.write(f'  CuentaCloud {cuenta.id} [{status}]')

        # ── 3. RecursoCloud ──────────────────────────────────────────────────
        tipos = ['EC2', 'S3', 'RDS', 'LAMBDA', 'EC2', 'S3', 'RDS', 'EC2', 'LAMBDA', 'S3']
        recursos = []
        for i in range(10):
            cuenta = cuentas[i % len(cuentas)]
            tipo = tipos[i]
            # Use a deterministic ID so this is idempotent (valid hex UUIDs)
            recurso_id = uuid.UUID(f'aaaaaaaa-aaaa-0000-0000-{(i + 1):012x}')
            recurso, created = RecursoCloud.objects.get_or_create(
                id=recurso_id,
                defaults={
                    'cuenta': cuenta,
                    'nombre': f'Recurso-{tipo}-{i + 1}',
                    'tipo': tipo,
                    'region': cuenta.region,
                    'resource_external_id': f'arn:aws:{tipo.lower()}:us-east-1:seed:{i + 1}',
                    'etiquetas': {'env': 'seed', 'index': str(i + 1)},
                    'activo': True,
                },
            )
            recursos.append(recurso)
            status = 'created' if created else 'exists'
            self.stdout.write(f'  RecursoCloud {recurso.id} [{status}]')

        # ── 4. MetricaConsumo ────────────────────────────────────────────────
        hoy = date.today()
        inicio = date(hoy.year, hoy.month, 1)
        fin = hoy
        tipos_metrica = ['COSTO', 'CPU', 'MEMORIA', 'ALMACENAMIENTO', 'TRANSFERENCIA']
        for i in range(5):
            recurso = recursos[i]
            tipo_m = tipos_metrica[i]
            metrica_id = uuid.UUID(f'bbbbbbbb-bbbb-0000-0000-{(i + 1):012x}')
            metrica, created = MetricaConsumo.objects.get_or_create(
                id=metrica_id,
                defaults={
                    'recurso': recurso,
                    'tipo_metrica': tipo_m,
                    'periodo_inicio': inicio,
                    'periodo_fin': fin,
                    'valor': Decimal(str(round(100.0 * (i + 1), 6))),
                    'costo': Decimal(str(round(10.0 * (i + 1), 4))),
                    'moneda': 'USD',
                },
            )
            status = 'created' if created else 'exists'
            self.stdout.write(f'  MetricaConsumo {metrica.id} [{status}]')

        self.stdout.write(self.style.SUCCESS('Cloud seed data ready.'))
