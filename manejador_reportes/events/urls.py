from django.urls import path
from . import views

urlpatterns = [
    path('events/batch', views.EventoBatchView.as_view(), name='evento-batch'),
    path('analytics', views.AnalisisListView.as_view(), name='analisis-list'),
    path('reports', views.ReporteListView.as_view(), name='reporte-list'),
    path('health', views.HealthCheckView.as_view(), name='health-check'),
]
