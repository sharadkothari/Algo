FROM monorepo_base
COPY . .
CMD ["gunicorn", "-c", "gunicorn_config.py", "alerts:app"]