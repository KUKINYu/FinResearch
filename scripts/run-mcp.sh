#!/usr/bin/env bash
# FinResearch MCP server (Claude Desktop / Cursor)
set -e
cd ""/usr/bin/../engine"
.venv/bin/python -m finengine.mcp_server
