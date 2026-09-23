#!/usr/bin/env bash
# FinResearch 启动脚本（macOS / Linux，首次使用请先运行 setup.sh）
set -e
# 防御：个别机器环境变量 ELECTRON_RUN_AS_NODE=1 会让 Electron 以纯 Node 模式运行导致启动失败
unset ELECTRON_RUN_AS_NODE 2>/dev/null || true
cd "$(dirname "$0")/.."
cd app
[ -d node_modules ] || npm install
npm run dev
