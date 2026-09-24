"""全文搜索（M6）：SQLite FTS5（中文 trigram）+ 同义词扩展。

设计：
- 索引 = pages 表上的 FTS5 虚表（trigram 分词适合中文子串匹配）
- 查询 <3 字的短词（如"客户"）回退 LIKE 扫描（trigram 只支持 ≥3 字）
- 同义词扩展：金融术语同义词表（数据文件），命中同组的词一起搜
- 结果带页码 + 上下文摘录（手工截取，可靠高亮）
"""

import json
import re
from pathlib import Path

from sqlalchemy import text

from ..db import engine

# 同义词表：一组同义表达（"主要客户"≈"前五大客户"）
SYNONYMS: list[list[str]] = [
    ["主要客户", "前五大客户", "前五名客户", "主要销售客户", "前五客户"],
    ["应收账款", "应收款项", "应收帐款"],
    ["毛利率", "销售毛利率", "综合毛利率"],
    ["经营活动现金流", "经营活动产生的现金流量", "经营性现金流"],
    ["研发费用", "研发投入", "研究开发费用"],
    ["资产负债率", "资产负债比率"],
    ["关联交易", "关联方交易", "关联采购", "关联销售"],
    ["主要供应商", "前五大供应商", "前五名供应商", "主要采购供应商"],
    ["实际控制人", "控股股东", "实控人"],
]

# 同义词查询表：词 → 同组其他词
_SYNONYM_MAP: dict[str, list[str]] = {}
for _group in SYNONYMS:
    for _w in _group:
        _SYNONYM_MAP[_w] = _group


def build_index() -> None:
    """（重）建 FTS5 索引（解析完成后调用）。"""
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS pages_fts"))
        conn.execute(
            text(
                "CREATE VIRTUAL TABLE pages_fts USING fts5("
                "text, content='pages', content_rowid='id', tokenize='trigram')"
            )
        )
        conn.execute(text("INSERT INTO pages_fts(pages_fts) VALUES('rebuild')"))


def expand_query(query: str) -> list[str]:
    """同义词扩展：命中同义词表的词，返回整组词。"""
    terms: list[str] = []
    for word, group in _SYNONYM_MAP.items():
        if word in query:
            terms.extend(group)
    if not terms:
        terms.append(query)
    return sorted(set(terms), key=len, reverse=True)


def _snippet(text: str, term: str, width: int = 60) -> str:
    """截取关键词周围上下文，用于结果摘录。"""
    pos = text.find(term)
    if pos < 0:
        return text[: width * 2]
    start = max(0, pos - width)
    end = min(len(text), pos + len(term) + width)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return prefix + text[start:end] + suffix


def search(file_ids: list[int], query: str, limit: int = 20) -> list[dict]:
    """搜索项目内文件（file_ids 为空 = 全库）。返回带页码与摘录的结果。"""
    terms = expand_query(query.strip())
    results: dict[tuple[int, int], dict] = {}  # (file_id, page_no) → 去重

    file_filter = "AND p.file_id IN ({})".format(",".join(str(i) for i in file_ids)) if file_ids else ""

    with engine.connect() as conn:
        for term in terms:
            if len(term) >= 3:
                # FTS5 trigram 匹配
                sql = (
                    "SELECT p.file_id, p.page_no, p.text "
                    "FROM pages_fts f JOIN pages p ON p.id = f.rowid "
                    "WHERE pages_fts MATCH :q {} LIMIT 200".format(file_filter)
                )
                rows = conn.execute(text(sql), {"q": f'"{term}"'}).fetchall()
            else:
                # 短词回退 LIKE（与 FTS 查询一致用别名 p）
                sql = "SELECT p.file_id, p.page_no, p.text FROM pages p WHERE p.text LIKE :q {} LIMIT 200".format(
                    file_filter
                )
                rows = conn.execute(text(sql), {"q": f"%{term}%"}).fetchall()

            for file_id, page_no, page_text in rows:
                text_ = page_text or ""
                pos = text_.find(term)
                if pos < 0:
                    continue
                key = (file_id, page_no)
                # 同义词组的多次命中累加得分（位置靠前得分高）
                score = 1.0 / (1 + pos / 500) + (2.0 if len(term) >= 4 else 1.0)
                if key not in results:
                    results[key] = {
                        "file_id": file_id,
                        "page_no": page_no,
                        "snippet": _snippet(text_, term),
                        "matched_term": term,
                        "score": score,
                    }
                else:
                    results[key]["score"] += score

    ranked = sorted(results.values(), key=lambda r: -r["score"])[:limit]
    return ranked
