"""Vercel build step for the Django API (runs after dependencies are installed).

Vercel runs `collectstatic` itself (STATIC_ROOT is set). This step applies database
migrations when DATABASE_URL is available, so every deployment ships with an up-to-date
schema. Set SKIP_MIGRATIONS=1 to opt out (e.g. preview deployments sharing a database).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Run as `python scripts/vercel_build.py`: make the project root importable (config, trips…).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")
    if os.environ.get("SKIP_MIGRATIONS") == "1":
        print("vercel_build: SKIP_MIGRATIONS=1, not migrating")
        return 0
    if not os.environ.get("DATABASE_URL"):
        print("vercel_build: DATABASE_URL not set, skipping migrations", file=sys.stderr)
        return 0
    import django
    from django.core.management import call_command

    django.setup()
    call_command("migrate", interactive=False, verbosity=1)
    print("vercel_build: migrations applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
