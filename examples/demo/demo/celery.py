import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "demo.settings")

# Tasks (AI fields, background agents) run inline: CELERY_TASK_ALWAYS_EAGER.
app = Celery("demo")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
