import os
import copy
import urllib.parse

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.develop")

from celery import Celery
from kombu import Queue, Exchange
from django.conf import settings

app = Celery("codabench")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.conf.imports = (
    "competitions.tasks",
    "profiles.tasks",
    "analytics.tasks",
)

app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

queue_static = getattr(settings, "QUEUE_STATIC", "compute-worker-static")
queue_rolling = getattr(settings, "QUEUE_ROLLING", "compute-worker-rolling")
queue_site = getattr(settings, "QUEUE_SITE", "site-worker")

app.conf.task_queues = [
    Queue(
        queue_static,
        Exchange(queue_static),
        routing_key=queue_static,
        queue_arguments={"x-max-priority": 10},
    ),
    Queue(
        queue_rolling,
        Exchange(queue_rolling),
        routing_key=queue_rolling,
        queue_arguments={"x-max-priority": 10},
    ),
    Queue(
        queue_site,
        Exchange(queue_site),
        routing_key=queue_site,
        queue_arguments={"x-max-priority": 10},
    ),
]

_vhost_apps = {}


def app_for_vhost(vhost):
    if vhost not in _vhost_apps:
        broker_url = settings.CELERY_BROKER_URL

        scheme = urllib.parse.urlparse(broker_url).scheme
        if scheme not in urllib.parse.uses_relative:
            urllib.parse.uses_relative.append(scheme)
        if scheme not in urllib.parse.uses_netloc:
            urllib.parse.uses_netloc.append(scheme)

        broker_url = urllib.parse.urljoin(broker_url, vhost)

        vhost_app = Celery(f"codabench-{vhost}")
        django_settings = copy.copy(settings)
        django_settings.CELERY_BROKER_URL = broker_url

        vhost_app.config_from_object(django_settings, namespace="CELERY")
        vhost_app.conf.imports = app.conf.imports
        vhost_app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
        vhost_app.conf.task_queues = app.conf.task_queues

        _vhost_apps[vhost] = vhost_app

    return _vhost_apps[vhost]