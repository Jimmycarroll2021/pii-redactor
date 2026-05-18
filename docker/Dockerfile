# syntax=docker/dockerfile:1.6
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install API/runtime deps first to leverage Docker layer caching.
# The production API image deliberately excludes demo/test dependencies.
COPY requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt

COPY pii_redactor ./pii_redactor
COPY api ./api
COPY app.py ./
COPY pyproject.toml README.md ./

# Install package itself so `from pii_redactor import ...` works system-wide
RUN pip install --no-cache-dir -e .

# Default to the FastAPI service. Override with:
#   docker run ... pii-redactor python app.py        (Gradio)
#   docker run ... pii-redactor uvicorn api.main:app (API, default)
EXPOSE 8000 7860
HEALTHCHECK --interval=30s --timeout=10s --retries=5 --start-period=30s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=5).read()" || exit 1
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
