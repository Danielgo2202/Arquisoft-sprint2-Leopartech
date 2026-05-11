import uuid
from django.db import models
from django.contrib.auth.hashers import make_password, check_password as django_check_password


class UsuarioLocal(models.Model):
    """
    Local user for JWT authentication when Cognito is not configured.
    Used in docker compose (local dev) without AWS credentials.
    In production, users are managed in Amazon Cognito.
    """
    class Rol(models.TextChoices):
        ADMIN = 'ADMIN', 'Admin'
        MANAGER = 'MANAGER', 'Manager'
        ANALYST = 'ANALYST', 'Analyst'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255)
    empresa_id = models.UUIDField(db_index=True)
    rol = models.CharField(max_length=50, choices=Rol.choices, default=Rol.ANALYST)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'usuarios_locales'

    def set_password(self, raw_password):
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password):
        return django_check_password(raw_password, self.password_hash)

    def __str__(self):
        return self.email
