from django.urls import path
from . import views

urlpatterns = [
    path('security/verify', views.VerifyView.as_view(), name='security-verify'),
    path('security/audit-log', views.AuditLogListView.as_view(), name='audit-log-list'),
    path('security/audit-log/<uuid:evento_id>', views.AuditLogDetailView.as_view(), name='audit-log-detail'),
    path('health', views.HealthCheckView.as_view(), name='health-check'),
]
