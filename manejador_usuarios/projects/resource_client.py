import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class CloudServiceUnavailable(Exception):
    """Raised when manejador_cloud is unreachable or times out."""


class ResourceServiceClient:
    """
    HTTP client for Resource Service (Manejador de Cloud).
    Used as fallback when Redis cache misses during CuentaCloud validation.
    Fail-closed: if Resource Service is unreachable, raises CloudServiceUnavailable
    so the caller can return HTTP 503 (ASR16 requirement: do NOT fail open).
    """

    BASE_URL: str = settings.RESOURCE_SERVICE_URL
    TIMEOUT: int = settings.RESOURCE_SERVICE_TIMEOUT

    @classmethod
    def validate_cuenta_cloud(cls, cuenta_cloud_id: str) -> bool:
        """
        Calls GET /cloud-accounts/{id}/validate on the Resource Service.
        Returns True if account exists and is active, False if not found/inactive.
        Raises CloudServiceUnavailable on connection errors or timeouts.
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
            return False
        except requests.exceptions.ConnectionError as exc:
            logger.error(
                "Resource Service unreachable while validating CuentaCloud %s: %s",
                cuenta_cloud_id, exc,
            )
            raise CloudServiceUnavailable(
                f"Resource Service unreachable: {exc}"
            ) from exc
        except requests.exceptions.Timeout as exc:
            logger.error(
                "Resource Service timeout for CuentaCloud %s", cuenta_cloud_id
            )
            raise CloudServiceUnavailable(
                "Resource Service did not respond in time."
            ) from exc
        except Exception:
            logger.exception("Unexpected error validating CuentaCloud %s", cuenta_cloud_id)
            raise CloudServiceUnavailable("Unexpected error contacting Resource Service.")
