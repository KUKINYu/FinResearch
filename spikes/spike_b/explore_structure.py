"""Spike B 第二步：探查招股书结构——找到"主要财务数据"章节所在页。

对每份招股书扫描全部页面，寻找关键章节标题，打印页码分布，
为提取器设计提供依据（不同券商/板块的招股书结构差异）。
"""

import sys
from pathlib import Path

import pdfplumber

DATA_DIR = Path(__file__).parent / "data"

# 章节关键词（招股书"财务会计信息"部分常见的标题写法）
SECTION_KEYWORDS = [
    "主要会计数据",
    "主要财务数据",
    "主要财务指标",
    "合并利润表",
    "合并资产负债表",
    "合并现金流量表",
    "营业收入构成",
    "经营成果",
]


def scan(path: Path) -> dict[str, list[int]]:
    hits: dict[str, list[int]] = {}
    with pdfplumber.open(path) as pdf:
        print(f"\n=== {path.name} === 共 {len(pdf.pages)} 页")
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            for kw in SECTION_KEYWORDS:
                if kw in text:
                    hits.setdefault(kw, []).append(i + 1)
    return hits


def main() -> int:
    for path in sorted(DATA_DIR.glob("*.pdf")):
        hits = scan(path)
        for kw, pages in hits.items():
            # 只显示前 8 个命中页，避免刷屏
            shown = pages[:8]
            suffix = " ..." if len(pages) > 8 else ""
            print(f"  {kw}: 第 {shown}{suffix}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
