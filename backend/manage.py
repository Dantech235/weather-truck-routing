#!/usr/bin/env python
"""Django's command-line utility."""

import os
import sys


def main() -> None:
    # Vercel sets VERCEL=1 when it runs manage.py to discover the settings module.
    default = "config.settings.prod" if os.environ.get("VERCEL") else "config.settings.dev"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", default)
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
