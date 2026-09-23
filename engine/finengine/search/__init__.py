"""搜索与 RAG 检索模块（Spike C 产出）。

按页切块 + 本地向量检索（bge-small-zh），每个检索结果携带
出处页码——AI 问答防幻觉的根基：检索到的原文片段连同页码
一起交给 AI，要求 AI 每个结论标注出处。
"""

from .retriever import DocumentRetriever, SearchHit

__all__ = ["DocumentRetriever", "SearchHit"]
