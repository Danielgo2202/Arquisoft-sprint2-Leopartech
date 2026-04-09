from rest_framework import serializers
from .models import Empresa, Proyecto, CuentaCloudRef, Presupuesto


class PresupuestoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Presupuesto
        fields = ['monto_mensual', 'moneda', 'alerta_porcentaje']


class PresupuestoInputSerializer(serializers.Serializer):
    monto_mensual = serializers.DecimalField(max_digits=15, decimal_places=2)
    moneda = serializers.CharField(max_length=3, default='USD')
    alerta_porcentaje = serializers.IntegerField(min_value=1, max_value=100, default=80)


class ProyectoCreateSerializer(serializers.Serializer):
    nombre = serializers.CharField(max_length=255)
    descripcion = serializers.CharField(required=False, default='', allow_blank=True)
    empresa_id = serializers.UUIDField()
    cuentas_cloud = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        error_messages={
            'min_length': 'Se requiere al menos una cuenta cloud activa (architecture.md §5.1).'
        }
    )
    presupuesto = PresupuestoInputSerializer(required=False)

    def validate_cuentas_cloud(self, value):
        if len(value) != len(set(str(v) for v in value)):
            raise serializers.ValidationError("No se permiten cuentas cloud duplicadas.")
        return value


class ProyectoResponseSerializer(serializers.ModelSerializer):
    empresa_id = serializers.UUIDField(source='empresa.id', read_only=True)
    empresa_nombre = serializers.CharField(source='empresa.nombre', read_only=True)
    cuentas_cloud = serializers.SerializerMethodField()
    presupuesto = PresupuestoSerializer(read_only=True)

    class Meta:
        model = Proyecto
        fields = [
            'id', 'nombre', 'descripcion', 'estado',
            'empresa_id', 'empresa_nombre',
            'cuentas_cloud', 'presupuesto', 'creado_en',
        ]
        read_only_fields = fields

    def get_cuentas_cloud(self, obj):
        return [str(c.cuenta_cloud_id) for c in obj.cuentas_cloud.select_related()]


class EmpresaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Empresa
        fields = ['id', 'nombre', 'nit', 'activa', 'creada_en']
        read_only_fields = ['id', 'creada_en']
