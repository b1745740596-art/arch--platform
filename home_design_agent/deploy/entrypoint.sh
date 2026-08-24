#!/usr/bin/env bash
# 容器启动入口：等数据库就绪 → 迁移 → 收集静态 → 可选灌种子 → 起 gunicorn
set -euo pipefail

echo "[entrypoint] waiting for database ..."
python - <<'PY'
import os
import sys
import time

url = os.environ.get('DATABASE_URL', '')
if not url:
    print('[entrypoint] DATABASE_URL 未设置，使用 SQLite，跳过等待')
    sys.exit(0)

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.db import connections
from django.db.utils import OperationalError

deadline = time.time() + int(os.environ.get('DB_WAIT_TIMEOUT', '60'))
while True:
    try:
        connections['default'].ensure_connection()
        print('[entrypoint] database ready')
        break
    except OperationalError as exc:
        if time.time() > deadline:
            print(f'[entrypoint] database not ready: {exc}')
            sys.exit(1)
        time.sleep(2)
PY

echo "[entrypoint] applying migrations ..."
python manage.py migrate --noinput

echo "[entrypoint] collecting static files ..."
python manage.py collectstatic --noinput

# 首次部署可设 SEED_ON_START=1 灌入预置工作流 / prompt 模块 / 示例数据。
# 这些命令幂等或带 --update，可重复执行。
if [ "${SEED_ON_START:-0}" = "1" ]; then
  echo "[entrypoint] seeding baseline data ..."
  python manage.py seed_prompt_modules --update || true
  python manage.py seed_workflows || true
  python manage.py seed_talkbot || true
  python manage.py seed_demo || true
fi

# 可选：用环境变量自动创建管理员，避免手工 exec 进容器
if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
  if [ "${#DJANGO_SUPERUSER_PASSWORD}" -lt 16 ] || [[ "$DJANGO_SUPERUSER_PASSWORD" == change-me* ]]; then
    echo "[entrypoint] refusing weak/placeholder DJANGO_SUPERUSER_PASSWORD" >&2
    exit 1
  fi
  echo "[entrypoint] ensuring superuser ${DJANGO_SUPERUSER_USERNAME} ..."
  python manage.py createsuperuser --noinput || true
fi

echo "[entrypoint] starting gunicorn ..."
exec gunicorn config.wsgi:application -c deploy/gunicorn.conf.py
