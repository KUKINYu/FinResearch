"""财务数据提取器（Spike B 核心产出）。

设计要点（来自对 5 份真实招股书的实测）：
1. 不依赖章节标题（各家写法不同），按表格内容识别：
   找到"指标名列 + 年份列"的表格，再按内容特征分类
   （摘要表 / 资产负债表 / 利润表 / 现金流量表）。
2. 每条提取出的数据带出处：文件 + 页码 + 行标签 + 表格坐标，
   这是全产品"可溯源"的地基。
3. 数值归一化：去千分位、识别百分号与"—"（无数据）；
   单位从行标签"（万元）"或表格附近文字"单位：万元"识别。
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

from .indicators import (
    COGS,
    GROSS_MARGIN,
    INDICATOR_DEFS,
    INTEREST_DEBT_COMPONENTS,
    NET_MARGIN,
    NET_PROFIT_PARENT,
    REVENUE,
    ROE,
    match_indicator,
    normalize_label,
)

# 天然是百分比的指标（单元格内可能没有 % 号，如"加权平均净资产收益率（%）"表）
PERCENT_INDICATORS = {ROE, GROSS_MARGIN, NET_MARGIN}

# 年份识别：2025年度 / 2025-12-31 / 2025年12月31日 / 2023-12-31/2023年度
YEAR_RE = re.compile(r"(20\d{2})")
# 期间列识别（严格版）：必须是完整日期/年度写法——裸年份"2022"不算
# （实测：散文里的裸年份曾伪造表头，导致子公司数据错位进假表）
# 捕获组 1 = 年份；后缀用非捕获组
PERIOD_CELL_RE = re.compile(r"(20\d{2})(?:年度|年\s*\d{1,2}|[-./])")
# 期间列判断：含"X月"或"1-6"等字样的是期间数（如 2026年6月30日 → 1-6月）
# 注意排除"12月31日"——年末时点数是整年列，不是期间数
INTERIM_RE = re.compile(r"(1[0-2]|[1-9])月|1-6|1-9|1-3|[一二三]季度")
# 回退通道里合法的表头标签（散文行的长标签不能当表头）
HEADER_LABEL_RE = re.compile(r"^(项目|指标|报告期|财务指标|主要财务指标)?$")
# 转置表的纯期间格："2025年度" / "2026年1-6月"（整格完全匹配，不含其他文字）
PURE_PERIOD_RE = re.compile(r"^(20\d{2})年(?:度|1-6月)$")

# 判定某表为资产负债表的关键行（表头为日期式时用）
BALANCE_MARKERS = ("货币资金", "存货", "资产总计", "资产总额", "负债合计", "流动资产", "非流动资产")
# 判定利润表
INCOME_MARKERS = ("营业总收入", "营业成本", "利润总额")
# 判定现金流量表（"经营活动产生的现金流量"可匹配到不带"净额"的片段标题）
CASHFLOW_MARKERS = (
    "经营活动产生的现金流量",
    "销售商品、提供劳务收到的现金",
    "投资活动产生的现金流量",
    "筹资活动产生的现金流量",
)
# 判定摘要表：营业收入+净利润+（ROE 或 经营现金流）
SUMMARY_MARKERS = ("营业收入", "净利润", "加权平均净资产收益率", "经营活动产生的现金流量净额")


@dataclass
class SourceRef:
    """出处四元组（M2 接入数据库后补 file_id，此处先记录文件路径）。"""

    file: str
    page: int
    label: str
    bbox: tuple[float, float, float, float] | None = None

    def to_dict(self) -> dict:
        return {"file": self.file, "page": self.page, "label": self.label, "bbox": self.bbox}


@dataclass
class DataPoint:
    """一个提取出的数值。value 为 float；unit 为原始单位（万元/元/%）。"""

    value: float
    unit: str
    period: str  # 期间标签，如 "2025年度"
    source: SourceRef

    def to_dict(self) -> dict:
        return {"value": self.value, "unit": self.unit, "period": self.period, "source": self.source.to_dict()}


@dataclass
class ExtractedTable:
    """一页上的一个表格：文本 + 坐标（供界面跳页高亮用）。"""

    page: int
    rows: list[list[str]] = field(default_factory=list)
    bbox: tuple[float, float, float, float] | None = None


# 行内"标签 + 数值们"的切分：找到第一个数值 token，之前为标签
LINE_ROW_RE = re.compile(r"-?\d[\d,\.]*%?")


def split_line(text: str) -> list[str]:
    """把一行文字切分为 [标签, 值1, 值2, ...]；无数值则返回 [整行]。

    表头可能被拆成 "2025.12.31" + "/2025年度" 两个 token，
    这里把以 "/" 开头的 token 并入前一个。
    """
    m = LINE_ROW_RE.search(text)
    if not m:
        return [text]
    # 剥离标签尾部残留的占位符（如"应收票据 - -"中的横线）
    label = text[: m.start()].strip().rstrip(" -—–　")
    values: list[str] = []
    for tok in text[m.start() :].split():
        if values and tok.startswith("/"):
            values[-1] = values[-1] + tok
        else:
            values.append(tok)
    if label:
        return [label] + values
    # 无标签行（如纯表头行）：补空标签占住第 0 列，保持列对齐
    return [""] + values


# 页码脚注（如"1-1-200"）：跳过即可，不代表表结束（跨页续表很常见）
FOOTER_RE = re.compile(r"^\d{1,2}-\d{1,2}-\d+$")


def text_line_tables(
    page, carry: list[list[str]] | None = None
) -> tuple[list[ExtractedTable], list[list[str]]]:
    """回退通道：pdfplumber 检测不到表格线时，按文字行重建表格。

    适用于表格以纯文本排版渲染的招股书（实测：燧原科技）。
    规则：含 ≥2 个年份的行是表头；其后所有"带数值的行"都归入该表。
    表状态跨页延续（carry）：跨页续表没有表头也能续上
    （实测：燧原资产负债表负债部分在第201页顶部无表头）。
    散文行会被指标匹配过滤。
    返回 (本页产生的表, 待续到下一页的行)。
    """
    words = page.extract_words()
    if not words:
        return [], carry or []
    # 按 top 坐标聚成行（容差 3pt），行内按 x0 排序后拼接
    grouped: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if not grouped or abs(w["top"] - grouped[-1][0]["top"]) > 3:
            grouped.append([w])
        else:
            grouped[-1].append(w)
    lines = [" ".join(w["text"] for w in ln) for ln in grouped]

    tables: list[ExtractedTable] = []
    current: list[list[str]] = list(carry or [])
    for text in lines:
        if FOOTER_RE.match(text.strip()):
            continue
        cells = split_line(text)
        year_count = sum(1 for c in cells[1:] if PERIOD_CELL_RE.search(normalize_label(c or "")))
        # 表头行的标签列必须是"项目/指标"等短标签，散文行（长标签）不能当表头
        header_label_ok = bool(HEADER_LABEL_RE.match(normalize_label(cells[0] or "")))
        has_nums = len(cells) > 1
        if year_count >= 2 and header_label_ok:
            # 新表头：收尾上一张表
            if current and len(current) > 2:
                tables.append(ExtractedTable(page=page.page_number, rows=current))
            current = [cells]
            continue
        if not current:
            continue
        if has_nums:
            current.append(cells)
    # 页末：本页已产生的表照常输出；current 同时作为 carry 延续到下一页
    if current and len(current) > 2:
        tables.append(ExtractedTable(page=page.page_number, rows=current))
    return tables, current


def iter_tables(pdf) -> list[ExtractedTable]:
    """提取 PDF 中所有表格（含页码与坐标）。

    优先 pdfplumber 的表格检测（带坐标，可高亮）。
    若一页的 pdfplumber 表格全都"不可用"（无年份列或无法分类——
    如标签列在表格线外的排版，实测：燧原科技），
    则该页走文本行回退通道（bbox 为 None）。
    """
    result: list[ExtractedTable] = []
    carry: list[list[str]] = []
    for page_idx, page in enumerate(pdf.pages):
        rows_list = page.extract_tables()
        usable = False
        if rows_list:
            found = page.find_tables()
            for i, rows in enumerate(rows_list):
                bbox = tuple(found[i].bbox) if i < len(found) else None
                table = ExtractedTable(page=page_idx + 1, rows=rows, bbox=bbox)
                if has_year_columns(rows) and table_hint(table) != "other":
                    usable = True
                result.append(table)
        if not usable:
            fallback_tables, carry = text_line_tables(page, carry)
            result.extend(fallback_tables)
        else:
            carry = []  # 有可用正规表格的页，回退通道的跨页续表中断
    return result


def parse_periods(header_row: list[str]) -> list[str]:
    """解析表头年份列，返回与数据列对齐的期间标签。

    "2025-12-31/ 2025年度" → "2025年度"；
    "2026年6月30日" → "2026年1-6月"（期间数，标为 interim 语义由调用方判断）。
    """
    periods: list[str] = []
    for cell in header_row[1:]:  # 第 0 列是"项目/指标"
        text = normalize_label(cell or "")
        m = PERIOD_CELL_RE.search(text)
        if not m:
            periods.append("")
            continue
        year = m.group(1)
        if INTERIM_RE.search(text) and "12月31日" not in text:
            periods.append(f"{year}年1-6月")
        else:
            periods.append(f"{year}年度")
    return periods


def parse_number(text: str) -> float | None:
    """解析数值：去千分位/空白；"—"/空 → None；"12.5%" → 12.5（单位另记）。"""
    if not text:
        return None
    s = text.replace(",", "").replace("，", "").strip()
    if s in ("—", "-", "――", "/", "不适用", "N/A", "n/a"):
        return None
    m = re.match(r"^-?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None


def detect_unit(text: str) -> str:
    """从文字中识别单位：万元 / 元 / %。默认万元（招股书主流口径）。"""
    if "%" in text:
        return "%"
    if "万元" in text:
        return "万元"
    if "亿元" in text:
        return "亿元"
    if "元" in text and "万元" not in text:
        return "元"
    return "万元"


def table_hint(table: ExtractedTable) -> str:
    """按表头样式 + 内容把表格归入一个类别（用于指标别名匹配的范围约束）。

    顺序很重要（实测 5 份招股书总结）：
    - 纯日期式表头（如 2025-12-31）→ 资产负债表（含跨页续页片段）
    - 期间式表头（2025年度 / 混合）→ 现金流 → 利润 → 摘要
    - 利润表含"净利润"字样，若不先排除会被误判为摘要表
    """
    header = [normalize_label(c or "") for c in table.rows[0]] if table.rows else []
    # 日期式表头三种写法："2025-12-31" / "2025年12月31日" / "2025.12.31"
    n_date = sum(1 for c in header[1:] if re.search(r"12[.\-]31|12月31日", c))
    n_period = sum(1 for c in header[1:] if "年度" in c)
    first_col = " ".join(normalize_label(r[0] or "") for r in table.rows if r)

    if n_date >= 2 and n_period == 0:
        # 日期式表头：资产负债表或其续页
        if any(m in first_col for m in BALANCE_MARKERS):
            return "balance"
        return "other"

    if sum(1 for m in CASHFLOW_MARKERS if m in first_col) >= 2:
        return "cashflow"
    if sum(1 for m in INCOME_MARKERS if m in first_col) >= 2:
        return "income"
    if any(m in first_col for m in SUMMARY_MARKERS) and any(
        m in first_col for m in (REVENUE, "净利润")
    ):
        return "summary"
    return "other"


def has_year_columns(rows: list[list[str]]) -> bool:
    """表头行至少 2 列含年份。"""
    if not rows:
        return False
    header = rows[0]
    year_cells = [c for c in header[1:] if YEAR_RE.search(normalize_label(c or ""))]
    return len(year_cells) >= 2


def unit_from_page(page_text: str, rows: list[list[str]]) -> str:
    """表格单位：优先表格附近的"单位：万元/元"（本页+上一页，报表的单位
    标注常在报表首页而表格跨页延续），其次行标签内"（万元）"，默认万元。"""
    m = re.search(r"单位[：:]\s*(万元|亿元|元)", page_text)
    if m:
        return m.group(1)
    for row in rows[:5]:
        label = normalize_label(row[0] or "")
        m = re.search(r"（(万元|亿元|元)）", label)
        if m:
            return m.group(1)
    return "万元"


def extract_from_table(
    table: ExtractedTable, hint: str, page_text: str, file_name: str
) -> dict[str, dict[str, DataPoint]]:
    """page_text 需包含本页与上一页文字（报表单位标注常跨页）。"""
    """从单个表格提取指标 → 期间 → 数值（带出处）。

    返回 {指标名: {期间标签: DataPoint}}。
    """
    periods = parse_periods(table.rows[0])
    if not any(periods):
        return {}
    unit = unit_from_page(page_text, table.rows)
    out: dict[str, dict[str, DataPoint]] = {}
    for row in table.rows[1:]:
        if not row:
            continue
        label = normalize_label(row[0] or "")
        indicator = match_indicator(label, hint)
        if indicator is None:
            continue
        # 列对齐：数据格少于表头期间数时，说明表头混入了非期间格
        # （如错位的"项目"字样），剔除空期间后再对齐（实测：燧原第202页）
        row_periods = periods
        if len(row) - 1 < len(periods):
            row_periods = [p for p in periods if p]
        # 数据格仍少于期间列数：行不完整（如单列的子公司数据混入多期表），跳过
        if len(row) - 1 < len(row_periods):
            continue
        for j, cell in enumerate(row[1:]):
            period = row_periods[j] if j < len(row_periods) else ""
            if not period:
                continue
            value = parse_number(cell or "")
            if value is None:
                continue
            # 单位优先级：百分比指标 > 单元格含 % > 表格单位标注
            if indicator in PERCENT_INDICATORS or "%" in (cell or ""):
                cell_unit = "%"
            else:
                cell_unit = unit
            src = SourceRef(file=file_name, page=table.page, label=row[0], bbox=table.bbox)
            out.setdefault(indicator, {})[period] = DataPoint(
                value=value, unit=cell_unit, period=period, source=src
            )
    return out


def extract_transposed(
    table: ExtractedTable, page_text: str, file_name: str
) -> dict[str, dict[str, DataPoint]]:
    """转置表提取：指标名在表头行、期间在第一列。

    证监会标准"净资产收益率及每股收益"表即此布局（实测：燧原第216页）：
      报告期 | 加权平均净资产收益率 | 基本每股收益
      2025年度 | -31.85% | -3.00
    期间格必须是纯"2025年度"格式——"2025年末/2025年度"是子公司
    数据表（实测：燧原第91页重要子公司情况），不得提取。
    """
    header = [normalize_label(c or "") for c in table.rows[0]] if table.rows else []
    col_indicators: dict[int, str] = {}
    for j, cell in enumerate(header[1:], start=1):
        ind = match_indicator(cell, "summary")
        if ind:
            col_indicators[j] = ind
    if not col_indicators:
        return {}
    unit = unit_from_page(page_text, table.rows)
    out: dict[str, dict[str, DataPoint]] = {}
    for row in table.rows[1:]:
        if not row:
            continue
        period_text = normalize_label(row[0] or "")
        m = PURE_PERIOD_RE.match(period_text)
        if not m:
            continue
        year = m.group(1)
        if INTERIM_RE.search(period_text):
            period = f"{year}年1-6月"
        else:
            period = f"{year}年度"
        for j, ind in col_indicators.items():
            if j >= len(row):
                continue
            cell = row[j] or ""
            value = parse_number(cell)
            if value is None:
                continue
            if ind in PERCENT_INDICATORS or "%" in cell:
                cell_unit = "%"
            else:
                cell_unit = unit
            src = SourceRef(file=file_name, page=table.page, label=row[0], bbox=table.bbox)
            out.setdefault(ind, {})[period] = DataPoint(
                value=value, unit=cell_unit, period=period, source=src
            )
    return out


def extract_document(path: str | Path) -> dict:
    """解析一份 PDF，返回结构化提取结果。

    返回：
    {
      "file": 文件名,
      "pages": 总页数,
      "indicators": {指标名: {期间: DataPoint}},
      "tables_found": [(页码, 表类型, 行数), ...],
    }
    """
    path = Path(path)
    out: dict[str, dict[str, DataPoint]] = {}
    tables_found: list[tuple[int, str, int]] = []
    with pdfplumber.open(path) as pdf:
        # 每页文字（用于单位识别；上一页拼入以覆盖"单位：元"标注跨页的情况）
        page_texts: dict[int, str] = {}
        for t in iter_tables(pdf):
            if t.page not in page_texts:
                prev = pdf.pages[t.page - 2].extract_text() or "" if t.page >= 2 else ""
                cur = pdf.pages[t.page - 1].extract_text() or ""
                page_texts[t.page] = prev + "\n" + cur
            # 常规表需表头行含年份；转置表年份在第一列，单独判断
            is_transposed_candidate = False
            if not has_year_columns(t.rows):
                first_col = " ".join(normalize_label(r[0] or "") for r in t.rows if r)
                is_transposed_candidate = len(YEAR_RE.findall(first_col)) >= 2
                if not is_transposed_candidate:
                    continue
            hint = table_hint(t)
            if is_transposed_candidate or hint == "other":
                # 常规分类不出的表可能是转置表（指标在表头行），尝试转置提取
                extracted = extract_transposed(t, page_texts[t.page], path.name)
                if extracted:
                    tables_found.append((t.page, "transposed", len(t.rows)))
                else:
                    continue
            else:
                tables_found.append((t.page, hint, len(t.rows)))
                extracted = extract_from_table(t, hint, page_texts[t.page], path.name)
                if not extracted:
                    extracted = extract_transposed(t, page_texts[t.page], path.name)
            # 首次出现优先：同一指标同一期间，保留文档中最早出现的来源
            # （重大事项提示/概览的摘要表比管理层讨论里的重复表更权威）
            for ind, periods in extracted.items():
                base = out.setdefault(ind, {})
                for period, dp in periods.items():
                    base.setdefault(period, dp)

    return {
        "file": path.name,
        "pages": len(pdf.pages),
        "indicators": out,
        "tables_found": tables_found,
    }


def extract_indicators(path: str | Path) -> dict:
    """提取 10 项核心指标（含派生计算），返回按指标组织的期间序列。

    派生指标：
    - 毛利率 = (营业收入 - 营业成本) / 营业收入（利润表）
    - 净利率 = 净利润 / 营业收入
    - 有息负债 = 短期借款 + 长期借款 + 应付债券 + 一年内到期的非流动负债（资产负债表）
    """
    doc = extract_document(path)
    inds = doc["indicators"]

    result: dict[str, dict] = {}
    for name in (REVENUE, "净利润", NET_PROFIT_PARENT, "加权平均净资产收益率",
                 "经营活动产生的现金流量净额", "应收账款", "存货", "研发费用",
                 "毛利率", "净利率", "有息负债"):
        result[name] = {p: d.to_dict() for p, d in inds.get(name, {}).items()}

    # 毛利率 / 净利率：从利润表科目计算（与摘要表已有值冲突时以提取值为准）
    revenue = inds.get(REVENUE, {})
    cogs = inds.get(COGS, {})
    net_profit = inds.get("净利润", {})
    for period, rev in revenue.items():
        if rev.unit != "%" and period in cogs and cogs[period].unit != "%":
            gm = (rev.value - cogs[period].value) / rev.value * 100 if rev.value else None
            if gm is not None and period not in result["毛利率"]:
                result["毛利率"][period] = {
                    "value": round(gm, 2),
                    "unit": "%",
                    "period": period,
                    "derived": "（营业收入-营业成本）/营业收入",
                    "source": rev.source.to_dict(),
                }
        if period in net_profit and net_profit[period].unit != "%":
            nm = net_profit[period].value / rev.value * 100 if rev.value else None
            if nm is not None and period not in result["净利率"]:
                result["净利率"][period] = {
                    "value": round(nm, 2),
                    "unit": "%",
                    "period": period,
                    "derived": "净利润/营业收入",
                    "source": rev.source.to_dict(),
                }

    # 有息负债：资产负债表科目求和（各科目单位一致才计算）
    components = [inds.get(c, {}) for c in INTEREST_DEBT_COMPONENTS]
    all_periods = {p for c in components for p in c}
    for period in all_periods:
        values, units, sources = [], set(), []
        for c in components:
            dp = c.get(period)
            if dp:
                values.append(dp.value)
                units.add(dp.unit)
                sources.append(dp.source)
        if values and len(units) == 1:
            result["有息负债"][period] = {
                "value": round(sum(values), 2),
                "unit": units.pop(),
                "period": period,
                "derived": "+".join(INTEREST_DEBT_COMPONENTS),
                "source": sources[0].to_dict(),
            }

    result["_meta"] = {"file": doc["file"], "pages": doc["pages"], "tables_found": doc["tables_found"]}
    return result
