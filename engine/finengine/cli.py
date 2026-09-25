"""FinEngine 命令行入口（跨 agent 无头使用的主要方式）。

用法（engine 目录下，Windows 用 .venv\\Scripts\\python）：
  python -m finengine serve [--port N]     启动引擎服务
  python -m finengine analyze <文件路径>   无头分析文档（M4 里程碑起逐步实现）
  python -m finengine version              打印版本
"""

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(prog="finengine", description="FinResearch 数据引擎")
    sub = parser.add_subparsers(dest="command", required=True)

    p_serve = sub.add_parser("serve", help="启动本地引擎服务（供桌面界面调用）")
    p_serve.add_argument("--host", default="127.0.0.1", help="监听地址（默认仅本机）")
    p_serve.add_argument("--port", type=int, default=0, help="端口（0=随机）")

    p_analyze = sub.add_parser("analyze", help="无头分析金融文档")
    p_analyze.add_argument("path", help="PDF/Excel 文件路径")

    sub.add_parser("version", help="打印引擎版本")

    args = parser.parse_args()

    if args.command == "serve":
        from .main import serve

        serve(args.host, args.port)
    elif args.command == "analyze":
        # 无头分析：创建项目 → 解析 → 打印指标与异常（供 agent 对话内使用）
        from pathlib import Path

        from .mcp_server import analyze_document

        p = Path(args.path)
        if not p.exists():
            print(f"文件不存在：{p}", file=sys.stderr)
            raise SystemExit(1)
        print(f"正在分析 {p.name} …（数百页文件可能需要 1-2 分钟）")
        result = analyze_document(str(p))
        if not result.get("ok"):
            print(f"分析失败：{result.get('error')}", file=sys.stderr)
            raise SystemExit(1)
        print(f"完成：项目 {result['project_id']}，提取财务行 {result['financial_lines']} 条，"
              f"发现异常 {result['anomalies']} 条")
        from .mcp_server import get_indicators, get_anomalies

        print("\n=== 财务指标 ===")
        for ind in get_indicators(result["project_id"]):
            page = f"（第{ind['source_page']}页）" if ind.get("source_page") else ""
            print(f"  {ind['name']} {ind['period']}: {ind['value']:,.2f}{ind['unit']}{page}")
        anomalies = get_anomalies(result["project_id"])
        if anomalies:
            print("\n=== 发现异常 ===")
            for a in anomalies:
                print(f"  [{a['severity']}] {a['title']}")
    elif args.command == "version":
        from . import __version__

        print(__version__)


if __name__ == "__main__":
    main()
