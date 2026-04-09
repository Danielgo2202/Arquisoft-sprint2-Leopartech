import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'manejador_reportes.settings')

app = Celery('manejador_reportes')

# Load Celery config from Django settings, namespace 'CELERY'
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in installed apps
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
