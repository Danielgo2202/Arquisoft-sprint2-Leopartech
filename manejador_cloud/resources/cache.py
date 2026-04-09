import logging
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

RECURSO_CACHE_TTL = getattr(settings, 'RECURSO_CACHE_TTL', 600)
CUENTA_CLOUD_CACHE_TTL = getattr(settings, 'CUENTA_CLOUD_CACHE_TTL', 300)
PROVEEDOR_CACHE_TTL = getattr(settings, 'PROVEEDOR_CACHE_TTL', 3600)


class CuentaCloudCache:
    """
    Caches CuentaCloud validation and detail data.
    Written here by Resource Service; read by Project Service (different Redis DB).
    Key pattern: cuenta_cloud:{id}:activa  → bool
                 cuenta_cloud:{id}:detail  → dict
    """
    KEY_VALIDATION = 'cuenta_cloud:{id}:activa'
    KEY_DETAIL = 'cuenta_cloud:{id}:detail'

    @classmethod
    def set_validation(cls, cuenta_id: str, is_active: bool):
        try:
            cache.set(
                cls.KEY_VALIDATION.format(id=cuenta_id),
                is_active,
                CUENTA_CLOUD_CACHE_TTL,
            )
        except Exception as exc:
            logger.warning("Redis set validation error for %s: %s", cuenta_id, exc)

    @classmethod
    def get_validation(cls, cuenta_id: str) -> bool | None:
        try:
            return cache.get(cls.KEY_VALIDATION.format(id=cuenta_id))
        except Exception as exc:
            logger.warning("Redis get validation error for %s: %s", cuenta_id, exc)
            return None

    @classmethod
    def set_detail(cls, cuenta_id: str, data: dict):
        try:
            cache.set(cls.KEY_DETAIL.format(id=cuenta_id), data, CUENTA_CLOUD_CACHE_TTL)
        except Exception as exc:
            logger.warning("Redis set detail error for %s: %s", cuenta_id, exc)

    @classmethod
    def get_detail(cls, cuenta_id: str) -> dict | None:
        try:
            return cache.get(cls.KEY_DETAIL.format(id=cuenta_id))
        except Exception as exc:
            logger.warning("Redis get detail error for %s: %s", cuenta_id, exc)
            return None

    @classmethod
    def invalidate(cls, cuenta_id: str):
        try:
            cache.delete_many([
                cls.KEY_VALIDATION.format(id=cuenta_id),
                cls.KEY_DETAIL.format(id=cuenta_id),
            ])
        except Exception as exc:
            logger.warning("Redis invalidate error for %s: %s", cuenta_id, exc)


class RecursoCloudCache:
    """
    Caches individual RecursoCloud details and list by account.
    Optimized for read-heavy operations (architecture.md §2.2 Manejador de Cloud).
    Key pattern: recurso:{id}               → dict
                 recursos_lista:{cuenta_id} → list[dict]
    """
    KEY_DETAIL = 'recurso:{id}'
    KEY_LIST = 'recursos_lista:{cuenta_id}'

    @classmethod
    def get_detail(cls, recurso_id: str) -> dict | None:
        try:
            return cache.get(cls.KEY_DETAIL.format(id=recurso_id))
        except Exception as exc:
            logger.warning("Redis get recurso error for %s: %s", recurso_id, exc)
            return None

    @classmethod
    def set_detail(cls, recurso_id: str, data: dict):
        try:
            cache.set(cls.KEY_DETAIL.format(id=recurso_id), data, RECURSO_CACHE_TTL)
        except Exception as exc:
            logger.warning("Redis set recurso error for %s: %s", recurso_id, exc)

    @classmethod
    def get_list(cls, cuenta_id: str) -> list | None:
        try:
            return cache.get(cls.KEY_LIST.format(cuenta_id=cuenta_id))
        except Exception as exc:
            logger.warning("Redis get list error for cuenta %s: %s", cuenta_id, exc)
            return None

    @classmethod
    def set_list(cls, cuenta_id: str, data: list):
        try:
            cache.set(cls.KEY_LIST.format(cuenta_id=cuenta_id), data, RECURSO_CACHE_TTL)
        except Exception as exc:
            logger.warning("Redis set list error for cuenta %s: %s", cuenta_id, exc)

    @classmethod
    def invalidate_detail(cls, recurso_id: str):
        try:
            cache.delete(cls.KEY_DETAIL.format(id=recurso_id))
        except Exception as exc:
            logger.warning("Redis invalidate recurso error for %s: %s", recurso_id, exc)

    @classmethod
    def invalidate_list(cls, cuenta_id: str):
        try:
            cache.delete(cls.KEY_LIST.format(cuenta_id=cuenta_id))
        except Exception as exc:
            logger.warning("Redis invalidate list error for cuenta %s: %s", cuenta_id, exc)
