"""估值工具箱（P1-5，借鉴 Vibe-Trading：可比公司/DCF/三表 +
输入哈希版本化审计追踪——每次测算的假设输入都有指纹可回溯）。

方法：
- 可比公司法：标的归母净利润 × 可比公司 PE 均值/区间 → 隐含市值区间
- DCF：两阶段自由现金流折现，支持保守/中性/乐观三情景
"""

import hashlib
import json

from sqlalchemy import select

from .db import SessionLocal
from .db.models import Comparable, Indicator, ValuationRun


def hash_inputs(inputs: dict) -> str:
    """输入指纹（排序后 JSON 的 sha256 前 16 位）。"""
    canonical = json.dumps(inputs, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _save_run(project_id: int, method: str, inputs: dict, result: dict) -> None:
    with SessionLocal() as session:
        session.add(
            ValuationRun(
                project_id=project_id,
                method=method,
                inputs_json=json.dumps(inputs, ensure_ascii=False),
                inputs_hash=hash_inputs(inputs),
                result_json=json.dumps(result, ensure_ascii=False),
            )
        )
        session.commit()


def list_runs(project_id: int) -> list[dict]:
    with SessionLocal() as session:
        rows = session.execute(
            select(ValuationRun)
            .where(ValuationRun.project_id == project_id)
            .order_by(ValuationRun.created_at.desc())
            .limit(20)
        ).scalars().all()
        return [
            {
                "id": r.id,
                "method": r.method,
                "inputs": json.loads(r.inputs_json),
                "inputs_hash": r.inputs_hash,
                "result": json.loads(r.result_json),
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
            }
            for r in rows
        ]


def _latest_np(project_id: int) -> tuple[str | None, float | None]:
    """标的最近整年的归母净利润（万元）——可比公司法的基础。"""
    with SessionLocal() as session:
        rows = session.execute(
            select(Indicator).where(
                Indicator.project_id == project_id,
                Indicator.name == "归属于母公司股东的净利润",
            )
        ).scalars().all()
    annual = {int(r.period[:4]): r.value for r in rows if r.period.endswith("年度")}
    if not annual:
        return None, None
    year = max(annual)
    return f"{year}年度", annual[year]


def comparable_valuation(project_id: int, refresh: bool = False) -> dict:
    """可比公司法：标的归母净利润 × 可比 PE。"""
    from .market.source import get_comparison

    period, target_np = _latest_np(project_id)
    with SessionLocal() as session:
        peers = session.execute(
            select(Comparable).where(Comparable.project_id == project_id)
        ).scalars().all()
    if not peers:
        return {"ok": False, "error": "尚未添加可比公司：请先在「同行对比」中添加同行业公司"}
    if target_np is None or target_np <= 0:
        return {"ok": False, "error": f"标的归母净利润缺失或为负（{target_np}），不适用 PE 估值"}

    comp = get_comparison([p.code for p in peers], refresh=refresh)
    rows = []
    pes = []
    for c in comp["companies"]:
        pe = (c.get("valuation") or {}).get("pe")
        implied = target_np * pe if pe else None
        if pe:
            pes.append(pe)
        rows.append(
            {
                "peer": c.get("name", c["code"]),
                "pe": pe,
                "implied_value_wan": round(implied, 0) if implied else None,
            }
        )
    if not pes:
        return {"ok": False, "error": "可比公司 PE 数据缺失（行情接口今日可能受限，稍后重试）"}
    avg_pe = sum(pes) / len(pes)
    min_pe, max_pe = min(pes), max(pes)
    result = {
        "ok": True,
        "method": "comparable",
        "basis": f"标的 {period} 归母净利润 {target_np:,.2f} 万元",
        "peer_rows": rows,
        "avg_pe": round(avg_pe, 2),
        "implied_range_wan": [round(target_np * min_pe), round(target_np * max_pe)],
        "implied_avg_wan": round(target_np * avg_pe),
    }
    inputs = {"period": period, "target_np_wan": target_np, "peers": [p.code for p in peers]}
    _save_run(project_id, "comparable", inputs, result)
    return result


# DCF 情景预设（保守/中性/乐观：增速与折现率组合）
SCENARIOS = {
    "保守": {"growth": 0.05, "wacc": 0.12, "terminal_growth": 0.01},
    "中性": {"growth": 0.12, "wacc": 0.10, "terminal_growth": 0.02},
    "乐观": {"growth": 0.20, "wacc": 0.09, "terminal_growth": 0.03},
}


def _dcf(base_fcf: float, growth: float, wacc: float, terminal_growth: float,
         shares: float, years: int = 5) -> dict:
    """两阶段 DCF：显性期 + 永续期（戈登模型）。金额单位：万元。"""
    fcf = base_fcf
    pv = 0.0
    details = []
    for i in range(1, years + 1):
        fcf = fcf * (1 + growth)
        pv_i = fcf / (1 + wacc) ** i
        pv += pv_i
        details.append({"year": i, "fcf": round(fcf, 2), "pv": round(pv_i, 2)})
    terminal_fcf = fcf * (1 + terminal_growth)
    if wacc <= terminal_growth:
        terminal_value = terminal_fcf / (wacc - terminal_growth + 1e-6)
    else:
        terminal_value = terminal_fcf / (wacc - terminal_growth)
    pv_terminal = terminal_value / (1 + wacc) ** years
    equity_value = pv + pv_terminal
    return {
        "details": details,
        "terminal_value": round(terminal_value, 2),
        "pv_terminal": round(pv_terminal, 2),
        "equity_value_wan": round(equity_value, 2),
        "per_share": round(equity_value / shares, 2) if shares > 0 else None,
    }


def dcf_valuation(project_id: int, inputs: dict) -> dict:
    """DCF 估值：自定义假设 + 三情景自动测算。"""
    required = ("base_fcf", "growth", "wacc", "terminal_growth", "shares")
    for k in required:
        if k not in inputs:
            return {"ok": False, "error": f"缺少输入参数：{k}"}
    try:
        base_fcf = float(inputs["base_fcf"])
        growth = float(inputs["growth"])
        wacc = float(inputs["wacc"])
        terminal_growth = float(inputs["terminal_growth"])
        shares = float(inputs["shares"])
    except (TypeError, ValueError):
        return {"ok": False, "error": "输入参数必须为数字"}
    if base_fcf <= 0 or shares <= 0:
        return {"ok": False, "error": "基期自由现金流与股本必须为正数"}

    custom = _dcf(base_fcf, growth, wacc, terminal_growth, shares)
    scenarios = {
        name: _dcf(base_fcf, p["growth"], p["wacc"], p["terminal_growth"], shares)
        for name, p in SCENARIOS.items()
    }
    result = {
        "ok": True,
        "method": "dcf",
        "custom": {**custom, "assumptions": inputs},
        "scenarios": {
            name: {
                "assumptions": {k: v for k, v in SCENARIOS[name].items() if k != "shares"},
                "equity_value_wan": scenarios[name]["equity_value_wan"],
                "per_share": scenarios[name]["per_share"],
            }
            for name in SCENARIOS
        },
    }
    _save_run(project_id, "dcf", inputs, result)
    return result
