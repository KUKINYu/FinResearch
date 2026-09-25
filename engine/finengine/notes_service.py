"""研究记忆与反思（P1-4）。

- 新资料解析完成后自动生成"数据更新对比"笔记（无需 AI，纯结构化对比）：
  新增期间 / 数值变化，标注出处页码
- AI 反思：结合历史笔记与当前异常清单，用快速模型生成"值得关注的变化"
- 用户可随时手写笔记
"""

from sqlalchemy import select

from .db import SessionLocal
from .db.models import File, FinancialLine, Indicator, ResearchNote

# 对比时关注的指标（按重要度排序）
WATCH_INDICATORS = (
    "营业收入", "净利润", "归属于母公司股东的净利润", "毛利率", "净利率",
    "加权平均净资产收益率", "经营活动产生的现金流量净额",
    "应收账款", "存货", "有息负债", "研发费用",
)


def add_data_update_note(project_id: int, file_id: int) -> ResearchNote | None:
    """新文件解析后：对比该文件提取行与项目既有指标，生成结构化笔记。"""
    with SessionLocal() as session:
        f = session.get(File, file_id)
        lines = session.execute(
            select(FinancialLine).where(FinancialLine.file_id == file_id)
        ).scalars().all()
        existing = session.execute(
            select(Indicator).where(Indicator.project_id == project_id)
        ).scalars().all()
        existing_map = {(i.name, i.period): i for i in existing}

        added: list[str] = []
        changed: list[str] = []
        for line in lines:
            if line.indicator not in WATCH_INDICATORS:
                continue
            key = (line.indicator, line.period)
            old = existing_map.get(key)
            if old is None:
                added.append(
                    f"{line.indicator} {line.period}：{line.value:,.2f}{line.unit}（第{line.page_no}页）"
                )
            elif abs(old.value - line.value) > max(abs(old.value) * 0.001, 1e-9):
                changed.append(
                    f"{line.indicator} {line.period}：{old.value:,.2f} → {line.value:,.2f}{line.unit}（第{line.page_no}页）"
                )

        if not added and not changed:
            return None
        parts = [f"资料《{f.original_name if f else ''}》解析完成："]
        if added:
            parts.append("新增数据：" + "；".join(added[:12]))
        if changed:
            parts.append("数据变化：" + "；".join(changed[:8]))
        note = ResearchNote(project_id=project_id, kind="data_update", content="\n".join(parts))
        session.add(note)
        session.commit()
        session.refresh(note)
        return note


def list_notes(project_id: int) -> list[dict]:
    with SessionLocal() as session:
        rows = session.execute(
            select(ResearchNote)
            .where(ResearchNote.project_id == project_id)
            .order_by(ResearchNote.created_at.desc())
        ).scalars().all()
        return [
            {
                "id": r.id,
                "kind": r.kind,
                "content": r.content,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
            }
            for r in rows
        ]


def add_manual_note(project_id: int, content: str) -> dict:
    with SessionLocal() as session:
        note = ResearchNote(project_id=project_id, kind="manual", content=content)
        session.add(note)
        session.commit()
        session.refresh(note)
        return {
            "id": note.id,
            "kind": note.kind,
            "content": note.content,
            "created_at": note.created_at.strftime("%Y-%m-%d %H:%M") if note.created_at else "",
        }


def delete_note(note_id: int) -> None:
    with SessionLocal() as session:
        note = session.get(ResearchNote, note_id)
        if note:
            session.delete(note)
            session.commit()


def ai_reflection(project_id: int) -> dict:
    """AI 反思：历史笔记 + 当前异常 → 快速模型总结"值得关注的变化"。"""
    from .ai.qa import summarize_text

    with SessionLocal() as session:
        notes = session.execute(
            select(ResearchNote)
            .where(ResearchNote.project_id == project_id)
            .order_by(ResearchNote.created_at.desc())
            .limit(10)
        ).scalars().all()
        from .db.models import Anomaly

        anomalies = session.execute(
            select(Anomaly).where(Anomaly.project_id == project_id)
        ).scalars().all()
    context_parts = ["【历史研究笔记】"]
    context_parts.extend(f"- ({n.created_at.strftime('%m-%d') if n.created_at else ''}) {n.content[:300]}" for n in notes)
    context_parts.append("【当前异常】")
    context_parts.extend(f"- {a.title}：{a.description[:200]}" for a in anomalies)
    if not notes and not anomalies:
        return {"ok": False, "error": "还没有研究笔记或异常数据，先上传资料或写几条笔记"}
    result = summarize_text(
        project_id,
        "对比此前的研究结论与最新数据/异常，列出 3-5 条最值得关注的变化或风险点，每条不超过两句话。",
        "\n".join(context_parts),
    )
    if result.get("ok"):
        with SessionLocal() as session:
            note = ResearchNote(
                project_id=project_id,
                kind="reflection",
                content=f"AI 反思：\n{result['answer']}",
            )
            session.add(note)
            session.commit()
    return result
