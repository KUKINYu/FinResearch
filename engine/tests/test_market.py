"""市场数据模块测试（mock akshare，不依赖网络与 pandas）。"""

import json

from finengine.db import SessionLocal
from finengine.db.models import MarketCache


class FakeDF(list):
    """最小 DataFrame 替身：支持 iterrows()。"""

    def iterrows(self):
        for i, row in enumerate(self):
            yield i, row


def test_cache_roundtrip(tmp_path, monkeypatch):
    from finengine import config
    from finengine.market.source import cache_get, cache_put

    monkeypatch.setattr(config, "data_dir", lambda: tmp_path)
    # cache_get/put 使用 engine 连接的固定库，这里直接测核心逻辑：
    # 写 → 立即读（TTL 内）→ 返回数据
    key = "test_key_1"
    cache_put(key, {"v": 42})
    got = cache_get(key, 3600)
    assert got == {"v": 42}


def test_cache_expired(tmp_path, monkeypatch):
    """过期缓存返回 None。"""
    import datetime

    from finengine import config
    from finengine.market.source import cache_get

    monkeypatch.setattr(config, "data_dir", lambda: tmp_path)
    with SessionLocal() as session:
        session.add(
            MarketCache(
                key="test_key_2",
                data_json=json.dumps({"v": 1}),
                fetched_at=datetime.datetime.now() - datetime.timedelta(hours=25),
            )
        )
        session.commit()
    assert cache_get("test_key_2", 3600) is None


def test_search_stocks_mocked(monkeypatch):
    """搜索逻辑：mock 掉 akshare 的股票列表。"""
    from finengine.market import source

    class FakeAk:
        @staticmethod
        def stock_info_a_code_name():
            return FakeDF(
                [
                    {"code": "601091", "name": "沈鼓集团"},
                    {"code": "300750", "name": "宁德时代"},
                    {"code": "601766", "name": "中国中车"},
                ]
            )

    monkeypatch.setattr(source, "_ak", lambda: FakeAk)
    # 清掉缓存影响
    with SessionLocal() as session:
        row = session.get(MarketCache, "a_stock_list")
        if row:
            session.delete(row)
            session.commit()
    hits = source.search_stocks("沈鼓")
    assert hits[0]["code"] == "601091"
    assert source.search_stocks("601091")[0]["name"] == "沈鼓集团"
    assert source.search_stocks("zzz") == []


def test_comparison_shape_mocked(monkeypatch):
    """对比汇总的数据结构（mock 财务与行情）。"""
    from finengine.market import source

    monkeypatch.setattr(source, "get_financials", lambda code, refresh=False: {
        "2025": {"营业收入": 1012221.24, "归母净利润": 73947.17, "毛利率": 26.08},
    })
    monkeypatch.setattr(source, "get_valuation", lambda codes, refresh=False: {
        "601091": {"name": "沈鼓集团", "pe": 18.5, "pb": 2.1, "market_cap": 2.5e10}
    })
    result = source.get_comparison(["601091"])
    assert result["companies"][0]["year"] == "2025"
    assert result["companies"][0]["financials"]["营业收入"] == 1012221.24
    assert result["companies"][0]["valuation"]["pe"] == 18.5
    assert "note" in result
