"""财务异常检测规则引擎（M5 核心卖点）。

设计原则：
- 规则即数据：每条规则 = 人话标题 + 说明 + 严重程度 + 默认阈值 + 检查函数
- 每条异常必须输出：结论（人话）+ 计算过程（中文公式与数据明细）+
  涉及数据点（含出处页码）——"不只是告诉你存在异常，还告诉你
  由哪些数据算出、来自原文哪一页"
- 检查基于整年期间（1-6月期间数不参与同比）

阈值默认值保守（宁可多报不误漏），P1 提供调节界面。
"""

from dataclasses import dataclass, field
from typing import Callable

# ---- 输入数据结构 ----

@dataclass
class Point:
    """一个指标数据点（带出处）。"""

    value: float
    unit: str
    source_file_id: int | None = None
    source_page: int | None = None

    def ref(self) -> str:
        """出处引用文案。"""
        return f"（第{self.source_page}页）" if self.source_page else ""


# 指标序列：指标名 → 期间 → 数据点
Series = dict[str, dict[str, Point]]


def annual(series: dict[str, Point]) -> dict[int, Point]:
    """只取整年期间，按年份升序返回 {年份: 数据点}。"""
    out: dict[int, Point] = {}
    for period, p in series.items():
        if period.endswith("年度"):
            out[int(period[:4])] = p
    return dict(sorted(out.items()))


def fmt(v: float | None, unit: str = "") -> str:
    if v is None:
        return "无数据"
    return f"{v:,.2f}{unit}"


def growth(cur: float, prev: float) -> float | None:
    """增长率（%）。prev 为 0 或负数时无法计算。"""
    if prev == 0:
        return None
    return (cur - prev) / prev * 100


def make_anomaly(
    rule_id: str,
    title: str,
    severity: str,
    description: str,
    points: list[dict],
) -> dict:
    return {
        "rule_id": rule_id,
        "title": title,
        "severity": severity,
        "description": description,
        "data_points": points,
    }


def pt(indicator: str, period: str, p: Point) -> dict:
    """数据点转 JSON（含出处，界面点击可跳原文）。"""
    return {
        "indicator": indicator,
        "period": period,
        "value": p.value,
        "unit": p.unit,
        "source_file_id": p.source_file_id,
        "source_page": p.source_page,
    }


def pair_points(
    series: Series, name: str, year: int, prev_year: int
) -> tuple[Point | None, Point | None]:
    """取某指标相邻两年的数据点（从整年序列）。"""
    a = annual(series.get(name, {}))
    return a.get(prev_year), a.get(year)


# ---- 规则定义 ----

RULE_DEFS: list[tuple[str, str, str, Callable[[Series], list[dict]]]] = []


def rule(rule_id: str, title: str, severity: str):
    """注册规则（装饰器）。"""

    def deco(fn: Callable[[Series], list[dict]]):
        RULE_DEFS.append((rule_id, title, severity, fn))
        return fn

    return deco


@rule("ar_vs_revenue_growth", "应收账款增速明显快于营业收入", "high")
def r_ar_vs_revenue(s: Series) -> list[dict]:
    """应收账款增速 - 营业收入增速 > 20 个百分点。"""
    out = []
    ar = annual(s.get("应收账款", {}))
    rev = annual(s.get("营业收入", {}))
    for year in ar:
        prev = year - 1
        if prev not in ar or prev not in rev or year not in rev:
            continue
        ar_g = growth(ar[year].value, ar[prev].value)
        rev_g = growth(rev[year].value, rev[prev].value)
        if ar_g is None or rev_g is None or rev_g <= 0:
            continue
        diff = ar_g - rev_g
        if diff > 20:
            out.append(
                make_anomaly(
                    "ar_vs_revenue_growth",
                    f"{year}年应收账款增速明显快于营业收入",
                    "high",
                    f"{year}年度应收账款 {fmt(ar[year].value, ar[year].unit)}{ar[year].ref()}，"
                    f"较上年 {fmt(ar[prev].value, ar[prev].unit)} 增长 {ar_g:.1f}%；"
                    f"营业收入 {fmt(rev[year].value, rev[year].unit)}{rev[year].ref()} 仅增长 {rev_g:.1f}%。"
                    f"增速差 {diff:.1f} 个百分点，超过 20 个百分点的关注阈值，"
                    f"可能存在放宽信用政策、回款放缓或提前确认收入的风险。",
                    [
                        pt("应收账款", f"{year}年度", ar[year]),
                        pt("应收账款", f"{prev}年度", ar[prev]),
                        pt("营业收入", f"{year}年度", rev[year]),
                        pt("营业收入", f"{prev}年度", rev[prev]),
                    ],
                )
            )
    return out


@rule("inventory_vs_revenue_growth", "存货增速明显快于营业收入", "high")
def r_inventory_vs_revenue(s: Series) -> list[dict]:
    """存货增速 - 营业收入增速 > 20 个百分点。"""
    out = []
    inv = annual(s.get("存货", {}))
    rev = annual(s.get("营业收入", {}))
    for year in inv:
        prev = year - 1
        if prev not in inv or prev not in rev or year not in rev:
            continue
        inv_g = growth(inv[year].value, inv[prev].value)
        rev_g = growth(rev[year].value, rev[prev].value)
        if inv_g is None or rev_g is None or rev_g <= 0:
            continue
        diff = inv_g - rev_g
        if diff > 20:
            out.append(
                make_anomaly(
                    "inventory_vs_revenue_growth",
                    f"{year}年存货增速明显快于营业收入",
                    "high",
                    f"{year}年度存货 {fmt(inv[year].value, inv[year].unit)}{inv[year].ref()}，"
                    f"较上年增长 {inv_g:.1f}%；营业收入仅增长 {rev_g:.1f}%。"
                    f"增速差 {diff:.1f} 个百分点，超过 20 个百分点的关注阈值，"
                    f"可能存在产品滞销、存货积压或跌价准备不足的风险。",
                    [
                        pt("存货", f"{year}年度", inv[year]),
                        pt("存货", f"{prev}年度", inv[prev]),
                        pt("营业收入", f"{year}年度", rev[year]),
                        pt("营业收入", f"{prev}年度", rev[prev]),
                    ],
                )
            )
    return out


@rule("profit_vs_ocf_growth", "净利润增长但经营现金流未同步", "high")
def r_profit_vs_ocf(s: Series) -> list[dict]:
    """净利润增速 > 20%，且经营现金流增速落后 > 20 个百分点（或现金流下滑）。"""
    out = []
    np_ = annual(s.get("净利润", {}))
    ocf = annual(s.get("经营活动产生的现金流量净额", {}))
    for year in np_:
        prev = year - 1
        if prev not in np_ or prev not in ocf or year not in ocf:
            continue
        np_g = growth(np_[year].value, np_[prev].value)
        ocf_g = growth(ocf[year].value, ocf[prev].value)
        if np_g is None or np_g <= 20 or ocf_g is None:
            continue
        if ocf_g < np_g - 20:
            ocf_text = f"下降 {-ocf_g:.1f}%" if ocf_g < 0 else f"仅增长 {ocf_g:.1f}%"
            out.append(
                make_anomaly(
                    "profit_vs_ocf_growth",
                    f"{year}年净利润增长但经营现金流未同步",
                    "high",
                    f"{year}年度净利润 {fmt(np_[year].value, np_[year].unit)}{np_[year].ref()}，"
                    f"较上年增长 {np_g:.1f}%；但经营活动现金流量净额 "
                    f"{fmt(ocf[year].value, ocf[year].unit)}{ocf[year].ref()} {ocf_text}。"
                    f"两者差距超过 20 个百分点，利润的现金含量下降，"
                    f"需关注应收款项回款、收入确认时点或利润质量。",
                    [
                        pt("净利润", f"{year}年度", np_[year]),
                        pt("净利润", f"{prev}年度", np_[prev]),
                        pt("经营活动产生的现金流量净额", f"{year}年度", ocf[year]),
                        pt("经营活动产生的现金流量净额", f"{prev}年度", ocf[prev]),
                    ],
                )
            )
    return out


@rule("ocf_np_divergence", "经营现金流与净利润长期背离", "high")
def r_ocf_np_divergence(s: Series) -> list[dict]:
    """连续两年 经营现金流/净利润 < 0.5（或现金流为负）。"""
    np_ = annual(s.get("净利润", {}))
    ocf = annual(s.get("经营活动产生的现金流量净额", {}))
    bad_years: list[tuple[int, float]] = []
    for year in np_:
        if year not in ocf or np_[year].value == 0:
            continue
        ratio = ocf[year].value / np_[year].value
        if ratio < 0.5:
            bad_years.append((year, ratio))
    if len(bad_years) >= 2 and bad_years[-1][0] - bad_years[-2][0] == 1:
        y1, r1 = bad_years[-2]
        y2, r2 = bad_years[-1]
        return [
            make_anomaly(
                "ocf_np_divergence",
                f"{y1}-{y2}年经营现金流与净利润持续背离",
                "high",
                f"{y1}年度经营现金流/净利润 = {r1:.2f}，{y2}年度 = {r2:.2f}，"
                f"连续两年低于 0.5 的阈值（经营现金流 "
                f"{fmt(ocf[y1].value, ocf[y1].unit)}{ocf[y1].ref()} vs 净利润 "
                f"{fmt(np_[y1].value, np_[y1].unit)}；"
                f"{fmt(ocf[y2].value, ocf[y2].unit)}{ocf[y2].ref()} vs "
                f"{fmt(np_[y2].value, np_[y2].unit)}）。"
                f"利润长期未转化为现金，需重点关注应收款质量、存货占用或收入确认政策。",
                [
                    pt("经营活动产生的现金流量净额", f"{y1}年度", ocf[y1]),
                    pt("净利润", f"{y1}年度", np_[y1]),
                    pt("经营活动产生的现金流量净额", f"{y2}年度", ocf[y2]),
                    pt("净利润", f"{y2}年度", np_[y2]),
                ],
            )
        ]
    return []


@rule("gross_margin_change", "毛利率出现异常变化", "medium")
def r_gross_margin_change(s: Series) -> list[dict]:
    """毛利率同比变动超过 5 个百分点。"""
    out = []
    gm = annual(s.get("毛利率", {}))
    for year in gm:
        prev = year - 1
        if prev not in gm:
            continue
        diff = gm[year].value - gm[prev].value
        if abs(diff) > 5:
            direction = "上升" if diff > 0 else "下降"
            out.append(
                make_anomaly(
                    "gross_margin_change",
                    f"{year}年毛利率{direction} {abs(diff):.1f} 个百分点",
                    "medium",
                    f"{year}年度毛利率 {fmt(gm[year].value, '%')}{gm[year].ref()}，"
                    f"较上年 {fmt(gm[prev].value, '%')} {direction} {abs(diff):.1f} 个百分点，"
                    f"超过 5 个百分点的关注阈值。需关注产品结构变化、原材料价格、"
                    f"定价策略或成本核算口径变化。",
                    [
                        pt("毛利率", f"{year}年度", gm[year]),
                        pt("毛利率", f"{prev}年度", gm[prev]),
                    ],
                )
            )
    return out


@rule("debt_ratio_change", "资产负债率明显变化", "medium")
def r_debt_ratio_change(s: Series) -> list[dict]:
    """资产负债率同比变动超过 10 个百分点。"""
    out = []
    dr = annual(s.get("资产负债率", {}))
    for year in dr:
        prev = year - 1
        if prev not in dr:
            continue
        diff = dr[year].value - dr[prev].value
        if abs(diff) > 10:
            direction = "上升" if diff > 0 else "下降"
            out.append(
                make_anomaly(
                    "debt_ratio_change",
                    f"{year}年资产负债率{direction} {abs(diff):.1f} 个百分点",
                    "medium",
                    f"{year}年度资产负债率 {fmt(dr[year].value, '%')}{dr[year].ref()}，"
                    f"较上年 {fmt(dr[prev].value, '%')} {direction} {abs(diff):.1f} 个百分点，"
                    f"超过 10 个百分点的关注阈值。需关注融资结构、大额借款或分红等重大变化。",
                    [
                        pt("资产负债率", f"{year}年度", dr[year]),
                        pt("资产负债率", f"{prev}年度", dr[prev]),
                    ],
                )
            )
    return out


@rule("interest_debt_cash_coverage", "有息负债对货币资金覆盖不足", "medium")
def r_interest_debt_cash(s: Series) -> list[dict]:
    """最近一年 有息负债/货币资金 > 1.2。"""
    debt = annual(s.get("有息负债", {}))
    cash = annual(s.get("货币资金", {}))
    if not debt or not cash:
        return []
    year = max(set(debt) & set(cash))
    ratio = debt[year].value / cash[year].value if cash[year].value else None
    if ratio is not None and ratio > 1.2:
        return [
            make_anomaly(
                "interest_debt_cash_coverage",
                f"{year}年有息负债超过货币资金",
                "medium",
                f"{year}年度有息负债 {fmt(debt[year].value, debt[year].unit)}{debt[year].ref()}，"
                f"货币资金 {fmt(cash[year].value, cash[year].unit)}{cash[year].ref()}，"
                f"有息负债/货币资金 = {ratio:.2f}，超过 1.2 的阈值，"
                f"货币资金对有息负债的覆盖能力偏弱，需关注偿债安排与再融资能力。",
                [
                    pt("有息负债", f"{year}年度", debt[year]),
                    pt("货币资金", f"{year}年度", cash[year]),
                ],
            )
        ]
    return []


@rule("rd_ratio_change", "研发费用占营收比例骤变", "low")
def r_rd_ratio_change(s: Series) -> list[dict]:
    """研发费用/营业收入 同比变动超过 5 个百分点。"""
    out = []
    rd = annual(s.get("研发费用", {}))
    rev = annual(s.get("营业收入", {}))
    for year in rd:
        prev = year - 1
        if year not in rev or prev not in rev or prev not in rd or rev[prev].value == 0 or rev[year].value == 0:
            continue
        r_cur = rd[year].value / rev[year].value * 100
        r_prev = rd[prev].value / rev[prev].value * 100
        diff = r_cur - r_prev
        if abs(diff) > 5:
            direction = "上升" if diff > 0 else "下降"
            out.append(
                make_anomaly(
                    "rd_ratio_change",
                    f"{year}年研发费用占营收比例{direction} {abs(diff):.1f} 个百分点",
                    "low",
                    f"{year}年度研发费用 {fmt(rd[year].value, rd[year].unit)}{rd[year].ref()}，"
                    f"占营业收入比例 {r_cur:.1f}%；上年为 {r_prev:.1f}%，"
                    f"{direction} {abs(diff):.1f} 个百分点。"
                    f"需关注研发投入节奏、资本化处理或收入结构变化。",
                    [
                        pt("研发费用", f"{year}年度", rd[year]),
                        pt("营业收入", f"{year}年度", rev[year]),
                        pt("研发费用", f"{prev}年度", rd[prev]),
                        pt("营业收入", f"{prev}年度", rev[prev]),
                    ],
                )
            )
    return out


@rule("revenue_vs_cash_received", "营业收入与销售收现背离", "high")
def r_revenue_vs_cash(s: Series) -> list[dict]:
    """最近一年 销售商品提供劳务收到的现金/营业收入 < 0.7。"""
    rev = annual(s.get("营业收入", {}))
    cash = annual(s.get("销售商品、提供劳务收到的现金", {}))
    if not rev or not cash:
        return []
    year = max(set(rev) & set(cash))
    ratio = cash[year].value / rev[year].value if rev[year].value else None
    if ratio is not None and ratio < 0.7:
        return [
            make_anomaly(
                "revenue_vs_cash_received",
                f"{year}年营业收入与销售收现背离",
                "high",
                f"{year}年度销售商品、提供劳务收到的现金 "
                f"{fmt(cash[year].value, cash[year].unit)}{cash[year].ref()}，"
                f"营业收入 {fmt(rev[year].value, rev[year].unit)}{rev[year].ref()}，"
                f"收现比 = {ratio:.2f}，低于 0.7 的阈值。"
                f"收入与回款明显不匹配，需关注收入确认政策、应收票据大量背书"
                f"转让或客户回款能力。",
                [
                    pt("销售商品、提供劳务收到的现金", f"{year}年度", cash[year]),
                    pt("营业收入", f"{year}年度", rev[year]),
                ],
            )
        ]
    return []


@rule("ar_days_deterioration", "应收账款周转天数恶化", "medium")
def r_ar_days(s: Series) -> list[dict]:
    """应收账款周转天数同比增长超过 30%。"""
    out = []
    ar = annual(s.get("应收账款", {}))
    rev = annual(s.get("营业收入", {}))
    for year in ar:
        prev = year - 1
        if year not in rev or prev not in rev or prev not in ar or rev[year].value <= 0 or rev[prev].value <= 0:
            continue
        days_cur = ar[year].value / rev[year].value * 365
        days_prev = ar[prev].value / rev[prev].value * 365
        if days_prev <= 0:
            continue
        g = (days_cur - days_prev) / days_prev * 100
        if g > 30:
            out.append(
                make_anomaly(
                    "ar_days_deterioration",
                    f"{year}年应收账款周转天数明显拉长",
                    "medium",
                    f"{year}年度应收账款周转天数约 {days_cur:.0f} 天"
                    f"（应收账款 {fmt(ar[year].value, ar[year].unit)}{ar[year].ref()} ÷ "
                    f"营业收入 {fmt(rev[year].value, rev[year].unit)} × 365），"
                    f"上年约 {days_prev:.0f} 天，拉长 {g:.0f}%，超过 30% 的阈值。"
                    f"回款速度明显放缓，需关注客户信用政策与坏账风险。",
                    [
                        pt("应收账款", f"{year}年度", ar[year]),
                        pt("营业收入", f"{year}年度", rev[year]),
                        pt("应收账款", f"{prev}年度", ar[prev]),
                        pt("营业收入", f"{prev}年度", rev[prev]),
                    ],
                )
            )
    return out


def run_rules(series: Series) -> list[dict]:
    """对项目指标序列运行全部规则，返回异常列表。"""
    anomalies: list[dict] = []
    for rule_id, title, severity, fn in RULE_DEFS:
        try:
            anomalies.extend(fn(series))
        except Exception as e:  # noqa: BLE001 单条规则失败不影响其他规则
            anomalies.append(
                make_anomaly(rule_id, title, "low", f"规则执行失败：{e}", [])
            )
    return anomalies
