@echo off
REM FinResearch 安装脚本：创建 Python 虚拟环境 + 安装引擎与界面依赖
REM 首次使用运行一次即可（约几分钟）
setlocal
cd /d "%~dp0.."

echo ============================================
echo   FinResearch 安装
echo ============================================

echo [1/3] 创建 Python 虚拟环境...
cd engine
python -m venv .venv
if errorlevel 1 (
  echo 失败：请确认已安装 Python 3.10+ 并加入 PATH（python.org 下载）
  pause & exit /b 1
)
.venv\Scripts\python -m pip install --upgrade pip --quiet
echo [2/3] 安装引擎依赖...
.venv\Scripts\python -m pip install -r requirements.txt --quiet

echo [3/3] 安装界面依赖（npm，可能需要几分钟）...
cd ..\app
call npm install

echo.
echo 安装完成！运行 scripts\launch.bat 启动软件。
pause
