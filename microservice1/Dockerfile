FROM monorepo_base

COPY microservice1/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY shared /app/shared
COPY microservice1 /app

CMD ["python", "app.py"]