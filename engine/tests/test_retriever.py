"""检索切块逻辑测试（Spike C）。"""

from finengine.search.retriever import chunk_page


def test_chunk_page_paragraphs():
    text = "第一段内容，这里是招股说明书正文。\n\n第二段内容，继续介绍公司情况。"
    chunks = chunk_page(1, text, "test.pdf")
    assert len(chunks) == 2
    assert chunks[0][0].startswith("第一段")
    assert chunks[0][1] == {"page": 1, "para_idx": 0}
    assert chunks[1][1] == {"page": 1, "para_idx": 1}


def test_chunk_page_drops_noise():
    # 页码、单行标题等过短内容被丢弃
    text = "1-1-46\n\n招股说明书正文内容，这一段足够长，不应该被丢弃掉。"
    chunks = chunk_page(1, text, "test.pdf")
    assert len(chunks) == 1
    assert "正文内容" in chunks[0][0]


def test_chunk_page_long_paragraph_split():
    # 超长段落按句硬切，每块不超过上限
    sentence = "公司持续投入研发以提升产品竞争力，并积极拓展下游应用领域。"
    text = sentence * 30  # 约 1000 字
    chunks = chunk_page(1, text, "test.pdf")
    assert len(chunks) > 1
    assert all(len(c) <= 400 + 5 for c, _ in chunks)


def test_chunk_page_empty():
    assert chunk_page(1, "", "test.pdf") == []
    assert chunk_page(1, None, "test.pdf") == []
