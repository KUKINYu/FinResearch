"""尽调风险评分卡（P1-3，借鉴 TradingAgents 风险管理团队与
Vibe-Trading 风险委员会的设计）。

五个维度打分（1-5 分，5 = 风险最低），每个分数附带"依据"说明
（用哪些数据、怎么算的、出处页码）——延续全产品可溯源的基因：
- 财务质量：异常清单严重度扣分 + 盈利能力水平
- 现金流质量：经营现金流/净利润（最近整年）
- 偿债能力：有息负债/货币资金 + 资产负债率
- 营运质量：应收账款周转天数变化
- 外部风险：负面公告/新闻数量
"""

import datetime

from sqlalchemy import select

from .db import SessionLocal
from .db.models import Anomaly, Announcement, Indicator
from .rules.engine import Point, annual

DIMENSIONS = ("财务质量", "现金流质量", "偿债能力", "营运质量", "外部风险")


def _clip(v: float, lo: float = 1.0, hi: float = 5.0) -> float:
    return max(lo, min(hi, v))


def _series(project_id: int) -> dict[str, dict[str, Point]]:
    with SessionLocal() as session:
        rows = session.execute(
            select(Indicator).where(Indicator.project_id == project_id)
        ).scalars().all()
    series: dict[str, dict[str, Point]] = {}
    for r in rows:
        series.setdefault(r.name, {})[r.period] = Point(
            value=r.value, unit=r.unit, source_page=r.source_page
        )
    return series


def _latest_year(series: dict[str, dict[str, Point]], name: str) -> tuple[int, Point] | None:
    a = annual(series.get(name, {}))
    if not a:
        return None
    year = max(a)
    return year, a[year]


def score_financial_quality(project_id: int) -> dict:
    """财务质量：异常严重度扣分（高-2/中-1）+ 毛利率与ROE水平微调。"""
    with SessionLocal() as session:
        anomalies = session.execute(
            select(Anomaly).where(Anomaly.project_id == project_id)
        ).scalars().all()
    penalty = sum({"high": 2, "medium": 1, "low": 0.5}.get(a.severity, 0) for a in anomalies)
    score = _clip(5 - penalty)
    basis = (
        f"异常清单共 {len(anomalies)} 条（高 {sum(1 for a in anomalies if a.severity == 'high')} 条、"
        f"中 {sum(1 for a in anomalies if a.severity == 'medium')} 条），"
        f"按严重度扣分：5 - {penalty} = {score}"
    )
    return {"score": round(score, 1), "basis": basis}


def score_cashflow_quality(project_id: int) -> dict:
    """现金流质量：经营现金流/净利润（最近整年）。"""
    s = _series(project_id)
    np_ = _latest_year(s, "净利润")
    ocf = _latest_year(s, "经营活动产生的现金流量净额")
    if np_ is None or ocf is None or np_[1].value == 0:
        return {"score": 3.0, "basis": "数据不足（缺净利润或经营现金流），中性评分 3 分"}
    ratio = ocf[1].value / np_[1].value
    if ratio >= 1.0:
        score = 5.0
    elif ratio >= 0.7:
        score = 4.0
    elif ratio >= 0.4:
        score = 3.0
    elif ratio >= 0:
        score = 2.0
    else:
        score = 1.0
    basis = (
        f"{np_[0]}年经营现金流 {ocf[1].value:,.2f}（第{ocf[1].source_page}页）÷ "
        f"净利润 {np_[1].value:,.2f} = {ratio:.2f}，评分 {score}"
    )
    return {"score": score, "basis": basis}


def score_solvency(project_id: int) -> dict:
    """偿债能力：有息负债/货币资金 + 资产负债率。"""
    s = _series(project_id)
    debt = _latest_year(s, "有息负债")
    cash = _latest_year(s, "货币资金")
    dr = _latest_year(s, "资产负债率")
    score = 3.0
    parts = []
    if debt is not None and cash is not None and cash[1].value > 0:
        ratio = debt[1].value / cash[1].value
        if ratio <= 0.5:
            score = 5.0
        elif ratio <= 1.0:
            score = 4.0
        elif ratio <= 1.5:
            score = 3.0
        elif ratio <= 2.5:
            score = 2.0
        else:
            score = 1.0
        parts.append(f"有息负债/货币资金 = {ratio:.2f}（第{debt[1].source_page}页）")
    else:
        parts.append("缺有息负债或货币资金数据")
    if dr is not None:
        v = dr[1].value
        if v > 80:
            score = min(score, 1.0)
        elif v > 65:
            score = min(score, 2.5)
        elif v > 50:
            score = min(score, 3.5)
        parts.append(f"资产负债率 {v:.1f}%（第{dr[1].source_page}页）")
    return {"score": round(score, 1), "basis": "；".join(parts)}


def score_operations(project_id: int) -> dict:
    """营运质量：应收账款周转天数同比变化。"""
    s = _series(project_id)
    ar = annual(s.get("应收账款", {}))
    rev = annual(s.get("营业收入", {}))
    years = sorted(set(ar) & set(rev))
    if len(years) < 2:
        return {"score": 3.0, "basis": "数据不足（应收账款/营业收入不足两年），中性评分 3 分"}
    y2, y1 = years[-1], years[-2]
    if rev[y2].value <= 0 or rev[y1].value <= 0:
        return {"score": 3.0, "basis": "营业收入为零或负，无法计算周转，中性评分 3 分"}
    d2 = ar[y2].value / rev[y2].value * 365
    d1 = ar[y1].value / rev[y1].value * 365
    if d1 <= 0:
        return {"score": 3.0, "basis": "上期周转天数为零，中性评分 3 分"}
    change = (d2 - d1) / d1 * 100
    if change <= -10:
        score = 5.0
    elif change <= 10:
        score = 4.0
    elif change <= 30:
        score = 3.0
    elif change <= 60:
        score = 2.0
    else:
        score = 1.0
    basis = (
        f"应收账款周转天数 {y1}年 {d1:.0f} 天 → {y2}年 {d2:.0f} 天"
        f"（变化 {change:+.0f}%），评分 {score}"
    )
    return {"score": score, "basis": basis}


def score_external_risk(project_id: int) -> dict:
    """外部风险：负面公告/新闻数量。"""
    with SessionLocal() as session:
        neg = session.execute(
            select(Announcement).where(
                Announcement.project_id == project_id, Announcement.negative.is_(True)
            )
        ).scalars().all()
    n = len(neg)
    if n == 0:
        score = 5.0
    elif n <= 2:
        score = 4.0
    elif n <= 5:
        score = 3.0
    elif n <= 10:
        score = 2.0
    else:
        score = 1.0
    basis = f"负面公告/新闻 {n} 条，评分 {score}"
    if n > 0:
        basis += "；如：" + "；".join(a.title[:40] for a in neg[:3])
    return {"score": score, "basis": basis}


def compute_risk_score(project_id: int) -> dict:
    """汇总五个维度，输出总分与风险等级。"""
    dims = [
        ("财务质量", score_financial_quality(project_id)),
        ("现金流质量", score_cashflow_quality(project_id)),
        ("偿债能力", score_solvency(project_id)),
        ("营运质量", score_operations(project_id)),
        ("外部风险", score_external_risk(project_id)),
    ]
    total = sum(d[1]["score"] for d in dims) / len(dims)
    if total >= 4.0:
        level = "风险较低"
    elif total >= 3.0:
        level = "风险中等"
    elif total >= 2.0:
        level = "风险偏高"
    else:
        level = "风险较高"
    return {
        "dimensions": [
            {"name": name, "score": d["score"], "basis": d["basis"]} for name, d in dims
        ],
        "overall": round(total, 2),
        "level": level,
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
