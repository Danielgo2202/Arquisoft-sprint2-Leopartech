"""
Management command: python manage.py seed_reportes_data

Seeds reportes_db with:
  - 1000 Analisis records
  - 1000 Reporte records
  - 5000 EjecucionAnalisis records (for ASR17 scalability load)
  - 10000 EventoEntrante records (idempotency / event tracking load)

Idempotent: skips seeding if records already exist.
"""
import uuid
import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from events.models import Analisis, EjecucionAnalisis, Reporte, EventoEntrante

TIPOS_ANALISIS = ['COSTO', 'CAPACIDAD', 'OPTIMIZACION']
ESTADOS_ANALISIS = ['PENDIENTE', 'EN_PROCESO', 'COMPLETADO']
TIPOS_REPORTE = ['MENSUAL', 'PROYECTO', 'AREA']
TIPOS_EVENTO = ['proyecto.creado', 'infra.actualizada']

HOY = date.today()
INICIO_PERIODO = date(HOY.year, HOY.month, 1)


class Command(BaseCommand):
    help = 'Seed Analisis, Reporte, EjecucionAnalisis, EventoEntrante for experiments'

    def handle(self, *args, **options):
        self.stdout.write('Seeding reportes data...')

        # ── 1. Analisis ───────────────────────────────────────────────────────
        if Analisis.objects.count() < 100:
            bulk = [
                Analisis(
                    id=uuid.uuid4(),
                    nombre=f'Analisis {i}',
                    proyecto_id=uuid.uuid4(),
                    empresa_id=uuid.uuid4(),
                    tipo=random.choice(TIPOS_ANALISIS),
                    estado=random.choice(ESTADOS_ANALISIS),
                )
                for i in range(1, 1001)
            ]
            Analisis.objects.bulk_create(bulk)
            self.stdout.write('  +1000 analisis')

        # ── 2. Reportes ──────────────────────────────────────────────────────
        if Reporte.objects.count() < 100:
            bulk = [
                Reporte(
                    id=uuid.uuid4(),
                    nombre=f'Reporte {i}',
                    tipo=random.choice(TIPOS_REPORTE),
                    proyecto_id=uuid.uuid4(),
                    empresa_id=uuid.uuid4(),
                    periodo_inicio=INICIO_PERIODO,
                    periodo_fin=HOY,
                    datos={},
                )
                for i in range(1, 1001)
            ]
            Reporte.objects.bulk_create(bulk)
            self.stdout.write('  +1000 reportes')

        # ── 3. EjecucionAnalisis ─────────────────────────────────────────────
        if EjecucionAnalisis.objects.count() < 1000:
            analisis_ids = list(Analisis.objects.values_list('id', flat=True))
            if analisis_ids:
                estados = ['COMPLETADO', 'EN_PROCESO', 'PENDIENTE']
                bulk = [
                    EjecucionAnalisis(
                        id=uuid.uuid4(),
                        analisis_id=random.choice(analisis_ids),
                        estado=random.choices(estados, weights=[60, 20, 20])[0],
                        celery_task_id=f'task-{random.randint(1, 10000)}',
                        duracion_ms=random.randint(10, 5000),
                        resultado={},
                    )
                    for _ in range(5000)
                ]
                EjecucionAnalisis.objects.bulk_create(bulk)
                self.stdout.write('  +5000 ejecuciones_analisis')

        # ── 4. EventoEntrante ────────────────────────────────────────────────
        if EventoEntrante.objects.count() < 1000:
            procesado_vals = [True, False]
            bulk = [
                EventoEntrante(
                    id=uuid.uuid4(),
                    evento_id=f'evt-{uuid.uuid4()}',
                    tipo_evento=random.choice(TIPOS_EVENTO),
                    payload={
                        'source': 'seed',
                        'batch_size': random.randint(1, 50),
                    },
                    procesado=random.choice(procesado_vals),
                )
                for _ in range(10000)
            ]
            EventoEntrante.objects.bulk_create(bulk)
            self.stdout.write('  +10000 eventos_entrantes')

        self.stdout.write(self.style.SUCCESS('Reportes seed data ready.'))
