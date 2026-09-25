@echo off
REM 无头分析：agent 对话内直接分析文档，无需打开界面
REM 用法：scripts\analyze.bat "文件路径.pdf"
cd /d "%~dp0..\engine"
.venv\Scripts\python -m finengine analyze %*
