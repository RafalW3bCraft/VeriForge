FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend .
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --upgrade pip && \
    pip install -r requirements.txt

COPY . .
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

# The service never needs root privileges. Named Compose volumes are populated
# from these owned directories on first use.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin veriforge && \
    mkdir -p /app/data /app/.hmem && \
    chown -R veriforge:veriforge /app

USER veriforge

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/ready', timeout=3)" || exit 1
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
