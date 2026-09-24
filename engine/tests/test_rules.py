"""规则引擎测试（合成序列，覆盖触发与不触发边界）。"""

from finengine.rules import run_rules
from finengine.rules.engine import Point


def series_of(name: str, values: dict[int, float], unit: str = "万元") -> dict:
    return {name: {f"{y}年度": Point(value=v, unit=unit, source_page=10) for y, v in values.items()}}


def titles(anomalies: list[dict]) -> list[str]:
    return [a["title"] for a in anomalies]


def test_ar_growth_much_faster_than_revenue():
    s = {
        **series_of("应收账款", {2024: 1000, 2025: 1500}),  # +50%
        **series_of("营业收入", {2024: 5000, 2025: 5100}),  # +2%
    }
    anomalies = run_rules(s)
    assert any("应收账款增速明显快于营业收入" in t for t in titles(anomalies))
    a = [x for x in anomalies if x["rule_id"] == "ar_vs_revenue_growth"][0]
    # 描述含计算过程与出处页码
    assert "50.0%" in a["description"] and "第10页" in a["description"]
    assert len(a["data_points"]) == 4


def test_ar_growth_normal_no_anomaly():
    s = {
        **series_of("应收账款", {2024: 1000, 2025: 1100}),
        **series_of("营业收入", {2024: 5000, 2025: 5500}),
    }
    assert all(a["rule_id"] != "ar_vs_revenue_growth" for a in run_rules(s))


def test_profit_up_but_ocf_declines():
    s = {
        **series_of("净利润", {2024: 100, 2025: 160}),  # +60%
        **series_of("经营活动产生的现金流量净额", {2024: 80, 2025: 60}),  # -25%
    }
    anomalies = run_rules(s)
    assert any("净利润增长但经营现金流未同步" in t for t in titles(anomalies))


def test_ocf_np_divergence_two_consecutive_years():
    s = {
        **series_of("净利润", {2023: 100, 2024: 120, 2025: 140}),
        **series_of("经营活动产生的现金流量净额", {2023: 30, 2024: 20, 2025: 10}),
    }
    anomalies = run_rules(s)
    assert any("经营现金流与净利润持续背离" in t for t in titles(anomalies))


def test_gross_margin_jump():
    s = series_of("毛利率", {2024: 20.0, 2025: 28.0}, unit="%")
    anomalies = run_rules(s)
    assert any("毛利率" in t and "上升" in t for t in titles(anomalies))


def test_interest_debt_exceeds_cash():
    s = {
        **series_of("有息负债", {2025: 2000}),
        **series_of("货币资金", {2025: 1000}),
    }
    anomalies = run_rules(s)
    assert any("有息负债超过货币资金" in t for t in titles(anomalies))


def test_revenue_cash_received_divergence():
    s = {
        **series_of("营业收入", {2025: 10000}),
        **series_of("销售商品、提供劳务收到的现金", {2025: 5000}),
    }
    anomalies = run_rules(s)
    assert any("销售收现背离" in t for t in titles(anomalies))


def test_ar_days_deterioration():
    # 2024: 应收/营收*365 = 73 天；2025: 219 天（+200%）
    s = {
        **series_of("应收账款", {2024: 200, 2025: 600}),
        **series_of("营业收入", {2024: 1000, 2025: 1000}),
    }
    anomalies = run_rules(s)
    assert any("周转天数" in t for t in titles(anomalies))


def test_rd_ratio_change():
    # 研发费用率 4% → 10%，+6pp，超过 5pp 阈值
    s = {
        **series_of("研发费用", {2024: 400, 2025: 1000}),
        **series_of("营业收入", {2024: 10000, 2025: 10000}),
    }
    anomalies = run_rules(s)
    assert any("研发费用占营收比例" in t for t in titles(anomalies))


def test_rule_failure_does_not_crash():
    # 空序列与零值不应抛异常
    assert run_rules({}) == []
    s = {**series_of("净利润", {2024: 0, 2025: 0}), **series_of("营业收入", {2024: 0, 2025: 0})}
    assert isinstance(run_rules(s), list)


def test_debt_ratio_change():
    s = {
        **series_of("资产负债率", {2024: 40.0, 2025: 55.0}, unit="%"),
    }
    anomalies = run_rules(s)
    assert any("资产负债率" in t for t in titles(anomalies))
