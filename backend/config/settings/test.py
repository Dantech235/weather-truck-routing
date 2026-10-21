from .base import *  # noqa: F403

DEBUG = True
SECRET_KEY = "test-key"
ALLOWED_HOSTS = ["*"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
PROVIDERS_MODE = "fake"
