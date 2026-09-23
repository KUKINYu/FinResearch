"""FinEngine 命令行入口（跨 agent 无头使用的主要方式）。

用法（engine 目录下，Windows 用 .venv\\Scripts\\python）：
  python -m finengine serve [--port N]     启动引擎服务
  python -m finengine analyze <文件路径>   无头分析文档（M4 里程碑起逐步实现）
  python -m finengine version              打印版本
"""

import argparse


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
        print("analyze 命令将在 M2/M4 里程碑实现（文档解析与财务提取）。")
    elif args.command == "version":
        from . import __version__

        print(__version__)


if __name__ == "__main__":
    main()
