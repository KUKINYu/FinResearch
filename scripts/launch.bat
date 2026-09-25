@echo off
REM FinResearch 启动脚本（首次使用请先运行 setup.bat）
REM 防御：个别机器环境变量 ELECTRON_RUN_AS_NODE=1 会让 Electron 以纯 Node 模式运行导致启动失败，这里强制移除
set ELECTRON_RUN_AS_NODE=
cd /d "%~dp0..\app"
if not exist node_modules (
  echo 首次运行，先安装依赖...
  call npm install
)
call npm run dev
