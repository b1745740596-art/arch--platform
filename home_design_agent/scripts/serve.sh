#!/usr/bin/env bash
# 本地一键启动：构建前端 → 收集静态 → 迁移 → 释放端口 → 前台起 Django。
#
# 为什么必须合成一步：DEBUG=false 时 /static/ 由 WhiteNoise 从 STATIC_ROOT 托管，
# 只跑 npm run build 会把产物留在 frontend_dist/，不 collectstatic 就整站白屏；
# 且 WhiteNoise 只在进程启动时扫描静态清单，收集完不重启同样白屏。
#
# 用法：
#   scripts/serve.sh                # 全量：构建前端 + 收集静态 + 迁移 + 启动
#   scripts/serve.sh --no-build     # 只改了后端，跳过 npm run build（快）
#   scripts/serve.sh --debug        # DJANGO_DEBUG=true（可浏览 API、详细报错）
#   scripts/serve.sh --port 8010    # 换端口
#   scripts/serve.sh --seed         # 顺带灌 prompt 模块 / 工作流 / 示例家具
#
# Ctrl+C 停止。
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(dirname "$PROJECT_DIR")"

DO_BUILD=1
DO_SEED=0
DEBUG_MODE=0
PORT=8000
HOST=0.0.0.0

while [ $# -gt 0 ]; do
  case "$1" in
    --no-build|--skip-build) DO_BUILD=0 ;;
    --build) DO_BUILD=1 ;;
    --seed) DO_SEED=1 ;;
    --debug) DEBUG_MODE=1 ;;
    --port) PORT="${2:?--port 需要参数}"; shift ;;
    --host) HOST="${2:?--host 需要参数}"; shift ;;
    -h|--help) sed -n '2,15p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "未知参数：$1（-h 查看用法）" >&2; exit 2 ;;
  esac
  shift
done

step() { printf '\n\033[1;36m[serve] %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m[serve] %s\033[0m\n' "$*" >&2; exit 1; }

cd "$PROJECT_DIR"

[ -x .venv/bin/python ] || die "缺少 .venv，请先 python -m venv .venv && pip install -r requirements.txt"
PY=.venv/bin/python

# DEBUG=false 且没有 nginx 时 Django 默认不托管 /media/，效果图会 404。
# 本地单进程直跑必须兜底打开；shell 里 export 的值优先于 .env。
export DJANGO_SERVE_MEDIA="${DJANGO_SERVE_MEDIA:-true}"
if [ "$DEBUG_MODE" = "1" ]; then
  export DJANGO_DEBUG=true
fi

# ---- 1. 构建前端 ----
if [ "$DO_BUILD" = "1" ]; then
  step "构建前端产物 -> frontend_dist/"
  if [ -d "$REPO_ROOT/.toolchain/node/bin" ]; then
    export PATH="$REPO_ROOT/.toolchain/node/bin:$PATH"
  fi
  command -v npm >/dev/null 2>&1 || die "找不到 npm（期望 $REPO_ROOT/.toolchain/node/bin）"
  [ -d frontend/node_modules ] || (cd frontend && npm install)
  (cd frontend && npm run build)
else
  step "跳过前端构建（--no-build）"
fi

# ---- 2. 收集静态 ----
step "收集静态文件 -> staticfiles/"
"$PY" manage.py collectstatic --noinput >/dev/null
echo "staticfiles/spa/assets 下 JS 资源：$(find staticfiles/spa/assets -type f -name '*.js' 2>/dev/null | wc -l | tr -d ' ') 个"

# ---- 3. 迁移 ----
step "应用数据库迁移"
"$PY" manage.py migrate --noinput

if [ "$DO_SEED" = "1" ]; then
  step "灌入基线数据"
  "$PY" manage.py seed_prompt_modules --update
  "$PY" manage.py seed_workflows
  "$PY" manage.py seed_demo
fi

# ---- 4. 释放端口 ----
# 残留旧进程会抢到请求，且持有过期静态清单 -> 表现为改了代码不生效 / 白屏。
if command -v lsof >/dev/null 2>&1; then
  OLD_PIDS="$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null || true)"
  if [ -n "$OLD_PIDS" ]; then
    step "端口 $PORT 有残留进程，结束：$(echo "$OLD_PIDS" | tr '\n' ' ')"
    kill $OLD_PIDS 2>/dev/null || true
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      sleep 0.5
      [ -z "$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null || true)" ] && break
    done
    STILL="$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null || true)"
    if [ -n "$STILL" ]; then
      kill -9 $STILL 2>/dev/null || true
      sleep 1
    fi
    STILL="$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null || true)"
    if [ -n "$STILL" ]; then
      die "端口 $PORT 仍被 PID $(echo "$STILL" | tr '\n' ' ')占用且无法结束（可能属于其他用户）。
      请手动处理：kill -9 $(echo "$STILL" | tr '\n' ' ')
      或换端口重跑：scripts/serve.sh --port 8010"
    fi
  fi
fi

# ---- 5. 启动 ----
step "启动 Django（DEBUG=${DJANGO_DEBUG:-false}，SERVE_MEDIA=${DJANGO_SERVE_MEDIA}）"
cat <<BANNER

  前端首页    http://localhost:$PORT/
  设计工作台  http://localhost:$PORT/studio
  效果图列表  http://localhost:$PORT/render
  管理后台    http://localhost:$PORT/admin/
  健康检查    http://localhost:$PORT/api/design/health/

  若仍白屏，按 Cmd+Shift+R 硬刷新清掉此前的 404 缓存。
  Ctrl+C 停止服务。

BANNER

exec "$PY" manage.py runserver "$HOST:$PORT" --noreload
