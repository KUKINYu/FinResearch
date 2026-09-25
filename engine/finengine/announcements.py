"""公告与舆情监控（P1-2）。

数据源：AkShare（东方财富公告/个股新闻，免费公开数据）。
- 按标的证券代码拉取近期公告 + 个股新闻
- 负面词命中识别（诉讼/处罚/问询/减持等）——尽调关注点
- 时间分层：近 3 天 / 近 30 天 / 更早（借鉴 TradingAgents 新闻分析师的
  时间权重设计，界面按层展示）
- AI 快摘要（quick 层级模型）："这家公司最近发生了什么"
"""

import datetime
import re

from sqlalchemy import select

from .db import SessionLocal
from .db.models import Announcement

# 负面关键词（尽调关注）
NEGATIVE_WORDS = (
    "诉讼", "处罚", "问询", "警示", "立案", "调查", "减持", "质押", "冻结",
    "违规", "整改", "亏损", "下滑", "减值", "终止", "退市", "警示函", "监管",
)


def _is_negative(title: str) -> bool:
    return any(w in title for w in NEGATIVE_WORDS)


def _layer(date_str: str | None) -> str:
    """时间分层：near(3天内) / month(30天内) / older。"""
    if not date_str:
        return "older"
    try:
        d = datetime.date.fromisoformat(date_str[:10])
    except ValueError:
        return "older"
    days = (datetime.date.today() - d).days
    if days <= 3:
        return "near"
    if days <= 30:
        return "month"
    return "older"


def fetch_and_store(project_id: int, code: str, limit: int = 30) -> dict:
    """拉取公告+新闻并入库（覆盖该代码旧数据）。返回统计。"""
    try:
        import akshare as ak
    except ImportError:  # pragma: no cover
        return {"ok": False, "error": "数据源组件未安装（akshare）"}
    items: list[dict] = []
    errors: list[str] = []

    # 公告（东方财富）
    try:
        df = ak.stock_announcement_em(symbol=code)
        for _, row in df.head(limit).iterrows():
            items.append(
                {
                    "title": str(row.get("公告标题", "")),
                    "date": str(row.get("公告日期", ""))[:10],
                    "url": str(row.get("网址", "") or ""),
                    "source": "公告",
                }
            )
    except Exception as e:  # noqa: BLE001
        errors.append(f"公告获取失败：{e}")

    # 个股新闻（东方财富）
    try:
        df = ak.stock_news_em(symbol=code)
        for _, row in df.head(limit).iterrows():
            items.append(
                {
                    "title": str(row.get("新闻标题", "")),
                    "date": str(row.get("发布时间", ""))[:10],
                    "url": str(row.get("新闻链接", "") or ""),
                    "source": "新闻",
                }
            )
    except Exception as e:  # noqa: BLE001
        errors.append(f"新闻获取失败：{e}")

    if not items:
        return {"ok": False, "error": "；".join(errors) or "未获取到数据（网络可能受限，稍后重试）"}

    # 入库：覆盖该项目的该代码旧记录
    with SessionLocal() as session:
        old = session.execute(
            select(Announcement).where(
                Announcement.project_id == project_id, Announcement.code == code
            )
        ).scalars().all()
        for o in old:
            session.delete(o)
        session.commit()
        stored = 0
        for it in items:
            if not it["title"] or not it["date"]:
                continue
            session.add(
                Announcement(
                    project_id=project_id,
                    code=code,
                    title=it["title"],
                    announce_date=it["date"],
                    url=it["url"] or None,
                    source=it["source"],
                    negative=_is_negative(it["title"]),
                )
            )
            stored += 1
        session.commit()

    return {"ok": True, "stored": stored, "errors": errors}


def list_announcements(project_id: int) -> dict:
    """按时间分层返回（近3天/近30天/更早，每层负面在前）。"""
    with SessionLocal() as session:
        rows = session.execute(
            select(Announcement)
            .where(Announcement.project_id == project_id)
            .order_by(Announcement.announce_date.desc())
        ).scalars().all()
    groups: dict[str, list[dict]] = {"near": [], "month": [], "older": []}
    for r in rows:
        groups[_layer(r.announce_date)].append(
            {
                "id": r.id,
                "title": r.title,
                "date": r.announce_date,
                "url": r.url,
                "source": r.source,
                "negative": r.negative,
            }
        )
    for g in groups.values():
        g.sort(key=lambda x: (not x["negative"], x["date"] or ""), reverse=False)
    return {
        "near": groups["near"],
        "month": groups["month"],
        "older": groups["older"],
        "total": len(rows),
    }


def ai_summarize(project_id: int) -> dict:
    """AI 快摘要（quick 层级）：最近发生了什么。"""
    from .ai.qa import summarize_text

    data = list_announcements(project_id)
    if data["total"] == 0:
        return {"ok": False, "error": "还没有公告数据，先点「拉取公告」"}
    lines = []
    for layer, label in (("near", "近3天"), ("month", "近30天"), ("older", "更早")):
        for it in data[layer][:15]:
            mark = "⚠" if it["negative"] else ""
            lines.append(f"[{label}] {it['date']} {it['title']} {mark}")
    result = summarize_text(
        project_id,
        "按时间顺序总结这家公司最近发生了哪些重要事项，负面事项单独列出，不超过 8 条。",
        "\n".join(lines),
    )
    if result.get("ok"):
        from .notes_service import add_manual_note

        add_manual_note(project_id, f"公告/舆情摘要（AI）：\n{result['answer']}")
    return result
