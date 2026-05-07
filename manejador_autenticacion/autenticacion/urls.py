from django.urls import path
from . import views

urlpatterns = [
    path('auth/login', views.LoginView.as_view(), name='auth-login'),
    path('auth/refresh', views.RefreshView.as_view(), name='auth-refresh'),
    path('auth/logout', views.LogoutView.as_view(), name='auth-logout'),
    path('auth/validate', views.ValidateView.as_view(), name='auth-validate'),
    path('health', views.HealthCheckView.as_view(), name='health-check'),
]
