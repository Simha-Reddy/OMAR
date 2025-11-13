"""Gunicorn entrypoint for OMAR_refactor."""
from omar import create_app

app = create_app()
