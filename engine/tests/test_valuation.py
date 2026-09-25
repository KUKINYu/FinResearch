"""估值工具箱测试（P1-5）。"""

from finengine.valuation import _dcf, hash_inputs


def test_hash_inputs_stable_and_order_independent():
    a = hash_inputs({"b": 2, "a": 1})
    b = hash_inputs({"a": 1, "b": 2})
    assert a == b
    assert hash_inputs({"a": 2}) != a
    assert len(a) == 16


def test_dcf_math():
    """零增长永续：value = FCF / WACC，与戈登公式一致。"""
    r = _dcf(base_fcf=1000, growth=0.0, wacc=0.10, terminal_growth=0.0, shares=1000)
    assert abs(r["equity_value_wan"] - 10000) < 1  # 1000/0.10
    assert abs(r["per_share"] - 10.0) < 0.01


def test_dcf_growth_increases_value():
    flat = _dcf(1000, 0.0, 0.10, 0.0, 1000)
    growing = _dcf(1000, 0.10, 0.10, 0.0, 1000)
    assert growing["equity_value_wan"] > flat["equity_value_wan"]


def test_dcf_higher_wacc_lowers_value():
    low_wacc = _dcf(1000, 0.10, 0.08, 0.02, 1000)
    high_wacc = _dcf(1000, 0.10, 0.15, 0.02, 1000)
    assert high_wacc["equity_value_wan"] < low_wacc["equity_value_wan"]


def test_dcf_scenarios_preset():
    from finengine.valuation import SCENARIOS

    assert set(SCENARIOS) == {"保守", "中性", "乐观"}
    r_con = _dcf(1000, **SCENARIOS["保守"], shares=1000)
    r_opt = _dcf(1000, **SCENARIOS["乐观"], shares=1000)
    assert r_opt["equity_value_wan"] > r_con["equity_value_wan"]


def test_dcf_zero_shares_guard():
    r = _dcf(1000, 0.1, 0.1, 0.02, 0)
    assert r["per_share"] is None
