import logging
from django.db import transaction

from .models import Empresa, Proyecto, CuentaCloudRef, Presupuesto
from .cache import CuentaCloudCache, EmpresaCache
from .publisher import ProyectoEventPublisher
from .resource_client import ResourceServiceClient

logger = logging.getLogger(__name__)


class ProyectoService:
    """
    Business logic for Proyecto creation.

    Flow (architecture.md §4 - Experiment B Latency):
    1. Validate Empresa  → Redis cache → DB fallback
    2. Validate CuentaCloud(s) → Redis cache → Resource Service HTTP fallback
    3. Persist Proyecto + CuentaCloudRef(s) + Presupuesto in a single transaction
    4. Publish proyecto_creado event NON-BLOCKING (background thread)
    5. Return Proyecto object → view returns HTTP 201
    """

    @staticmethod
    def crear_proyecto(data: dict) -> Proyecto:
        empresa_id = data['empresa_id']
        cuenta_cloud_ids = data['cuentas_cloud']

        # Step 1: Validate Empresa
        empresa = ProyectoService._validar_empresa(str(empresa_id))

        # Step 2: Validate every CuentaCloud (at least 1 required per architecture §5.1)
        for cuenta_id in cuenta_cloud_ids:
            ProyectoService._validar_cuenta_cloud(str(cuenta_id))

        # Step 3: Persist
        with transaction.atomic():
            proyecto = Proyecto.objects.create(
                nombre=data['nombre'],
                descripcion=data.get('descripcion', ''),
                empresa=empresa,
            )

            CuentaCloudRef.objects.bulk_create([
                CuentaCloudRef(proyecto=proyecto, cuenta_cloud_id=cid)
                for cid in cuenta_cloud_ids
            ])

            presupuesto_data = data.get('presupuesto')
            if presupuesto_data:
                Presupuesto.objects.create(proyecto=proyecto, **presupuesto_data)

        # Step 4: Publish event (non-blocking)
        ProyectoEventPublisher.publish_proyecto_creado(proyecto)

        logger.info(
            "Proyecto creado",
            extra={
                'proyecto_id': str(proyecto.id),
                'empresa_id': str(empresa.id),
                'cuentas_count': len(cuenta_cloud_ids),
            }
        )

        # Step 5: Return (view sends HTTP 201)
        return proyecto

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validar_empresa(empresa_id: str) -> Empresa:
        """Redis-first lookup, DB fallback, then cache result."""
        cached = EmpresaCache.get(empresa_id)
        if cached is not None:
            if not cached.get('activa', False):
                raise ValueError(f"Empresa {empresa_id} no está activa.")
            try:
                return Empresa.objects.get(id=empresa_id)
            except Empresa.DoesNotExist:
                raise ValueError(f"Empresa {empresa_id} no encontrada.")

        try:
            empresa = Empresa.objects.get(id=empresa_id)
        except Empresa.DoesNotExist:
            raise ValueError(f"Empresa {empresa_id} no encontrada.")

        if not empresa.activa:
            raise ValueError(f"Empresa {empresa_id} no está activa.")

        EmpresaCache.set(empresa_id, {'activa': empresa.activa, 'nombre': empresa.nombre})
        return empresa

    @staticmethod
    def _validar_cuenta_cloud(cuenta_id: str) -> None:
        """
        Redis-first validation:
        - Cache hit (True)  → pass
        - Cache hit (False) → raise ValueError
        - Cache miss        → call Resource Service, cache result, then validate
        """
        cached = CuentaCloudCache.get_validation(cuenta_id)

        if cached is True:
            return
        if cached is False:
            raise ValueError(
                f"Cuenta cloud {cuenta_id} no está activa o no existe en Resource Service."
            )

        # Cache miss → HTTP call to Resource Service
        is_active = ResourceServiceClient.validate_cuenta_cloud(cuenta_id)
        CuentaCloudCache.set_validation(cuenta_id, is_active)

        if not is_active:
            raise ValueError(
                f"Cuenta cloud {cuenta_id} no está activa o no existe en Resource Service."
            )
