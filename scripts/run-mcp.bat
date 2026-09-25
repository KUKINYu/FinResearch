@echo off
REM FinResearch MCP 服务器（接入 Claude Desktop / Cursor 等客户端）
cd /d "%~dp0..\engine"
.venv\Scripts\python -m finengine.mcp_server
