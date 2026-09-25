"""风险评分卡测试（P1-3）。"""

from finengine.risk_score import DIMENSIONS, compute_risk_score


def test_compute_on_real_project():
    """项目 1（中塑，含真实指标与异常）能算出五维评分。"""
    result = compute_risk_score(1)
    assert [d["name"] for d in result["dimensions"]] == list(DIMENSIONS)
    assert 1 <= result["overall"] <= 5
    assert result["level"] in ("风险较低", "风险中等", "风险偏高", "风险较高")
    for d in result["dimensions"]:
        assert 1 <= d["score"] <= 5
        assert d["basis"]  # 每个分数必须有依据说明（可溯源）


def test_solvency_scoring(monkeypatch):
    """偿债能力：低杠杆 5 分，高杠杆 1 分。"""
    import finengine.risk_score as rs

    from finengine.rules.engine import Point

    def fake_series(project_id):
        return {
            "有息负债": {"2025年度": Point(1000, "万元", source_page=175)},
            "货币资金": {"2025年度": Point(5000, "万元", source_page=174)},
            "资产负债率": {"2025年度": Point(20.0, "%", source_page=174)},
        }

    monkeypatch.setattr(rs, "_series", fake_series)
    good = rs.score_solvency(1)
    assert good["score"] == 5.0

    def fake_series_bad(project_id):
        return {
            "有息负债": {"2025年度": Point(8000, "万元", source_page=175)},
            "货币资金": {"2025年度": Point(2000, "万元", source_page=174)},
            "资产负债率": {"2025年度": Point(85.0, "%", source_page=174)},
        }

    monkeypatch.setattr(rs, "_series", fake_series_bad)
    bad = rs.score_solvency(1)
    assert bad["score"] == 1.0


def test_operations_scoring(monkeypatch):
    """营运质量：周转天数大幅拉长 → 低分。"""
    import finengine.risk_score as rs

    from finengine.rules.engine import Point

    def fake(project_id):
        return {
            "应收账款": {"2024年度": Point(200, "万元"), "2025年度": Point(600, "万元")},
            "营业收入": {"2024年度": Point(1000, "万元"), "2025年度": Point(1000, "万元")},
        }

    monkeypatch.setattr(rs, "_series", fake)
    result = rs.score_operations(1)
    assert result["score"] <= 2.0
    assert "周转天数" in result["basis"]
