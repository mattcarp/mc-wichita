"""Pytest defaults: keep legacy API tests unauthenticated unless they opt in."""

import os

os.environ.setdefault("WICHITA_AUTH_REQUIRED", "false")
