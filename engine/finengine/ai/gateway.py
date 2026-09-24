"""BYOK 多模型网关：OpenAI 兼容接口 + Anthropic 官方接口。

设计（BYOK = 用户自带 Key，开发者零 AI 成本）：
- DeepSeek/通义千问(DashScope 兼容)/GLM/Kimi/OpenAI 都提供
  OpenAI 兼容接口，openai 库换 base_url 通吃；
- Claude 不提供 OpenAI 兼容端点，用 Anthropic 官方 SDK；
- 设置页每家预置模板（base_url/默认模型/注册链接），用户只粘 Key。
"""

from dataclasses import dataclass

# 预置服务商模板
PROVIDERS: dict[str, dict] = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
        "register_url": "https://platform.deepseek.com/",
        "kind": "openai",
    },
    "qwen": {
        "name": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "register_url": "https://dashscope.console.aliyun.com/",
        "kind": "openai",
    },
    "glm": {
        "name": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
        "register_url": "https://open.bigmodel.cn/",
        "kind": "openai",
    },
    "kimi": {
        "name": "Kimi（月之暗面）",
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
        "register_url": "https://platform.moonshot.cn/",
        "kind": "openai",
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "register_url": "https://platform.openai.com/",
        "kind": "openai",
    },
    "claude": {
        "name": "Claude（Anthropic）",
        "base_url": "",
        "default_model": "claude-sonnet-4-5",
        "register_url": "https://console.anthropic.com/",
        "kind": "anthropic",
    },
}


@dataclass
class ChatResult:
    answer: str
    model: str
    prompt_tokens: int
    completion_tokens: int


def chat(
    provider: str,
    api_key: str,
    model: str,
    messages: list[dict],
    temperature: float = 0.2,
) -> ChatResult:
    """调用模型对话。messages = [{"role": "system"|"user", "content": str}]"""
    cfg = PROVIDERS.get(provider)
    if cfg is None:
        raise ValueError(f"未知的服务商：{provider}")
    if cfg["kind"] == "openai":
        return _chat_openai_compat(cfg, api_key, model, messages, temperature)
    return _chat_anthropic(api_key, model, messages, temperature)


def _chat_openai_compat(cfg, api_key, model, messages, temperature) -> ChatResult:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=cfg["base_url"])
    resp = client.chat.completions.create(
        model=model, messages=messages, temperature=temperature
    )
    usage = resp.usage
    return ChatResult(
        answer=resp.choices[0].message.content or "",
        model=resp.model or model,
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
    )


def _chat_anthropic(api_key, model, messages, temperature) -> ChatResult:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    system = next((m["content"] for m in messages if m["role"] == "system"), None)
    user_msgs = [m for m in messages if m["role"] != "system"]
    resp = client.messages.create(
        model=model,
        max_tokens=2048,
        temperature=temperature,
        system=system or "",
        messages=user_msgs,
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    return ChatResult(
        answer=text,
        model=resp.model,
        prompt_tokens=resp.usage.input_tokens,
        completion_tokens=resp.usage.output_tokens,
    )
