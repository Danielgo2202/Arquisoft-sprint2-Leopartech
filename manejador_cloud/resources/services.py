import logging
from django.db import transaction

from .models import ProveedorCloud, CuentaCloud, RecursoCloud, MetricaConsumo
from .cache import CuentaCloudCache, RecursoCloudCache
from .serializers import (
    CuentaCloudSerializer, RecursoCloudSerializer, MetricaConsumoSerializer
)

logger = logging.getLogger(__name__)


class CuentaCloudService:
    """
    Business logic for CuentaCloud management and validation.
    Implements Redis-first read for the ≤100 ms latency requirement.
    """

    @staticmethod
    def get_by_id(cuenta_id: str) -> CuentaCloud | None:
        cached = CuentaCloudCache.get_detail(cuenta_id)
        if cached:
            return cached

        try:
            cuenta = (
                CuentaCloud.objects
                .select_related('proveedor')
                .get(id=cuenta_id)
            )
        except CuentaCloud.DoesNotExist:
            return None

        data = CuentaCloudSerializer(cuenta).data
        CuentaCloudCache.set_detail(cuenta_id, data)
        return cuenta

    @staticmethod
    def validate(cuenta_id: str) -> dict:
        """
        Returns validation dict used by Project Service.
        Cached in Redis for fast cross-service validation.
        """
        cached = CuentaCloudCache.get_validation(cuenta_id)
        if cached is not None:
            return {'cuenta_cloud_id': cuenta_id, 'activa': cached}

        try:
            cuenta = CuentaCloud.objects.select_related('proveedor').get(id=cuenta_id)
            result = {
                'cuenta_cloud_id': str(cuenta.id),
                'activa': cuenta.activa,
                'proveedor_tipo': cuenta.proveedor.tipo,
            }
            CuentaCloudCache.set_validation(cuenta_id, cuenta.activa)
        except CuentaCloud.DoesNotExist:
            result = {'cuenta_cloud_id': cuenta_id, 'activa': False}
            CuentaCloudCache.set_validation(cuenta_id, False)

        return result

    @staticmethod
    def create(data: dict) -> CuentaCloud:
        with transaction.atomic():
            cuenta = CuentaCloud.objects.create(**data)

        # Warm up cache after creation
        validation = {
            'cuenta_cloud_id': str(cuenta.id),
            'activa': cuenta.activa,
            'proveedor_tipo': cuenta.proveedor.tipo,
        }
        CuentaCloudCache.set_validation(str(cuenta.id), cuenta.activa)
        CuentaCloudCache.set_detail(str(cuenta.id), CuentaCloudSerializer(cuenta).data)
        logger.info("CuentaCloud created and cached: %s", cuenta.id)
        return cuenta

    @staticmethod
    def deactivate(cuenta_id: str) -> bool:
        updated = CuentaCloud.objects.filter(id=cuenta_id).update(activa=False)
        if updated:
            CuentaCloudCache.invalidate(cuenta_id)
            logger.info("CuentaCloud deactivated and cache invalidated: %s", cuenta_id)
        return bool(updated)


class RecursoCloudService:
    """
    Business logic for RecursoCloud management.
    Read-heavy: Redis-first for list and detail lookups.
    """

    @staticmethod
    def list_by_cuenta(cuenta_id: str) -> list:
        cached = RecursoCloudCache.get_list(cuenta_id)
        if cached is not None:
            return cached

        recursos = (
            RecursoCloud.objects
            .filter(cuenta_id=cuenta_id, activo=True)
            .select_related('cuenta__proveedor')
            .order_by('tipo', 'nombre')
        )
        data = RecursoCloudSerializer(recursos, many=True).data
        RecursoCloudCache.set_list(cuenta_id, data)
        return data

    @staticmethod
    def get_by_id(recurso_id: str) -> RecursoCloud | None:
        cached = RecursoCloudCache.get_detail(recurso_id)
        if cached:
            return cached

        try:
            recurso = (
                RecursoCloud.objects
                .select_related('cuenta__proveedor')
                .get(id=recurso_id)
            )
        except RecursoCloud.DoesNotExist:
            return None

        data = RecursoCloudSerializer(recurso).data
        RecursoCloudCache.set_detail(recurso_id, data)
        return recurso

    @staticmethod
    def create(data: dict) -> RecursoCloud:
        with transaction.atomic():
            recurso = RecursoCloud.objects.create(**data)

        # Invalidate list cache for the account
        RecursoCloudCache.invalidate_list(str(recurso.cuenta_id))
        logger.info("RecursoCloud created: %s for cuenta %s", recurso.id, recurso.cuenta_id)
        return recurso

    @staticmethod
    def get_metricas_by_recurso(recurso_id: str) -> list:
        metricas = (
            MetricaConsumo.objects
            .filter(recurso_id=recurso_id)
            .order_by('-periodo_inicio')
            .select_related('recurso')
        )
        return MetricaConsumoSerializer(metricas, many=True).data
