import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import connection, OperationalError

from .serializers import (
    CuentaCloudSerializer, CuentaCloudCreateSerializer,
    RecursoCloudSerializer, RecursoCloudCreateSerializer,
    MetricaConsumoCreateSerializer,
)
from .services import CuentaCloudService, RecursoCloudService

logger = logging.getLogger(__name__)


class CuentaCloudListCreateView(APIView):
    """GET /cloud-accounts  |  POST /cloud-accounts"""

    def get(self, request):
        from .models import CuentaCloud
        proyecto_id = request.query_params.get('proyecto_id')
        qs = CuentaCloud.objects.select_related('proveedor').filter(activa=True)
        if proyecto_id:
            qs = qs.filter(proyecto_id=proyecto_id)
        serializer = CuentaCloudSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = CuentaCloudCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            cuenta = CuentaCloudService.create(serializer.validated_data)
            return Response(CuentaCloudSerializer(cuenta).data, status=status.HTTP_201_CREATED)
        except Exception:
            logger.exception("Error creating CuentaCloud")
            return Response(
                {'error': 'Error interno del servidor.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CuentaCloudDetailView(APIView):
    """GET /cloud-accounts/{id}  |  DELETE /cloud-accounts/{id}"""

    def get(self, request, cuenta_id):
        result = CuentaCloudService.get_by_id(str(cuenta_id))
        if result is None:
            return Response({'error': 'CuentaCloud no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        if hasattr(result, 'pk'):
            return Response(CuentaCloudSerializer(result).data)
        return Response(result)  # from cache (already serialized dict)

    def delete(self, request, cuenta_id):
        deactivated = CuentaCloudService.deactivate(str(cuenta_id))
        if not deactivated:
            return Response({'error': 'CuentaCloud no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CuentaCloudValidateView(APIView):
    """
    GET /cloud-accounts/{id}/validate
    Called by Project Service to validate a CuentaCloud before project creation.
    Uses Redis cache for fast response (≤100 ms latency SLA).
    """

    def get(self, request, cuenta_id):
        result = CuentaCloudService.validate(str(cuenta_id))
        if not result.get('activa', False):
            return Response(result, status=status.HTTP_404_NOT_FOUND)
        return Response(result, status=status.HTTP_200_OK)


class RecursoCloudListCreateView(APIView):
    """GET /resources  |  POST /resources"""

    def get(self, request):
        cuenta_id = request.query_params.get('cuenta_id')
        if not cuenta_id:
            return Response(
                {'error': 'Se requiere el parámetro cuenta_id.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = RecursoCloudService.list_by_cuenta(cuenta_id)
        return Response(data)

    def post(self, request):
        serializer = RecursoCloudCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            recurso = RecursoCloudService.create(serializer.validated_data)
            return Response(RecursoCloudSerializer(recurso).data, status=status.HTTP_201_CREATED)
        except Exception:
            logger.exception("Error creating RecursoCloud")
            return Response(
                {'error': 'Error interno del servidor.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class RecursoCloudDetailView(APIView):
    """GET /resources/{id}"""

    def get(self, request, recurso_id):
        result = RecursoCloudService.get_by_id(str(recurso_id))
        if result is None:
            return Response({'error': 'RecursoCloud no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        if hasattr(result, 'pk'):
            return Response(RecursoCloudSerializer(result).data)
        return Response(result)


class MetricaConsumoCreateView(APIView):
    """POST /metrics"""

    def post(self, request):
        serializer = MetricaConsumoCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        metrica = serializer.save()
        return Response(MetricaConsumoCreateSerializer(metrica).data, status=status.HTTP_201_CREATED)


class HealthCheckView(APIView):
    """GET /health"""
    throttle_classes = []

    def get(self, request):
        checks = {}

        try:
            connection.ensure_connection()
            checks['database'] = 'ok'
        except OperationalError:
            checks['database'] = 'error'

        try:
            from django.core.cache import cache
            cache.set('_health', '1', 5)
            checks['redis'] = 'ok' if cache.get('_health') == '1' else 'error'
        except Exception:
            checks['redis'] = 'error'

        all_ok = all(v == 'ok' for v in checks.values())
        return Response(
            {
                'service': 'manejador_cloud',
                'status': 'healthy' if all_ok else 'degraded',
                'checks': checks,
            },
            status=status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        )
