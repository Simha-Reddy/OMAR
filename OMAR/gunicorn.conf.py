"""Gunicorn runtime configuration for OMAR."""

import multiprocessing
import os

bind = os.getenv("GUNICORN_BIND", "0.0.0.0:5050")
workers = int(os.getenv("GUNICORN_WORKERS", str((multiprocessing.cpu_count() * 2) + 1)))
threads = int(os.getenv("GUNICORN_THREADS", "2"))
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gthread")
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))
preload_app = True
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOGLEVEL", "info")
worker_tmp_dir = os.getenv("GUNICORN_WORKER_TMP_DIR", "/dev/shm")
