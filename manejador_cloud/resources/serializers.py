from rest_framework import serializers
from .models import ProveedorCloud, CuentaCloud, RecursoCloud, MetricaConsumo


class ProveedorCloudSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProveedorCloud
        fields = ['id', 'nombre', 'tipo', 'activo', 'creado_en']
        read_only_fields = ['id', 'creado_en']


class CuentaCloudSerializer(serializers.ModelSerializer):
    proveedor_tipo = serializers.CharField(source='proveedor.tipo', read_only=True)
    proveedor_nombre = serializers.CharField(source='proveedor.nombre', read_only=True)

    class Meta:
        model = CuentaCloud
        fields = [
            'id', 'nombre', 'proveedor', 'proveedor_tipo', 'proveedor_nombre',
            'proyecto_id', 'account_external_id', 'region',
            'activa', 'creada_en', 'actualizada_en',
        ]
        read_only_fields = ['id', 'creada_en', 'actualizada_en']


class CuentaCloudCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CuentaCloud
        fields = ['nombre', 'proveedor', 'proyecto_id', 'account_external_id', 'region']


class CuentaCloudValidationSerializer(serializers.Serializer):
    cuenta_cloud_id = serializers.UUIDField(read_only=True)
    activa = serializers.BooleanField(read_only=True)
    proveedor_tipo = serializers.CharField(read_only=True)


class RecursoCloudSerializer(serializers.ModelSerializer):
    cuenta_nombre = serializers.CharField(source='cuenta.nombre', read_only=True)
    proveedor_tipo = serializers.CharField(source='cuenta.proveedor.tipo', read_only=True)

    class Meta:
        model = RecursoCloud
        fields = [
            'id', 'nombre', 'tipo', 'region',
            'resource_external_id', 'etiquetas', 'activo',
            'cuenta', 'cuenta_nombre', 'proveedor_tipo',
            'creado_en', 'actualizado_en',
        ]
        read_only_fields = ['id', 'creado_en', 'actualizado_en']


class RecursoCloudCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecursoCloud
        fields = ['nombre', 'tipo', 'region', 'resource_external_id', 'etiquetas', 'cuenta']


class MetricaConsumoSerializer(serializers.ModelSerializer):
    recurso_nombre = serializers.CharField(source='recurso.nombre', read_only=True)

    class Meta:
        model = MetricaConsumo
        fields = [
            'id', 'recurso', 'recurso_nombre', 'tipo_metrica',
            'periodo_inicio', 'periodo_fin', 'valor', 'costo', 'moneda',
            'registrada_en',
        ]
        read_only_fields = ['id', 'registrada_en']


class MetricaConsumoCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MetricaConsumo
        fields = ['recurso', 'tipo_metrica', 'periodo_inicio', 'periodo_fin',
                  'valor', 'costo', 'moneda']
