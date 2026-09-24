"""AI 模块测试（不实际调用外部 API，只测本地逻辑）。"""

from finengine.ai.gateway import PROVIDERS
from finengine.ai.qa import _build_prompt
from finengine.ai.security import decrypt, encrypt
from finengine.search.fts import expand_query


def test_encrypt_decrypt_roundtrip():
    secret = "sk-test-abcdef123456"
    stored = encrypt(secret)
    assert stored != secret
    assert decrypt(stored) == secret
    assert encrypt("") == ""
    assert decrypt("") == ""


def test_provider_templates_complete():
    assert "deepseek" in PROVIDERS and "claude" in PROVIDERS
    for pid, cfg in PROVIDERS.items():
        assert cfg["name"] and cfg["default_model"]
        assert cfg["kind"] in ("openai", "anthropic")


def test_synonym_expansion():
    terms = expand_query("主要客户情况")
    assert "前五大客户" in terms and "主要客户" in terms
    # 无同义词的词返回自身
    assert expand_query("行业格局") == ["行业格局"]


def test_prompt_includes_page_citations_and_rules():
    chunks = [
        {"file_id": 1, "page_no": 41, "text": "应收账款风险说明段落"},
        {"file_id": 1, "page_no": 33, "text": "营业收入数据段落"},
    ]
    messages = _build_prompt("应收账款为什么增长？", chunks)
    system, user = messages[0]["content"], messages[1]["content"]
    # 铁律：标注出处 + 禁止编造
    assert "第X页" in system and "严禁编造" in system
    # 用户消息包含片段与页码
    assert "[片段1｜第41页]" in user
    assert "[片段2｜第33页]" in user
    assert "应收账款为什么增长？" in user
