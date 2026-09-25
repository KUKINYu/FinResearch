"""A 股数据源实现（AkShare + 本地缓存 + 降级）。"""

import datetime
import json
import time

from sqlalchemy import select

from ..db import SessionLocal
from ..db.models import MarketCache


def _ak():
    """延迟导入：akshare 未安装时给出明确提示。"""
    try:
        import akshare as ak

        return ak
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("数据源组件未安装（akshare），请运行 setup 脚本更新依赖") from e


# ---------- 缓存 ----------

def cache_get(key: str, ttl_seconds: int) -> dict | None:
    with SessionLocal() as session:
        row = session.get(MarketCache, key)
        if row is None:
            return None
        fetched = row.fetched_at
        now = datetime.datetime.now()
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=datetime.timezone.utc)
            now = now.astimezone(datetime.timezone.utc)
        if (now - fetched).total_seconds() > ttl_seconds:
            return None
        try:
            return json.loads(row.data_json)
        except json.JSONDecodeError:
            return None


def cache_put(key: str, data: dict) -> None:
    with SessionLocal() as session:
        row = session.get(MarketCache, key)
        payload = json.dumps(data, ensure_ascii=False)
        if row is None:
            session.add(MarketCache(key=key, data_json=payload, fetched_at=datetime.datetime.now()))
        else:
            row.data_json = payload
            row.fetched_at = datetime.datetime.now()
        session.commit()


# ---------- 个股搜索 ----------

def search_stocks(q: str, limit: int = 20) -> list[dict]:
    """按代码/名称搜索 A 股。全市场列表缓存 24 小时。"""
    q = (q or "").strip()
    if not q:
        return []
    cached = cache_get("a_stock_list", 24 * 3600)
    if cached is None:
        ak = _ak()
        df = ak.stock_info_a_code_name()
        items = [
            {"code": str(r["code"]), "name": str(r["name"])}
            for _, r in df.iterrows()
        ]
        cache_put("a_stock_list", {"items": items})
    else:
        items = cached["items"]
    ql = q.lower()
    out = [
        s for s in items if ql in s["code"].lower() or q in s["name"]
    ]
    return out[:limit]


# ---------- 个股财务数据 ----------

def _annual_financials(code: str) -> dict[str, dict[str, float]]:
    """按年份的财务指标：营收/归母净利润（东方财富业绩报表）+
    毛利率/净利率/ROE/研发投入（财务指标表）。

    返回 {年份: {indicator: value}}，金额单位统一为万元。
    """
    ak = _ak()
    out: dict[str, dict[str, float]] = {}

    # 东方财富业绩报表：营业总收入、归母净利润（单位元 → 万元）
    try:
        df = ak.stock_yjbb_em(date="20251231")  # 全市场年报
        sub = df[df["股票代码"] == code]
        for _, row in sub.iterrows():
            year = str(row["报告期"])[:4] if "报告期" in row else ""
            slot = out.setdefault(year, {})
            if row.get("营业总收入") is not None:
                slot["营业收入"] = float(row["营业总收入"]) / 10000
            if row.get("归母净利润") is not None:
                slot["归母净利润"] = float(row["归母净利润"]) / 10000
    except Exception as e:  # noqa: BLE001
        print(f"[finengine] 业绩报表获取失败（{code}）：{e}")

    # 财务指标表（毛利率/净利率/ROE/研发费用）
    try:
        ind = ak.stock_financial_analysis_indicator(
            symbol=code, start_year=str(datetime.datetime.now().year - 4)
        )
        for _, row in ind.iterrows():
            date_s = str(row["日期"])
            if not date_s.endswith("12-31"):
                continue
            year = date_s[:4]
            slot = out.setdefault(year, {})
            for col, key in (("销售毛利率", "毛利率"), ("销售净利率", "净利率"),
                             ("净资产收益率", "ROE"), ("研发费用", "研发投入")):
                if row.get(col) is not None:
                    try:
                        v = float(row[col])
                        slot[key] = v if key in ("毛利率", "净利率", "ROE") else v / 10000
                    except (TypeError, ValueError):
                        continue
    except Exception as e:  # noqa: BLE001
        print(f"[finengine] 财务指标获取失败（{code}）：{e}")

    return out


def get_financials(code: str, refresh: bool = False) -> dict[str, dict[str, float]]:
    """按年份财务指标（带 24h 缓存）。"""
    key = f"fin_{code}"
    if not refresh:
        cached = cache_get(key, 24 * 3600)
        if cached is not None:
            return cached["data"]
    data = _annual_financials(code)
    cache_put(key, {"data": data})
    return data


# ---------- 估值与行情 ----------

def get_valuation(codes: list[str], refresh: bool = False) -> dict[str, dict]:
    """实时估值：PE/PB/总市值（全市场快照缓存 1 小时）。

    P1-9 数据源回退链：akshare（东财）失败 → 缓存 → baostock（如已安装）。
    """
    result: dict[str, dict] = {}
    if not codes:
        return result
    key = "a_spot_em"
    if not refresh:
        cached = cache_get(key, 3600)
        if cached is not None:
            items = cached["items"]
            for code in codes:
                if code in items:
                    result[code] = items[code]
            return result
    ak = _ak()
    try:
        df = ak.stock_zh_a_spot_em()
        items: dict[str, dict] = {}
        for _, row in df.iterrows():
            c = str(row["代码"])
            items[c] = {
                "name": str(row.get("名称", "")),
                "pe": float(row["市盈率-动态"]) if row.get("市盈率-动态") not in (None, "-") else None,
                "pb": float(row["市净率"]) if row.get("市净率") not in (None, "-") else None,
                "market_cap": float(row["总市值"]) if row.get("总市值") not in (None, "-") else None,
            }
        cache_put(key, {"items": items})
        for code in codes:
            if code in items:
                result[code] = items[code]
    except Exception as e:  # noqa: BLE001 行情失败不影响财务数据
        print(f"[finengine] 行情数据获取失败（akshare）：{e}，尝试备用源 baostock")
        result = _valuation_via_baostock(codes)
        if result:
            cache_put(key, {"items": result})
    return result


def _valuation_via_baostock(codes: list[str]) -> dict[str, dict]:
    """备用源：baostock 日线含 peTTM/pbMRQ（需已安装 baostock 包）。"""
    try:
        import baostock as bs
    except ImportError:
        return {}
    out: dict[str, dict] = {}
    try:
        bs.login()
        for code in codes:
            bs_code = f"sh.{code}" if code.startswith(("6", "9")) else f"sz.{code}"
            rs = bs.query_history_k_data_plus(
                bs_code, "date,code,close,peTTM,pbMRQ", start_date="", end_date="", frequency="d"
            )
            rows = []
            while rs.error_code == "0" and rs.next():
                rows.append(rs.get_row_data())
            if rows:
                date_, c, close, pe, pb = rows[-1]
                out[code] = {
                    "name": c,
                    "pe": float(pe) if pe else None,
                    "pb": float(pb) if pb else None,
                    "market_cap": None,
                    "price": float(close) if close else None,
                    "as_of": date_,
                }
    except Exception as e:  # noqa: BLE001
        print(f"[finengine] baostock 获取失败：{e}")
    finally:
        try:
            bs.logout()
        except Exception:  # noqa: BLE001
            pass
    return out


def get_price_history(code: str, days: int = 250, refresh: bool = False) -> list[dict]:
    """日线收盘价（前复权），用于走势图。缓存 6 小时。"""
    key = f"price_{code}"
    if not refresh:
        cached = cache_get(key, 6 * 3600)
        if cached is not None:
            return cached["data"]
    ak = _ak()
    data: list[dict] = []
    try:
        df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date="", adjust="qfq")
        df = df.tail(days)
        for _, row in df.iterrows():
            data.append({"date": str(row["日期"]), "close": float(row["收盘"])})
    except Exception as e:  # noqa: BLE001
        print(f"[finengine] 股价历史获取失败：{e}")
        data = _price_via_baostock(code, days)
    if data:
        cache_put(key, {"data": data})
    return data


def _price_via_baostock(code: str, days: int) -> list[dict]:
    try:
        import baostock as bs
    except ImportError:
        return []
    out: list[dict] = []
    try:
        bs.login()
        bs_code = f"sh.{code}" if code.startswith(("6", "9")) else f"sz.{code}"
        rs = bs.query_history_k_data_plus(bs_code, "date,close", frequency="d", adjustflag="2")
        rows = []
        while rs.error_code == "0" and rs.next():
            rows.append(rs.get_row_data())
        for date_, close in rows[-days:]:
            out.append({"date": date_, "close": float(close)})
    except Exception as e:  # noqa: BLE001
        print(f"[finengine] baostock 股价获取失败：{e}")
    finally:
        try:
            bs.logout()
        except Exception:  # noqa: BLE001
            pass
    return out


# ---------- 对比汇总 ----------

def get_comparison(codes: list[str], refresh: bool = False) -> dict:
    """一次拿齐：各公司财务指标（最新整年）+ 估值。"""
    companies: list[dict] = []
    latest_year = str(datetime.datetime.now().year - 1)  # 默认用最近一个完整年度
    for code in codes:
        fin = get_financials(code, refresh=refresh)
        years = sorted(fin.keys())
        use_year = latest_year if latest_year in fin else (years[-1] if years else None)
        entry = {"code": code, "year": use_year, "financials": fin.get(use_year, {}) if use_year else {}}
        companies.append(entry)
    valuation = get_valuation(codes, refresh=refresh)
    for c in companies:
        c["valuation"] = valuation.get(c["code"], {})
    return {
        "companies": companies,
        "fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "note": "数据来源：公开行情与财报（AkShare）。财务指标为最近完整年度；市占率需人工补充。",
    }
