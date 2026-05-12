"""
Management command: python manage.py seed_usuarios_data

Seeds usuarios_db with:
  - 3  Empresa records with fixed UUIDs (used by JMeter / Postman / ASR experiments)
  - 50 additional Empresa records (volume for load tests)
  - 1000 Empleado records distributed across companies
  - 5000 Proyecto records (ASR16 latency experiment load)
  - 500  Presupuesto records (one per first 500 proyectos)

The three fixed empresa UUIDs match experiments/data/projects_payload.json
and the ASR3 Postman collection.  Idempotent on empresa records.
"""
import uuid
import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from projects.models import Empresa, Empleado, Proyecto, Presupuesto

FIXED_EMPRESAS = [
    ('550e8400-e29b-41d4-a716-446655440001', 'BITE Empresa Principal',   'NIT-9000000001'),
    ('550e8400-e29b-41d4-a716-446655440002', 'BITE Empresa Secundaria',  'NIT-9000000002'),
    ('550e8400-e29b-41d4-a716-446655440003', 'BITE Empresa Terciaria',   'NIT-9000000003'),
]

ROLES = ['ADMIN', 'MANAGER', 'ANALYST']


class Command(BaseCommand):
    help = 'Seed Empresa, Empleado, Proyecto and Presupuesto for experiments'

    def handle(self, *args, **options):
        self.stdout.write('Seeding usuarios data...')

        # ── 1. Fixed empresas (idempotent) ───────────────────────────────────
        for emp_id, nombre, nit in FIXED_EMPRESAS:
            empresa, created = Empresa.objects.get_or_create(
                id=uuid.UUID(emp_id),
                defaults={'nombre': nombre, 'nit': nit, 'activa': True},
            )
            status = 'created' if created else 'exists'
            self.stdout.write(f'  Empresa {empresa.id} [{status}]')

        # ── 2. Additional empresas (skip if already populated) ───────────────
        if Empresa.objects.count() < 10:
            bulk = [
                Empresa(
                    id=uuid.uuid4(),
                    nombre=f'Empresa {i}',
                    nit=f'NIT-{1000000000 + i}',
                    activa=True,
                )
                for i in range(1, 51)
            ]
            Empresa.objects.bulk_create(bulk, ignore_conflicts=True)
            self.stdout.write(f'  +50 empresas adicionales')

        # ── 3. Empleados ─────────────────────────────────────────────────────
        if Empleado.objects.count() < 100:
            empresa_ids = list(Empresa.objects.values_list('id', flat=True))
            bulk = [
                Empleado(
                    id=uuid.uuid4(),
                    empresa_id=random.choice(empresa_ids),
                    nombre_completo=f'Empleado {i}',
                    email=f'empleado{i}@empresa{i % 50}.com',
                    rol=random.choice(ROLES),
                )
                for i in range(1, 1001)
            ]
            Empleado.objects.bulk_create(bulk, ignore_conflicts=True)
            self.stdout.write(f'  +1000 empleados')

        # ── 4. Proyectos ─────────────────────────────────────────────────────
        if Proyecto.objects.count() < 1000:
            empresa_ids = list(Empresa.objects.values_list('id', flat=True))
            bulk = [
                Proyecto(
                    id=uuid.uuid4(),
                    nombre=f'Proyecto {i}',
                    descripcion='Proyecto para experimento ASR latencia',
                    empresa_id=random.choice(empresa_ids),
                    estado='ACTIVO',
                )
                for i in range(1, 5001)
            ]
            Proyecto.objects.bulk_create(bulk, ignore_conflicts=True)
            self.stdout.write(f'  +5000 proyectos')

        # ── 5. Presupuestos (first 500 proyectos without one) ─────────────────
        if Presupuesto.objects.count() < 100:
            proyectos_sin_presupuesto = (
                Proyecto.objects.filter(presupuesto__isnull=True)[:500]
            )
            bulk = [
                Presupuesto(
                    id=uuid.uuid4(),
                    proyecto=p,
                    monto_mensual=Decimal(str(round(random.uniform(100, 10000), 2))),
                    moneda='USD',
                    alerta_porcentaje=80,
                )
                for p in proyectos_sin_presupuesto
            ]
            Presupuesto.objects.bulk_create(bulk, ignore_conflicts=True)
            self.stdout.write(f'  +{len(bulk)} presupuestos')

        self.stdout.write(self.style.SUCCESS('Usuarios seed data ready.'))
