"""文档解析与财务数据提取模块。

Spike B 产出：financial_extractor 从招股书/年报 PDF 中定位并提取
10 项核心财务指标，每条数据带出处（页码 + 坐标 + 原始文字）。
"""

from .financial_extractor import extract_indicators, extract_document

__all__ = ["extract_indicators", "extract_document"]
