"""Gunicorn entrypoint for OMAR."""
from omar import create_app

app = create_app()
