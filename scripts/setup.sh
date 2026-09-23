#!/usr/bin/env bash
# FinResearch 安装脚本（macOS / Linux）
set -e
cd "$(dirname "$0")/.."

echo "============================================"
echo "  FinResearch 安装"
echo "============================================"

echo "[1/3] 创建 Python 虚拟环境..."
cd engine
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip --quiet
echo "[2/3] 安装引擎依赖..."
.venv/bin/python -m pip install -r requirements.txt --quiet

echo "[3/3] 安装界面依赖（npm，可能需要几分钟）..."
cd ../app
npm install

echo
echo "安装完成！运行 scripts/launch.sh 启动软件。"
