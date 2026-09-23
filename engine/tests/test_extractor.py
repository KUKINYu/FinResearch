"""提取器单元测试。

覆盖 Spike B 实测 5 份真实招股书踩过的全部坑：
日期表头三种写法、期间误判（12月31日）、表头污染（错位"项目"）、
转置表、别名误配（研发费用率）、单位跨页、亏损公司写法等。
"""

from finengine.extract.financial_extractor import (
    ExtractedTable,
    extract_from_table,
    parse_number,
    parse_periods,
    split_line,
    table_hint,
)
from finengine.extract.indicators import match_indicator, normalize_label


# ---------- 数值解析 ----------

def test_parse_number_basic():
    assert parse_number("1,234.56") == 1234.56
    assert parse_number("-63,237.11") == -63237.11
    assert parse_number("24.20%") == 24.20
    assert parse_number(" 100 ") == 100.0


def test_parse_number_none_cases():
    assert parse_number("—") is None
    assert parse_number("-") is None
    assert parse_number("――") is None
    assert parse_number("不适用") is None
    assert parse_number("") is None
    assert parse_number(None) is None


# ---------- 期间解析 ----------

def test_parse_periods_date_styles():
    assert parse_periods(["项目", "2025-12-31", "2024-12-31"]) == ["2025年度", "2024年度"]
    assert parse_periods(["项目", "2025年12月31日", "2024年12月31日"]) == ["2025年度", "2024年度"]
    assert parse_periods(["项目", "2025.12.31", "2024.12.31"]) == ["2025年度", "2024年度"]


def test_parse_periods_mixed_and_interim():
    # 混合表头（摘要表）
    assert parse_periods(["项目", "2025-12-31/2025年度", "2024-12-31/2024年度"]) == [
        "2025年度",
        "2024年度",
    ]
    # 期间数（6月30日）
    assert parse_periods(["项目", "2026年6月30日", "2025年12月31日"]) == [
        "2026年1-6月",
        "2025年度",
    ]
    # 12月31日是整年不是期间（坑：正则曾把"12月"里的"2月"当期间）
    assert parse_periods(["项目", "2025年12月31日", "2023年12月31日"]) == [
        "2025年度",
        "2023年度",
    ]


def test_parse_periods_non_year_cells():
    # 非年份列（如"同比变动"）留空占位
    assert parse_periods(["项目", "2025年度", "同比变动"]) == ["2025年度", ""]


# ---------- 行切分（回退通道） ----------

def test_split_line_basic():
    assert split_line("营业收入 74,947.57 69,995.26") == ["营业收入", "74,947.57", "69,995.26"]


def test_split_line_merged_slash_header():
    # "/2025年度" 是被拆开的表头 token，需并入前一个
    assert split_line("2025.12.31 /2025年度 2024.12.31 /2024年度") == [
        "",
        "2025.12.31/2025年度",
        "2024.12.31/2024年度",
    ]


def test_split_line_dash_placeholder_pollution():
    # 纯"-"占位符不该污染标签：剥离后标签干净、数值列对齐
    # （实测：燧原资产负债表"应收票据"行的占位符在词序中位于数值之前）
    assert split_line("应收票据 - - 537.49") == ["应收票据", "537.49"]


def test_split_line_no_number():
    assert split_line("流动资产：") == ["流动资产："]


# ---------- 指标别名匹配 ----------

def test_match_indicator_parent_net_profit_first():
    # 归母净利润必须先于净利润匹配（长别名优先）
    assert match_indicator("归属于母公司股东的净利润（万元）", "summary") == "归属于母公司股东的净利润"
    assert match_indicator("净利润（万元）", "summary") == "净利润"


def test_match_indicator_rejects_suffix_noise():
    # "研发费用"不得误配"研发费用率"
    assert match_indicator("研发费用率", "income") is None
    assert match_indicator("研发费用（万元）", "income") == "研发费用"
    # "应收账款"不得误配"应收账款周转率"
    assert match_indicator("应收账款周转率（次/年）", "balance") is None
    # "净利润率"应归入净利率
    assert match_indicator("净利润率", "summary") == "净利率"


def test_match_indicator_loss_company_wording():
    # 亏损公司写法
    assert match_indicator("归属于母公司股东/所有者的净亏损", "summary") == "归属于母公司股东的净利润"
    assert match_indicator("净亏损", "income") == "净利润"


def test_normalize_label():
    # 去空白；全角冒号转半角；括号保持原样
    assert normalize_label("营业收入（万 元）") == "营业收入（万元）"
    assert normalize_label("其中：营业收入") == "其中:营业收入"


# ---------- 表分类 ----------

def _table(header, labels):
    rows = [header] + [[l] for l in labels]
    return ExtractedTable(page=1, rows=rows)


def test_table_hint_balance_date_styles():
    # 三种日期表头写法都识别为资产负债表
    labels = ["货币资金", "存货", "资产总计"]
    assert table_hint(_table(["项目", "2025-12-31", "2024-12-31"], labels)) == "balance"
    assert table_hint(_table(["项目", "2025年12月31日", "2024年12月31日"], labels)) == "balance"
    assert table_hint(_table(["项目", "2025.12.31", "2024.12.31"], labels)) == "balance"


def test_table_hint_income_vs_summary():
    # 利润表含"净利润"字样，必须先判利润表再判摘要
    income = _table(
        ["项目", "2025年度", "2024年度"],
        ["一、营业总收入", "其中：营业成本", "利润总额", "净利润"],
    )
    assert table_hint(income) == "income"
    summary = _table(
        ["项目", "2025年度", "2024年度"],
        ["营业收入", "净利润", "加权平均净资产收益率"],
    )
    assert table_hint(summary) == "summary"


def test_table_hint_cashflow():
    cf = _table(
        ["项目", "2025年度", "2024年度"],
        ["经营活动产生的现金流量", "投资活动产生的现金流量", "销售商品、提供劳务收到的现金"],
    )
    assert table_hint(cf) == "cashflow"


# ---------- 表提取 ----------

def test_extract_alignment_with_polluted_header():
    """表头混入错位"项目"（实测：燧原第202页）时列对齐。

    表头 4 格（含 1 个污染格）对 3 个数据格：剔除空期间后对齐。
    """
    table = ExtractedTable(
        page=202,
        rows=[
            ["", "2025年度", "项目", "2024年度", "2023年度"],
            ["经营活动产生的现金流量净额", "-96,508.71", "-179,773.78", "-120,900.41"],
        ],
    )
    out = extract_from_table(table, "cashflow", "", "test.pdf")
    ocf = out["经营活动产生的现金流量净额"]
    assert ocf["2025年度"].value == -96508.71
    assert ocf["2024年度"].value == -179773.78
    assert ocf["2023年度"].value == -120900.41


def test_extract_percent_unit_by_cell():
    table = ExtractedTable(
        page=35,
        rows=[
            ["项目", "2025年度", "2024年度"],
            ["加权平均净资产收益率", "24.20%", "24.54%"],
            ["营业收入（万元）", "74,947.57", "69,995.26"],
        ],
    )
    out = extract_from_table(table, "summary", "", "test.pdf")
    assert out["加权平均净资产收益率"]["2025年度"].unit == "%"
    assert out["营业收入"]["2025年度"].unit == "万元"
    assert out["营业收入"]["2025年度"].value == 74947.57


def test_extract_unit_from_row_label_without_page_note():
    """页面无"单位：X"标注时，行标签"（万元）"兜底。"""
    table = ExtractedTable(
        page=1,
        rows=[
            ["项目", "2025年度", "2024年度"],
            ["存货（万元）", "6,621.59", "7,383.82"],
        ],
    )
    out = extract_from_table(table, "balance", "这里没有单位标注", "test.pdf")
    assert out["存货"]["2025年度"].unit == "万元"
