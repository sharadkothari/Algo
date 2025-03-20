import os

workers = 1
reload = True
keepalive = 5
# Enable threading for AP Scheduler compatibility
threads = 2

bind = os.getenv("GUNICORN_BIND", "0.0.0.0:5000")
# Keepalive setting

# Gunicorn log settings
accesslog = None  # log_file
errorlog = "-"
loglevel = "info"
capture_output = True

