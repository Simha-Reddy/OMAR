"""Gunicorn entrypoint for OMAR_refactor."""
from app import create_app

app = create_app()
