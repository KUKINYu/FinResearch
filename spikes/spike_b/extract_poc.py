"""Spike B 第三步：核心指标提取 POC。

策略：找到含"主要会计数据"或"主要财务指标"的页面，提取其中表格，
打印表格前几行（人工/程序核对结构），为指标行定位规则提供依据。
"""

import sys
from pathlib import Path

import pdfplumber

DATA_DIR = Path(__file__).parent / "data"
MAX_ROWS_SHOWN = 6


def show_tables(path: Path, keywords: tuple[str, ...], max_pages: int = 6) -> None:
    print(f"\n{'=' * 60}\n{path.name}")
    with pdfplumber.open(path) as pdf:
        shown = 0
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if not any(kw in text for kw in keywords):
                continue
            tables = page.extract_tables()
            if not tables:
                continue
            print(f"\n--- 第 {i + 1} 页（命中关键词，{len(tables)} 个表格） ---")
            for t in tables:
                print(f"表格 {len(t)} 行 x {len(t[0]) if t else 0} 列，前几行：")
                for row in t[:MAX_ROWS_SHOWN]:
                    cells = [c.replace("\n", " ") if c else "" for c in row]
                    print("  | " + " | ".join(cells))
            shown += 1
            if shown >= max_pages:
                return


def main() -> int:
    files = sorted(DATA_DIR.glob("*.pdf"))
    # 先详细看第一份（中塑股份），再快速看其余
    show_tables(files[0], ("主要会计数据", "主要财务指标"))
    for path in files[1:]:
        show_tables(path, ("主要会计数据", "主要财务指标"), max_pages=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
