FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspace/BackEnd

COPY requirements-core.txt .
RUN python -m pip install --no-cache-dir -r requirements-core.txt

COPY alembic.ini .
COPY migrations migrations
COPY scripts scripts
COPY app app
COPY seed_core.py .

EXPOSE 8015
CMD ["sh", "-c", "python scripts/migrate.py && uvicorn app.main:app --host 0.0.0.0 --port 8015"]
