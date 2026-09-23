"""Spike B 验收运行器：对 5 份真实招股书执行指标提取并输出报告。

运行：engine/.venv/Scripts/python spikes/spike_b/run_extraction.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine"))

from finengine.extract import extract_indicators  # noqa: E402

DATA_DIR = Path(__file__).parent / "data"
CORE = ("营业收入", "净利润", "归属于母公司股东的净利润", "毛利率", "净利率",
        "加权平均净资产收益率", "经营活动产生的现金流量净额",
        "应收账款", "存货", "有息负债", "研发费用")


def report(path: Path) -> dict:
    result = extract_indicators(path)
    meta = result.pop("_meta")
    print(f"\n{'=' * 70}")
    print(f"{meta['file']}  （共 {meta['pages']} 页，识别表格 {len(meta['tables_found'])} 个）")
    from collections import Counter
    type_dist = Counter(hint for _, hint, _ in meta["tables_found"])
    print(f"  表类型分布: {dict(type_dist)}")
    for ind in CORE:
        periods = result.get(ind, {})
        if not periods:
            print(f"  ✗ {ind}: 未提取到")
            continue
        for p, d in sorted(periods.items()):
            derived = f" [{d.get('derived', '')}]" if d.get("derived") else ""
            print(f"  ✓ {ind} {p}: {d['value']} {d['unit']}  (第{d['source']['page']}页){derived}")
    return {"file": meta["file"], "indicators": result, "meta": meta}


def main() -> int:
    results = []
    for path in sorted(DATA_DIR.glob("*.pdf")):
        results.append(report(path))
    out = Path(__file__).parent / "extraction_result.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n完整结果已写入 {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
