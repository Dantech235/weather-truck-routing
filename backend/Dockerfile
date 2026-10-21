FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --home /app app

ARG INSTALL_DEV=false
COPY pyproject.toml ./
RUN pip install --upgrade pip \
    && if [ "$INSTALL_DEV" = "true" ]; then pip install ".[dev]"; else pip install .; fi

COPY . .

# collectstatic needs a key at build time only; the real one comes from the environment.
RUN DJANGO_SECRET_KEY=build-only DJANGO_SETTINGS_MODULE=config.settings.prod \
    python manage.py collectstatic --noinput

USER app
EXPOSE 8000

CMD ["sh", "-c", "gunicorn config.wsgi -w 3 -b 0.0.0.0:${PORT} --access-logfile -"]
