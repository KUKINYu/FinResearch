"""文档检索器：按页切块 → 本地向量索引 → 语义检索（带页码溯源）。

设计（Spike C 验证）：
- 切块单位 = 页内段落：块元数据 (file, page, para_idx)
- 向量：BAAI/bge-small-zh-v1.5（中文检索效果好的小模型，CPU 可跑）
- 检索返回 top-K 块 + 页码，界面/AI 都用这个页码引用原文
- 存储：Spike 用内存 numpy（验证检索质量）；M6 换成持久化向量库

注意（M3/M7 待办）：招股书印刷页码与 PDF 页序可能不一致，
需"页码映射表"（每份文件存偏移），保证 AI 引用页码与用户
实际翻到的页码一致。
"""

import re
from dataclasses import dataclass

import numpy as np
from fastembed import TextEmbedding

# 块大小上限（字符数，约 200 tokens 内，适配小模型的上下文）
CHUNK_MAX_CHARS = 400
# 检索返回条数
TOP_K = 5


@dataclass
class SearchHit:
    """一个检索命中：原文片段 + 出处（页码是关键）。"""

    text: str
    file: str
    page: int
    para_idx: int
    score: float

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "file": self.file,
            "page": self.page,
            "para_idx": self.para_idx,
            "score": round(float(self.score), 4),
        }


def chunk_page(page_no: int, text: str, file_name: str) -> list[tuple[str, dict]]:
    """把一页文字切成块，返回 [(块文本, 元数据), ...]。

    按段落切，超长段落硬切；丢弃过短/纯页码噪声块。
    """
    text = text or ""
    paras = [p.strip() for p in re.split(r"\n{2,}", text)]
    chunks: list[tuple[str, dict]] = []
    for para_idx, para in enumerate(paras):
        if len(para) < 10:  # 噪声（页码、单行标题等）
            continue
        if len(para) <= CHUNK_MAX_CHARS:
            chunks.append((para, {"page": page_no, "para_idx": para_idx}))
            continue
        # 超长段落按句号硬切
        pieces = [s.strip() + "。" for s in re.split(r"。|；", para) if s.strip()]
        buf = ""
        for piece in pieces:
            if len(buf) + len(piece) > CHUNK_MAX_CHARS and buf:
                chunks.append((buf, {"page": page_no, "para_idx": para_idx}))
                buf = piece
            else:
                buf += piece
        if len(buf) >= 10:
            chunks.append((buf, {"page": page_no, "para_idx": para_idx}))
    return chunks


class DocumentRetriever:
    """单文档检索器（P0 项目级：一个项目多个文档时各建一个实例）。"""

    def __init__(self, file_name: str, model_name: str = "BAAI/bge-small-zh-v1.5"):
        self.file_name = file_name
        self.model = TextEmbedding(model_name=model_name)
        self.texts: list[str] = []
        self.metas: list[dict] = []
        self.embeddings: np.ndarray | None = None

    def add_page(self, page_no: int, text: str) -> None:
        """追加一页的块（先切块收集，索引前再统一向量化）。"""
        for chunk, meta in chunk_page(page_no, text, self.file_name):
            self.texts.append(chunk)
            self.metas.append(meta)

    def build_index(self) -> int:
        """向量化全部块（CPU 运行，数百页约几分钟，界面需显示进度）。"""
        self.embeddings = np.array(
            list(self.model.embed(self.texts, batch_size=16)), dtype=np.float32
        )
        # 归一化便于余弦相似度
        norms = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.embeddings /= norms
        return len(self.texts)

    def search(self, query: str, top_k: int = TOP_K) -> list[SearchHit]:
        """语义检索，返回带页码出处的 top-k 片段。"""
        if self.embeddings is None:
            raise RuntimeError("索引未构建：先 build_index()")
        q = np.array(list(self.model.embed([query])), dtype=np.float32)
        q = q / (np.linalg.norm(q) + 1e-9)
        scores = (self.embeddings @ q.T).ravel()
        idx = np.argsort(-scores)[:top_k]
        return [
            SearchHit(
                text=self.texts[i],
                file=self.file_name,
                page=self.metas[i]["page"],
                para_idx=self.metas[i]["para_idx"],
                score=float(scores[i]),
            )
            for i in idx
        ]
