import logging
import requests as http_requests
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import connection, OperationalError
from django.conf import settings

from .models import EventoSeguridad, RegistroAuditoria
from .serializers import EventoSeguridadSerializer

logger = logging.getLogger(__name__)


def _get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def _validate_token_via_auth_service(token):
    """Validate token by calling manejador_autenticacion /auth/validate."""
    try:
        resp = http_requests.get(
            f'{settings.AUTH_SERVICE_URL}/auth/validate',
            headers={'Authorization': f'Bearer {token}'},
            timeout=settings.AUTH_SERVICE_TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except http_requests.RequestException as e:
        logger.warning("Auth service unreachable: %s", e)
        # Fallback: validate locally if JWT secret is available
        return _validate_token_locally(token)


def _validate_token_locally(token):
    """Local JWT validation fallback (same secret as manejador_autenticacion)."""
    try:
        import jwt
        payload = jwt.decode(
            token,
            settings.LOCAL_JWT_SECRET,
            algorithms=['HS256'],
        )
        if payload.get('type') != 'access':
            return None
        return {
            'user_id': payload.get('sub'),
            'email': payload.get('email', ''),
            'empresa_id': payload.get('empresa_id'),
            'valid': True,
        }
    except Exception as e:
        logger.warning("Local token fallback failed: %s", e)
        return None


def _log_event(tipo, endpoint, metodo, ip, empresa_id_token=None, empresa_id_recurso=None, evidencia=None):
    """Create EventoSeguridad + RegistroAuditoria."""
    try:
        evento = EventoSeguridad.objects.create(
            tipo=tipo,
            endpoint=endpoint,
            metodo=metodo,
            ip_origen=ip,
            empresa_id_token=empresa_id_token,
            empresa_id_recurso=empresa_id_recurso,
            bloqueado=True,
            evidencia=evidencia or {},
        )
        RegistroAuditoria.objects.create(
            evento=evento,
            descripcion=(
                f"Acceso bloqueado: tipo={tipo}, endpoint={endpoint}, "
                f"ip={ip}, tenant_token={empresa_id_token}, tenant_recurso={empresa_id_recurso}"
            ),
        )
    except Exception:
        logger.exception("Failed to log security event")


class VerifyView(APIView):
    """
    POST /security/verify

    Validates the Bearer token and optionally checks tenant isolation.
    Body (all optional):
        empresa_id_recurso: UUID — if provided, checks cross-tenant access
        endpoint: str — for audit logging
        method: str — for audit logging

    Returns 200 with tenant info on success, 403 on any violation.
    """

    def post(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            _log_event(
                tipo=EventoSeguridad.Tipo.ACCESO_NO_AUTORIZADO,
                endpoint=request.data.get('endpoint', '/unknown'),
                metodo=request.data.get('method', request.method),
                ip=_get_client_ip(request),
                evidencia={'reason': 'missing_bearer_token'},
            )
            return Response(
                {'error': 'Token de autenticación requerido.', 'bloqueado': True},
                status=status.HTTP_403_FORBIDDEN,
            )

        token = auth_header[7:]
        user_info = _validate_token_via_auth_service(token)

        if user_info is None:
            _log_event(
                tipo=EventoSeguridad.Tipo.TOKEN_INVALIDO,
                endpoint=request.data.get('endpoint', '/unknown'),
                metodo=request.data.get('method', request.method),
                ip=_get_client_ip(request),
                evidencia={'reason': 'invalid_or_expired_token'},
            )
            return Response(
                {'error': 'Token inválido o expirado.', 'bloqueado': True},
                status=status.HTTP_403_FORBIDDEN,
            )

        empresa_id_token = user_info.get('empresa_id')
        empresa_id_recurso = request.data.get('empresa_id_recurso')

        # Cross-tenant check: only if empresa_id_recurso is provided
        if empresa_id_recurso and str(empresa_id_token) != str(empresa_id_recurso):
            _log_event(
                tipo=EventoSeguridad.Tipo.ACCESO_CRUZADO_TENANT,
                endpoint=request.data.get('endpoint', '/unknown'),
                metodo=request.data.get('method', request.method),
                ip=_get_client_ip(request),
                empresa_id_token=empresa_id_token,
                empresa_id_recurso=empresa_id_recurso,
                evidencia={
                    'reason': 'cross_tenant_access',
                    'token_empresa': str(empresa_id_token),
                    'resource_empresa': str(empresa_id_recurso),
                },
            )
            return Response(
                {
                    'error': 'Acceso denegado: empresa del token no coincide con el recurso solicitado.',
                    'bloqueado': True,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(
            {
                'valid': True,
                'empresa_id': empresa_id_token,
                'user_id': user_info.get('user_id'),
                'email': user_info.get('email', ''),
            },
            status=status.HTTP_200_OK,
        )


class AuditLogListView(APIView):
    """
    GET /security/audit-log
    Returns security events filtered by the requesting tenant's empresa_id.
    Requires valid Bearer token.
    """

    def get(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return Response({'error': 'Token requerido.'}, status=status.HTTP_403_FORBIDDEN)

        token = auth_header[7:]
        user_info = _validate_token_via_auth_service(token)
        if user_info is None:
            return Response({'error': 'Token inválido.'}, status=status.HTTP_403_FORBIDDEN)

        empresa_id = user_info.get('empresa_id')
        qs = EventoSeguridad.objects.filter(empresa_id_token=empresa_id).order_by('-creado_en')[:100]
        serializer = EventoSeguridadSerializer(qs, many=True)
        return Response(serializer.data)


class AuditLogDetailView(APIView):
    """GET /security/audit-log/<id>"""

    def get(self, request, evento_id):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return Response({'error': 'Token requerido.'}, status=status.HTTP_403_FORBIDDEN)

        token = auth_header[7:]
        user_info = _validate_token_via_auth_service(token)
        if user_info is None:
            return Response({'error': 'Token inválido.'}, status=status.HTTP_403_FORBIDDEN)

        empresa_id = user_info.get('empresa_id')
        try:
            evento = EventoSeguridad.objects.get(id=evento_id, empresa_id_token=empresa_id)
        except EventoSeguridad.DoesNotExist:
            return Response({'error': 'Evento no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = EventoSeguridadSerializer(evento)
        return Response(serializer.data)


class HealthCheckView(APIView):
    """GET /health"""

    def get(self, request):
        checks = {}
        try:
            connection.ensure_connection()
            checks['database'] = 'ok'
        except OperationalError:
            checks['database'] = 'error'

        all_ok = checks.get('database') == 'ok'
        return Response(
            {
                'service': 'manejador_seguridad',
                'status': 'healthy' if all_ok else 'degraded',
                'checks': checks,
            },
            status=status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        )
