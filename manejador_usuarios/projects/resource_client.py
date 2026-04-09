import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class ResourceServiceClient:
    """
    HTTP client for Resource Service (Manejador de Cloud).
    Used as fallback when Redis cache misses during CuentaCloud validation.
    Fail-open policy: if Resource Service is unreachable, validation passes
    to avoid blocking project creation (availability over strict consistency).
    """

    BASE_URL: str = settings.RESOURCE_SERVICE_URL
    TIMEOUT: int = settings.RESOURCE_SERVICE_TIMEOUT

    @classmethod
    def validate_cuenta_cloud(cls, cuenta_cloud_id: str) -> bool:
        """
        Calls GET /cloud-accounts/{id}/validate on the Resource Service.
        Returns True if account exists and is active, False if not found/inactive.
        Returns True (fail-open) on connection errors or timeouts.
        """
        url = f"{cls.BASE_URL}/cloud-accounts/{cuenta_cloud_id}/validate"
        try:
            response = requests.get(url, timeout=cls.TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                return bool(data.get('activa', False))
            if response.status_code == 404:
                logger.warning("CuentaCloud %s not found in Resource Service", cuenta_cloud_id)
                return False
            logger.warning(
                "Resource Service returned %s for CuentaCloud %s",
                response.status_code, cuenta_cloud_id,
            )
            return True  # fail-open
        except requests.exceptions.ConnectionError:
            logger.warning(
                "Resource Service unreachable while validating CuentaCloud %s. Failing open.",
                cuenta_cloud_id,
            )
            return True
        except requests.exceptions.Timeout:
            logger.warning(
                "Resource Service timeout for CuentaCloud %s. Failing open.",
                cuenta_cloud_id,
            )
            return True
        except Exception:
            logger.exception("Unexpected error validating CuentaCloud %s", cuenta_cloud_id)
            return True
