from django.urls import path
from . import views

urlpatterns = [
    path('projects', views.ProyectoCreateView.as_view(), name='proyecto-create'),
    path('health', views.HealthCheckView.as_view(), name='health-check'),
]
