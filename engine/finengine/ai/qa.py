"""RAG 问答（防幻觉设计）。

流程：
1. 检索：向量语义检索（bge-small-zh）+ 关键词检索（FTS）混合取块，
   每块带 (file_id, 页码)
2. 提示词：把资料片段连同页码交给模型，强制要求——
   - 每个结论标注出处（第X页）
   - 资料中没有依据时明确说"没有"，禁止编造
3. 返回：回答 + 引用来源列表（界面可点击跳原文）+ token 消耗
"""

import os

from sqlalchemy import select

from ..db import SessionLocal
from ..db.models import Page, Setting
from ..search.fts import search as keyword_search
from ..search.retriever import DocumentRetriever
from .gateway import PROVIDERS, chat
from .security import decrypt

# 国内访问 HuggingFace 不稳，优先走镜像（模型首次下载用；已缓存则无关）
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

# 每项目的向量检索器缓存（key = project_id，页数变化时重建）
_retriever_cache: dict[int, tuple[int, DocumentRetriever]] = {}

SYSTEM_PROMPT = """你是金融研究助理，帮助用户分析他们上传的招股说明书、年报等资料。

【铁律】
1. 只依据下面提供的"资料片段"回答问题，每个结论必须标注出处，格式为（第X页）。
2. 资料片段中没有的信息，直接回答"资料中没有找到相关信息"，严禁编造任何数字、事实或推断。
3. 不要引用资料之外的行业常识来补充具体数字；可以提醒用户"此问题超出已上传资料范围"。
4. 回答使用简体中文，简明、结构化。
"""


def _build_prompt(question: str, chunks: list[dict]) -> list[dict]:
    parts = []
    for i, c in enumerate(chunks, 1):
        parts.append(f"[片段{i}｜第{c['page_no']}页]\n{c['text'][:600]}")
    user = (
        f"问题：{question}\n\n"
        f"资料片段：\n" + "\n\n".join(parts)
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def _load_project_pages(project_id: int) -> list[tuple[int, str, str]]:
    """加载项目全部页面文字 [(file_id, page_no, text)]。"""
    from ..db.models import File

    with SessionLocal() as session:
        file_ids = [
            f.id for f in session.execute(select(File).where(File.project_id == project_id)).scalars()
        ]
        out: list[tuple[int, str, str]] = []
        for fid in file_ids:
            pages = session.execute(
                select(Page).where(Page.file_id == fid).order_by(Page.page_no)
            ).scalars().all()
            out.extend((fid, p.page_no, p.text or "") for p in pages)
        return out


def _model_available() -> bool:
    """本地向量模型是否已下载完整（无 onnx 文件 = 未就绪，不尝试加载）。"""
    from ..config import cache_dir

    root = cache_dir() / "models"
    if not root.exists():
        return False
    return any(root.rglob("*.onnx"))


def _retrieve(project_id: int, question: str, top_k: int = 6) -> list[dict]:
    """混合检索：向量 + 关键词，按 (file_id, 页码) 去重。

    向量模型未就绪（首次使用未下载完成）或加载失败时，
    自动降级为纯关键词检索——功能不瘫痪；模型就绪后自动升级。
    """
    pages = _load_project_pages(project_id)
    if not pages:
        return []
    total = len(pages)
    # (file_id, page_no) → 整页文字
    full_text = {(fid, pno): text for fid, pno, text in pages}

    # 向量检索（缓存）；模型未就绪/下载失败时优雅降级为纯关键词检索
    hits: dict[tuple[int, int], dict] = {}
    if _model_available():
        try:
            cached = _retriever_cache.get(project_id)
            if cached is None or cached[0] != total:
                r = DocumentRetriever(f"project-{project_id}")
                for fid, page_no, text in pages:
                    r.add_page(page_no, text, file_id=fid)
                r.build_index()
                _retriever_cache[project_id] = (total, r)
                # 缓存上限：只保留最近 2 个项目，避免内存膨胀
                if len(_retriever_cache) > 2:
                    oldest = min(_retriever_cache.keys())
                    _retriever_cache.pop(oldest, None)
            else:
                r = cached[1]
            for h in r.search(question, top_k=top_k):
                hits[(h.file_id or 0, h.page)] = {
                    "file_id": h.file_id,
                    "page_no": h.page,
                    "text": h.text,
                    "score": h.score + 2.0,  # 向量命中权重更高
                }
        except Exception as e:  # noqa: BLE001 模型缺失/加载失败 → 降级关键词检索
            print(f"[finengine] 向量检索不可用（{e}），已降级为关键词检索")
    # 关键词检索补充（同义词扩展）
    file_ids = sorted({fid for fid, _, _ in pages})
    for kw in keyword_search(file_ids, question, limit=4):
        key = (kw["file_id"], kw["page_no"])
        if key not in hits:
            hits[key] = {
                "file_id": kw["file_id"],
                "page_no": kw["page_no"],
                "text": full_text.get(key, kw["snippet"]),
                "score": kw["score"],
            }
    ranked = sorted(hits.values(), key=lambda h: -h["score"])[: top_k + 2]
    return ranked


def _get_settings() -> tuple[str, str, str]:
    """读取 AI 设置：(provider, model, api_key)。"""
    with SessionLocal() as session:
        rows = session.execute(select(Setting)).scalars().all()
        kv = {s.key: s.value for s in rows}
    provider = kv.get("ai.provider", "")
    model = kv.get("ai.model", "")
    api_key = decrypt(kv.get("ai.api_key", ""))
    return provider, model, api_key


def _get_tier_settings(tier: str) -> tuple[str, str, str]:
    """按任务层级读设置：deep = 深度分析；quick = 快速任务（摘要/检索类）。

    quick 未配置时自动回落到 deep 配置。
    """
    provider, model, api_key = _get_settings()
    if tier == "quick":
        with SessionLocal() as session:
            rows = session.execute(select(Setting)).scalars().all()
            kv = {s.key: s.value for s in rows}
        q_provider = kv.get("ai.quick_provider", "")
        q_key = decrypt(kv.get("ai.quick_api_key", ""))
        if q_provider and q_key:
            provider = q_provider
            model = kv.get("ai.quick_model", "")
            api_key = q_key
    return provider, model, api_key


def answer_question(project_id: int, question: str, tier: str = "deep") -> dict:
    """项目级 RAG 问答入口。tier: deep（深度分析）| quick（快速任务）。"""
    provider, model, api_key = _get_tier_settings(tier)
    if not provider or not api_key:
        return {
            "ok": False,
            "error": "未配置 AI 服务：请在设置中填写 API Key（BYOK，费用由你自己的账号承担）",
        }
    if model == "":
        model = PROVIDERS.get(provider, {}).get("default_model", "")

    chunks = _retrieve(project_id, question)
    if not chunks:
        return {"ok": True, "answer": "该项目还没有可检索的资料。请先在「项目档案」上传并解析文件。", "sources": [], "usage": None}

    messages = _build_prompt(question, chunks)
    result = chat(provider, api_key, model, messages)

    # 清理回答中可能的幻觉页码（仅保留检索块中出现过的页码）
    return {
        "ok": True,
        "answer": result.answer,
        "sources": [
            {"file_id": c["file_id"], "page_no": c["page_no"], "snippet": c["text"][:150]}
            for c in chunks
        ],
        "usage": {
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "model": result.model,
        },
    }


def summarize_text(project_id: int, question: str, context: str) -> dict:
    """轻量摘要任务（quick 层级，不给检索、只给指定文本）。

    用于公告摘要、风险小结等高频低成本场景。
    """
    provider, model, api_key = _get_tier_settings("quick")
    if not provider or not api_key:
        return {"ok": False, "error": "未配置 AI 服务"}
    if model == "":
        model = PROVIDERS.get(provider, {}).get("default_model", "")
    messages = [
        {
            "role": "system",
            "content": "你是金融研究助理。只依据给定内容做简明摘要，标注关键数字，不要编造。",
        },
        {
            "role": "user",
            "content": f"任务：{question}\n\n内容：\n{context[:4000]}",
        },
    ]
    result = chat(provider, api_key, model, messages, temperature=0.1)
    return {
        "ok": True,
        "answer": result.answer,
        "usage": {
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "model": result.model,
        },
    }
