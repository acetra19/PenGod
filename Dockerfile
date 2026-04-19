# PenGod API (FastAPI). For local/VPS use with docker-compose (Qdrant separate service).
FROM python:3.11-slim-bookworm

# onnxruntime (FastEmbed) expects OpenMP on many Linux builds
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY pyproject.toml README.md ./
COPY pengod ./pengod

RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -e .

EXPOSE 8000

# First model download can be slow; set HF_HOME if you mount a cache volume
CMD ["uvicorn", "pengod.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
