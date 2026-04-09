# Infraestructura local - Arquitectura de Experimentos

Este módulo contiene la infraestructura local para soportar los experimentos de:

- ASR16 → Latencia
- ASR17 → Escalabilidad

## Servicios disponibles

### Bases de datos PostgreSQL

| Servicio | Puerto | Base de datos |
|---|---:|---|
| Projects DB | 5432 | cloud_projects_db |
| Reports DB | 5433 | reports_db |
| Users Company DB | 5434 | users_company_db |

### Otros servicios

| Servicio | Puerto |
|---|---:|
| Redis | 6379 |
| RabbitMQ | 5672 |
| RabbitMQ UI | 15672 |

---

## Levantar entorno

```bash
docker compose up -d

docker ps

## Credenciales PostgreSQL

usuario = admin
contraseña = admin123
host_local = 127.0.0.1


Para la correcta conexión de los microservicios, asegúrate de configurar el archivo `settings.py` con los siguientes diccionarios de conexión:

### 1. Projects DB (Principal)
```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "cloud_projects_db",
        "USER": "admin",
        "PASSWORD": "admin123",
        "HOST": "127.0.0.1",
        "PORT": "5432",
    }
}
2. Reports DB
Python
DATABASES["reports"] = {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": "reports_db",
    "USER": "admin",
    "PASSWORD": "admin123",
    "HOST": "127.0.0.1",
    "PORT": "5433",
}
3. Users Company DB
Python
DATABASES["users_company"] = {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": "users_company_db",
    "USER": "admin",
    "PASSWORD": "admin123",
    "HOST": "127.0.0.1",
    "PORT": "5434",
}


🌱 Semillas Ejecutadas (Data Population)
Se ha poblado el sistema con los siguientes volúmenes de datos para las pruebas de carga:

Proyectos: 5,000 registros.

Recursos Cloud: 20,000 registros.

Reportes / Jobs: 1,000 registros.

Empleados / Presupuestos: Cargados exitosamente.


⚠️ MUY IMPORTANTE → Compatibilidad con Django
Para que Django pueda comunicarse con PostgreSQL, es obligatorio incluir el driver en el archivo requirements.txt.

Debe estar presente la siguiente dependencia:

Plaintext
psycopg2-binary

Nota: Esto es clave. Si no se incluye la versión -binary, Django no podrá conectar con las bases de datos en entornos de desarrollo.
