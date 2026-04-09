from django.urls import path
from . import views

urlpatterns = [
    path('cloud-accounts', views.CuentaCloudListCreateView.as_view(), name='cuenta-cloud-list-create'),
    path('cloud-accounts/<uuid:cuenta_id>', views.CuentaCloudDetailView.as_view(), name='cuenta-cloud-detail'),
    path('cloud-accounts/<uuid:cuenta_id>/validate', views.CuentaCloudValidateView.as_view(), name='cuenta-cloud-validate'),
    path('resources', views.RecursoCloudListCreateView.as_view(), name='recurso-cloud-list-create'),
    path('resources/<uuid:recurso_id>', views.RecursoCloudDetailView.as_view(), name='recurso-cloud-detail'),
    path('metrics', views.MetricaConsumoCreateView.as_view(), name='metrica-consumo-create'),
    path('health', views.HealthCheckView.as_view(), name='health-check'),
]
