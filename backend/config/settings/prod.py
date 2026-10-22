"""Production settings (Vercel Functions or any WSGI host behind HTTPS)."""

import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import ALLOWED_HOSTS, DATABASES, PROVIDERS_MODE, SECRET_KEY, env_bool, env_list

DEBUG = False

if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set in production.")
if PROVIDERS_MODE != "live":
    raise ImproperlyConfigured("PROVIDERS_MODE=fake is test-only and refused when DEBUG=False.")

# Vercel sets VERCEL=1 at build and run time; deployments are served on *.vercel.app (plus any
# custom domain listed in ALLOWED_HOSTS).
ON_VERCEL = bool(os.environ.get("VERCEL"))
if ON_VERCEL:
    ALLOWED_HOSTS = [*ALLOWED_HOSTS, ".vercel.app"]

# Serverless: don't hold connections across idle periods (use the provider's pooled URL, e.g.
# Neon's "-pooler" host). Health checks drop connections the pooler has closed.
DATABASES["default"]["CONN_MAX_AGE"] = int(os.environ.get("DB_CONN_MAX_AGE", "0"))
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

# Optional: allow frontend preview deployments, e.g. ^https://truck-web-.*\.vercel\.app$
CORS_ALLOWED_ORIGIN_REGEXES = env_list("CORS_ALLOWED_ORIGIN_REGEXES")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"

SILENCED_SYSTEM_CHECKS = [
    # Token-free JSON API with no sessions or cookie auth: CSRF middleware has nothing to guard.
    "security.W003",
    # HSTS preload is a decision for the domain owner (vercel.app is already preloaded).
    "security.W021",
]

# Vercel runs `collectstatic` automatically when STATIC_ROOT is set and serves the files from
# its CDN; WhiteNoise serves them anywhere else.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
