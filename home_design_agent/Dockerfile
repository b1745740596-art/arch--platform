# ---------- 阶段 1：构建 Vue 前端产物 ----------
FROM node:24-bookworm-slim AS frontend

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ ./
# vite.config.js 里 outDir 指向 ../frontend_dist，因此产物落在 /frontend_dist
RUN npm run build

# ---------- 阶段 2：Python 运行时 ----------
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings

# opencv-python-headless 需要 libgl/libglib；pdf2image 需要 poppler-utils
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgl1 \
        poppler-utils \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY manage.py ./
COPY config/ ./config/
COPY design/ ./design/
COPY deploy/ ./deploy/

# 前端构建产物（Django 通过 STATICFILES_DIRS 挂到 /static/spa/，模板读 index.html）
COPY --from=frontend /frontend_dist/ ./frontend_dist/

# 静态与媒体目录，媒体在 compose 里挂持久卷
RUN mkdir -p /app/staticfiles /data/media \
    && chmod +x deploy/entrypoint.sh

ENV DJANGO_MEDIA_ROOT=/data/media \
    DJANGO_STATIC_ROOT=/app/staticfiles

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app /data
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/design/health/ || exit 1

ENTRYPOINT ["./deploy/entrypoint.sh"]
