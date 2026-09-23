"""Spike C 验收运行器：RAG 溯源 POC。

对一份真实招股书建索引，用金融研究中的典型问题测试检索质量：
每个命中必须带页码出处，片段与问题相关。
验收标准（人工核验）：
- top-5 命中里 ≥3 条与问题直接相关
- 每条命中带 (页码) 可回原文核对
"""

import sys
import time
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine"))

from finengine.search import DocumentRetriever  # noqa: E402

PDF = Path(__file__).resolve().parents[1] / "spike_b" / "data" / "301686_中塑股份_招股说明书.pdf"
MAX_PAGES = 150

# 金融研究典型问题（用户真实会问的）
QUERIES = [
    "主要客户情况",
    "应收账款增长的原因",
    "毛利率变化原因",
    "研发投入情况",
    "关联交易情况",
    "行业竞争格局",
]


def main() -> int:
    print(f"索引文件: {PDF.name} 前 {MAX_PAGES} 页")
    retriever = DocumentRetriever(PDF.name)

    t0 = time.time()
    with pdfplumber.open(PDF) as pdf:
        for i in range(min(MAX_PAGES, len(pdf.pages))):
            text = pdf.pages[i].extract_text() or ""
            retriever.add_page(i + 1, text)
    n_chunks = retriever.build_index()
    print(f"切块 {n_chunks} 个，建索引耗时 {time.time() - t0:.1f} 秒\n")

    for query in QUERIES:
        print(f"{'=' * 60}\n问：{query}")
        hits = retriever.search(query, top_k=5)
        for rank, h in enumerate(hits, 1):
            print(f"  #{rank} 第{h.page}页 (相关度 {h.score:.3f})")
            print(f"     {h.text[:120]}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
