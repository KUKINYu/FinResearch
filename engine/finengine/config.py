"""路径与运行配置：用户数据目录、缓存目录、数据库位置。"""

from pathlib import Path


def data_dir() -> Path:
    """用户数据目录（默认 文档\\FinResearch），不存在则创建。

    存放：项目文件原件、解析缓存、SQLite 数据库。
    注意：解析缓存可随时删除重建，不是关键数据；文件原件只读，永不修改。
    """
    base = Path.home() / "Documents" / "FinResearch"
    base.mkdir(parents=True, exist_ok=True)
    return base


def cache_dir() -> Path:
    """解析缓存目录（页面图片、OCR 结果、向量索引），可安全删除重建。"""
    p = data_dir() / "cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


def db_path() -> Path:
    """SQLite 数据库文件路径。"""
    return data_dir() / "finresearch.db"
