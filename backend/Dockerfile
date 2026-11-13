# API and background worker image (same code, different command).
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

COPY requirements.txt requirements-embeddings.txt ./
RUN pip install -r requirements.txt
# Search by meaning with a small CPU model inside the app (RFP_EMBEDDING_PROVIDER=local).
# Build with --build-arg LOCAL_EMBEDDINGS=false to leave it out (~200 MB smaller).
ARG LOCAL_EMBEDDINGS=true
RUN if [ "$LOCAL_EMBEDDINGS" = "true" ]; then pip install -r requirements-embeddings.txt; fi

COPY alembic.ini .
COPY migrations ./migrations
COPY app ./app
COPY evals ./evals

# Run as an unprivileged user; uploaded files live on a volume mounted at /data.
RUN useradd --system --uid 10001 --home /app rfp && mkdir -p /data/files /data/models && chown -R rfp /data
USER rfp
ENV RFP_STORAGE_DIR=/data/files RFP_EMBEDDING_CACHE_DIR=/data/models \
    HF_HOME=/data/models/huggingface XDG_CACHE_HOME=/data/models/cache

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
