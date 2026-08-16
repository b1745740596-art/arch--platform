#!/usr/bin/env bash
# 双击本文件即可启动网站。窗口关闭或按 Control+C 即停止。
cd "$(dirname "$0")/home_design_agent" || exit 1
./scripts/serve.sh "$@"
