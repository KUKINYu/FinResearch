"""把 scripts 下的 .bat 用 GBK 编码重写（一次性维护工具）。

背景：Windows cmd 按系统代码页（GBK）解析批处理文件；
UTF-8 编码的中文注释会被误读为命令。本脚本用 raw string
重写全部 .bat，避免转义链（bash→Python）破坏内容。
"""

from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent

SETUP_BAT = r"""@echo off
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
"""

LAUNCH_BAT = r"""@echo off
REM FinResearch 启动脚本（首次使用请先运行 setup.bat）
REM 防御：个别机器环境变量 ELECTRON_RUN_AS_NODE=1 会让 Electron 以纯 Node 模式运行导致启动失败，这里强制移除
set ELECTRON_RUN_AS_NODE=
cd /d "%~dp0..\app"
if not exist node_modules (
  echo 首次运行，先安装依赖...
  call npm install
)
call npm run dev
"""

ANALYZE_BAT = r"""@echo off
REM 无头分析：agent 对话内直接分析文档，无需打开界面
REM 用法：scripts\analyze.bat "文件路径.pdf"
cd /d "%~dp0..\engine"
.venv\Scripts\python -m finengine analyze %*
"""


def main() -> None:
    for name, content in (
        ("setup.bat", SETUP_BAT),
        ("launch.bat", LAUNCH_BAT),
        ("analyze.bat", ANALYZE_BAT),
    ):
        # Windows 批处理必须是 CRLF 换行 + GBK 编码（LF 会被 cmd 误解析）
        content_crlf = content.replace("\n", "\r\n")
        (SCRIPTS_DIR / name).write_bytes(content_crlf.encode("gbk"))
        print(f"{name} 已用 GBK+CRLF 写入")


if __name__ == "__main__":
    main()
