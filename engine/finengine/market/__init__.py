"""A 股市场数据源（P1 同行对比）。

统一数据源接口 + 本地缓存 + 失败降级：
- 数据源：AkShare（免费公开数据，仅学术/个人使用——商用前必须换授权数据源，
  见 CLAUDE.md 合规红线）
- 缓存：market_cache 表（财务数据 24h、行情 1h），联网失败用缓存兜底
- 联网功能挂了不影响核心闭环（上传/分析/异常/搜索全部本地）
"""

from .source import (
    get_comparison,
    get_valuation,
    search_stocks,
)

__all__ = ["search_stocks", "get_valuation", "get_comparison"]
