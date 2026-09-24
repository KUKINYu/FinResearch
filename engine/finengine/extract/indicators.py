"""指标定义与别名表。

行标签 → 标准指标名的映射是提取准确率的关键：不同券商/公司
对同一指标的行标签写法不同（如"营业总收入"vs"营业收入"）。
匹配规则按（长→短）顺序尝试，避免短别名抢先误配。
"""

from dataclasses import dataclass

# 标准指标名（产品层使用的 10 项核心指标 + 派生计算所需的基础科目）
REVENUE = "营业收入"
NET_PROFIT = "净利润"
NET_PROFIT_PARENT = "归属于母公司股东的净利润"
GROSS_MARGIN = "毛利率"
NET_MARGIN = "净利率"
ROE = "加权平均净资产收益率"
OCF = "经营活动产生的现金流量净额"
AR = "应收账款"
INVENTORY = "存货"
INTEREST_DEBT = "有息负债"
RD_EXPENSE = "研发费用"

# 派生指标所需科目（不在 10 项核心之列，但计算要用）
COGS = "营业成本"
ST_LOAN = "短期借款"
LT_LOAN = "长期借款"
BONDS = "应付债券"
NCL_DUE_1Y = "一年内到期的非流动负债"
OPERATING_INCOME = "营业总收入"

# M5 异常检测规则所需科目
TOTAL_ASSETS = "总资产"
TOTAL_LIABILITIES = "总负债"
DEBT_RATIO = "资产负债率"
CASH = "货币资金"
CASH_FROM_SALES = "销售商品、提供劳务收到的现金"


@dataclass(frozen=True)
class IndicatorDef:
    """一个标准指标的定义：别名列表 + 主要数据来源表类型。"""

    name: str
    aliases: tuple[str, ...]
    # 该指标通常出现在哪类表：summary=财务数据摘要表 balance=资产负债表
    # income=利润表 cashflow=现金流量表
    source_hint: str


# 别名按长度降序排列，长别名优先匹配（如"其中：营业收入"先于"营业收入"）
INDICATOR_DEFS: dict[str, IndicatorDef] = {
    name: def_
    for name, def_ in [
        (
            REVENUE,
            IndicatorDef(
                REVENUE,
                ("其中：营业收入", "营业收入（", "营业总收入（", "营业收入", "营业总收入"),
                "summary|income",
            ),
        ),
        (
            NET_PROFIT_PARENT,
            IndicatorDef(
                NET_PROFIT_PARENT,
                (
                    "归属于母公司所有者的净利润",
                    "归属于母公司股东的净利润",
                    "归属于母公司普通股股东的净利润",
                    # 亏损公司的写法（实测：燧原科技"归属于母公司股东/所有者的净亏损"）
                    "归属于母公司股东/所有者的净亏损",
                    "归属于母公司股东的净亏损",
                ),
                "summary|income",
            ),
        ),
        (
            NET_PROFIT,
            IndicatorDef(
                NET_PROFIT,
                ("净利润（", "净利润", "净亏损（", "净亏损"),
                "summary|income",
            ),
        ),
        (
            ROE,
            IndicatorDef(
                ROE,
                ("加权平均净资产收益率（", "加权平均净资产收益率", "净资产收益率（加权）"),
                "summary",
            ),
        ),
        (
            OCF,
            IndicatorDef(
                OCF,
                ("经营活动产生的现金流量净额（", "经营活动产生的现金流量净额", "经营活动现金流量净额"),
                "summary|cashflow",
            ),
        ),
        (
            GROSS_MARGIN,
            IndicatorDef(GROSS_MARGIN, ("综合毛利率", "主营业务毛利率", "毛利率"), "summary|income"),
        ),
        (
            NET_MARGIN,
            IndicatorDef(NET_MARGIN, ("销售净利率", "净利率", "净利润率"), "summary|income"),
        ),
        (
            AR,
            IndicatorDef(AR, ("应收账款（", "应收账款账面价值", "应收账款"), "balance"),
        ),
        (
            INVENTORY,
            IndicatorDef(INVENTORY, ("存货（", "存货"), "balance"),
        ),
        (
            RD_EXPENSE,
            IndicatorDef(RD_EXPENSE, ("研发费用（", "研发费用"), "summary|income"),
        ),
        (
            COGS,
            IndicatorDef(COGS, ("营业成本（", "营业成本", "其中：营业成本", "减：营业成本"), "summary|income"),
        ),
        (
            ST_LOAN,
            # balance|summary：资产负债表续页可能与利润表/摘要表合并成一张表（实测：燧原第201页）
            IndicatorDef(ST_LOAN, ("短期借款（", "短期借款"), "balance|summary"),
        ),
        (
            LT_LOAN,
            IndicatorDef(
                LT_LOAN,
                ("长期借款（", "长期借款（含一年内到期部分）", "长期借款"),
                "balance|summary",
            ),
        ),
        (BONDS, IndicatorDef(BONDS, ("应付债券（", "应付债券"), "balance|summary")),
        (
            NCL_DUE_1Y,
            IndicatorDef(NCL_DUE_1Y, ("一年内到期的非流动负债（", "一年内到期的非流动负债"), "balance|summary"),
        ),
        (
            TOTAL_ASSETS,
            IndicatorDef(TOTAL_ASSETS, ("资产总计（", "资产总计", "资产总额（", "资产总额", "总资产（", "总资产"), "balance|summary"),
        ),
        (
            TOTAL_LIABILITIES,
            IndicatorDef(
                TOTAL_LIABILITIES,
                ("负债总计（", "负债总计", "负债合计（", "负债合计", "负债总额（", "负债总额", "总负债（", "总负债"),
                "balance|summary",
            ),
        ),
        (CASH, IndicatorDef(CASH, ("货币资金（", "货币资金"), "balance|summary")),
        (
            CASH_FROM_SALES,
            IndicatorDef(CASH_FROM_SALES, ("销售商品、提供劳务收到的现金（", "销售商品、提供劳务收到的现金"), "cashflow|summary"),
        ),
    ]
}

# 有息负债的构成科目（默认口径，可在设置中调整）
INTEREST_DEBT_COMPONENTS = (ST_LOAN, LT_LOAN, BONDS, NCL_DUE_1Y)


def match_indicator(label: str, table_hint: str) -> str | None:
    """把表格行标签映射到标准指标名；不匹配返回 None。

    所有别名按长度降序匹配：长别名优先（如"归属于母公司股东的净利润"
    必须先于"净利润"），避免短别名抢先误配。标签与别名都做归一化。
    """
    norm = normalize_label(label)
    if not norm or len(norm) > 40:  # 过长的标签（如整句文字）不匹配
        return None
    candidates: list[tuple[int, str, str]] = []
    for name, def_ in INDICATOR_DEFS.items():
        if table_hint not in def_.source_hint:
            continue
        for alias in def_.aliases:
            candidates.append((len(normalize_label(alias)), name, normalize_label(alias)))
    candidates.sort(reverse=True)
    for _, name, alias in candidates:
        if norm == alias:
            return name
        # 前缀匹配仅在别名以"（"结尾、或匹配后紧跟"（"时允许：
        # "营业收入（万元）"✓；"研发费用率"✗（防止"研发费用"误配"研发费用率"）
        if norm.startswith(alias) and (
            alias.endswith("（") or (len(norm) > len(alias) and norm[len(alias)] in "（(")
        ):
            return name
    return None


def normalize_label(label: str) -> str:
    """归一化行标签：去空白与全角标点干扰。"""
    return "".join(label.split()).replace("：", ":").replace("　", "")
