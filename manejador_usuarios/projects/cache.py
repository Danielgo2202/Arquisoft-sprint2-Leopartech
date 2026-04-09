import logging
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

CUENTA_CLOUD_CACHE_TTL = getattr(settings, 'CUENTA_CLOUD_CACHE_TTL', 300)
EMPRESA_CACHE_TTL = getattr(settings, 'EMPRESA_CACHE_TTL', 300)


class CuentaCloudCache:
    """
    Redis cache for CuentaCloud validation results.
    Key: cuenta_cloud:{id}:activa → bool
    TTL: 300 seconds (5 min). Used to minimize calls to Resource Service.
    """
    KEY_PREFIX = 'cuenta_cloud'

    @classmethod
    def _key(cls, cuenta_id: str) -> str:
        return f"{cls.KEY_PREFIX}:{cuenta_id}:activa"

    @classmethod
    def get_validation(cls, cuenta_id) -> bool | None:
        """Returns True/False if cached, None if cache miss."""
        try:
            value = cache.get(cls._key(str(cuenta_id)))
            return value
        except Exception as exc:
            logger.warning("Redis get error for cuenta_cloud %s: %s", cuenta_id, exc)
            return None

    @classmethod
    def set_validation(cls, cuenta_id, is_active: bool):
        try:
            cache.set(cls._key(str(cuenta_id)), is_active, CUENTA_CLOUD_CACHE_TTL)
        except Exception as exc:
            logger.warning("Redis set error for cuenta_cloud %s: %s", cuenta_id, exc)

    @classmethod
    def invalidate(cls, cuenta_id):
        try:
            cache.delete(cls._key(str(cuenta_id)))
        except Exception as exc:
            logger.warning("Redis delete error for cuenta_cloud %s: %s", cuenta_id, exc)


class EmpresaCache:
    """
    Redis cache for Empresa active-status lookups.
    Key: empresa:{id} → dict with {activa, nombre}
    TTL: 300 seconds (5 min).
    """
    KEY_PREFIX = 'empresa'

    @classmethod
    def _key(cls, empresa_id: str) -> str:
        return f"{cls.KEY_PREFIX}:{empresa_id}"

    @classmethod
    def get(cls, empresa_id) -> dict | None:
        try:
            return cache.get(cls._key(str(empresa_id)))
        except Exception as exc:
            logger.warning("Redis get error for empresa %s: %s", empresa_id, exc)
            return None

    @classmethod
    def set(cls, empresa_id, data: dict):
        try:
            cache.set(cls._key(str(empresa_id)), data, EMPRESA_CACHE_TTL)
        except Exception as exc:
            logger.warning("Redis set error for empresa %s: %s", empresa_id, exc)

    @classmethod
    def invalidate(cls, empresa_id):
        try:
            cache.delete(cls._key(str(empresa_id)))
        except Exception as exc:
            logger.warning("Redis delete error for empresa %s: %s", empresa_id, exc)
