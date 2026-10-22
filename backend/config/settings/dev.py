from .base import *  # noqa: F403
from .base import SECRET_KEY, env_bool

DEBUG = env_bool("DJANGO_DEBUG", True)
SECRET_KEY = SECRET_KEY or "dev-insecure-key-do-not-use-in-prod"
ALLOWED_HOSTS = ["*"]

# Any local dev origin (localhost or 127.0.0.1, any port) in addition to CORS_ALLOWED_ORIGINS.
CORS_ALLOWED_ORIGIN_REGEXES = [r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"]
