from .base import *  # noqa: F403
from .base import SECRET_KEY, env_bool

DEBUG = env_bool("DJANGO_DEBUG", True)
SECRET_KEY = SECRET_KEY or "dev-insecure-key-do-not-use-in-prod"
ALLOWED_HOSTS = ["*"]
