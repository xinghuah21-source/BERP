FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev ca-certificates && apt-get install -y --no-install-recommends --reinstall libssl3 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade --force-reinstall -r /app/requirements.txt

COPY . /app

ENV PYTHONPATH=/app

CMD ["sh", "-c", "python -m alembic upgrade head && python scripts/seed.py && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"]
