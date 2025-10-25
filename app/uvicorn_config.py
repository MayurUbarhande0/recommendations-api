# uvicorn_config.py
import multiprocessing

# Uvicorn configuration for Windows
bind = "0.0.0.0:8000"
workers = min(4, multiprocessing.cpu_count())
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
keepalive = 5
timeout = 60
graceful_timeout = 30
max_requests = 10000
max_requests_jitter = 1000

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"