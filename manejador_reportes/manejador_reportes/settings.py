import os
from pathlib import Path
from kombu import Exchange, Queue, binding

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'rest_framework',
    'events',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
]

ROOT_URLCONF = 'manejador_reportes.urls'
WSGI_APPLICATION = 'manejador_reportes.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'HOST': os.environ.get('DATABASE_HOST', 'localhost'),
        'PORT': os.environ.get('DATABASE_PORT', '5432'),
        'NAME': os.environ.get('DATABASE_NAME', 'reportes_db'),
        'USER': os.environ.get('DATABASE_USER', 'admin'),
        'PASSWORD': os.environ.get('DATABASE_PASSWORD', 'admin123'),
        'CONN_MAX_AGE': 60,
        'OPTIONS': {'connect_timeout': 10},
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://redis:6379/2'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'IGNORE_EXCEPTIONS': True,
        },
        'TIMEOUT': int(os.environ.get('REDIS_CACHE_TTL', '300')),
    }
}

# ── Celery ──────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = os.environ.get(
    'CELERY_BROKER_URL',
    'amqp://bite:bite_pass@rabbitmq:5672/bite_vhost',
)
CELERY_RESULT_BACKEND = os.environ.get(
    'CELERY_RESULT_BACKEND',
    'redis://redis:6379/3',
)
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_SOFT_TIME_LIMIT = int(os.environ.get('CELERY_TASK_SOFT_TIME_LIMIT', '120'))
CELERY_TASK_TIME_LIMIT = int(os.environ.get('CELERY_TASK_TIME_LIMIT', '180'))
CELERY_WORKER_CONCURRENCY = int(os.environ.get('CELERY_WORKER_CONCURRENCY', '4'))
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# ── RabbitMQ topic exchange – same exchange manejador_usuarios publishes to ──
# architecture.md §4.1 Scalability Experiment – bite_events topic exchange
#
# Single queue 'bite.eventos' bound to all routing-key patterns so that
# workers started without --queues (e.g. Terraform) use the default queue
# and still receive every event type.
_BITE_EXCHANGE = Exchange('bite_events', type='topic', durable=True)

CELERY_DEFAULT_QUEUE = 'bite.eventos'
CELERY_QUEUES = (
    Queue(
        'bite.eventos',
        bindings=[
            binding(_BITE_EXCHANGE, routing_key='evento.#'),
            binding(_BITE_EXCHANGE, routing_key='proyecto.*'),
            binding(_BITE_EXCHANGE, routing_key='analisis.*'),
            binding(_BITE_EXCHANGE, routing_key='reporte.*'),
        ],
        durable=True,
    ),
)

# All tasks route to bite.eventos on the bite_events exchange
CELERY_TASK_ROUTES = {
    'events.tasks.procesar_evento_batch': {
        'queue': 'bite.eventos',
        'exchange': 'bite_events',
        'routing_key': 'evento.batch',
    },
    'events.tasks.procesar_proyecto_creado': {
        'queue': 'bite.eventos',
        'exchange': 'bite_events',
        'routing_key': 'proyecto.creado',
    },
    'events.tasks.generar_reporte': {
        'queue': 'bite.eventos',
        'exchange': 'bite_events',
        'routing_key': 'reporte.solicitado',
    },
    'events.tasks.enviar_notificacion': {
        'queue': 'bite.eventos',
        'exchange': 'bite_events',
        'routing_key': 'evento.notificacion',
    },
    'events.tasks.ejecutar_analisis': {
        'queue': 'bite.eventos',
        'exchange': 'bite_events',
        'routing_key': 'analisis.ejecutar',
    },
}

# ── RabbitMQ (raw AMQP consumer) ───────────────────────────────────────────
RABBITMQ_URL = os.environ.get(
    'RABBITMQ_URL',
    'amqp://bite:bite_pass@rabbitmq:5672/bite_vhost',
)
RABBITMQ_EXCHANGE = os.environ.get('RABBITMQ_EXCHANGE', 'bite_events')
RABBITMQ_QUEUE_PROYECTOS = os.environ.get('RABBITMQ_QUEUE_PROYECTOS', 'bite.proyectos')
RABBITMQ_QUEUE_ANALISIS = os.environ.get('RABBITMQ_QUEUE_ANALISIS', 'bite.analisis')
RABBITMQ_QUEUE_REPORTES = os.environ.get('RABBITMQ_QUEUE_REPORTES', 'bite.reportes')

# ── Email notifications (architecture.md §2.2 API Email Provider) ──────────
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend',
)
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.sendgrid.net')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = True
EMAIL_FROM = os.environ.get('EMAIL_FROM', 'notificaciones@bite.co')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.environ.get('LOG_LEVEL', 'INFO'),
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.environ.get('DJANGO_LOG_LEVEL', 'WARNING'),
            'propagate': False,
        },
        'celery': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_PARSER_CLASSES': ['rest_framework.parsers.JSONParser'],
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.AnonRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {
        'anon': os.environ.get('API_THROTTLE_ANON', '5000/min'),
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
USE_TZ = True
TIME_ZONE = 'UTC'
LANGUAGE_CODE = 'en-us'
