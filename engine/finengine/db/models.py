"""数据模型。

核心原则（全产品的地基）：
每一条财务数据、每个搜索命中都带"出处四元组"
= file_id + 页码 + 页内坐标 + 原始文字。
"""

import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# 文件解析状态
STATUS_UPLOADED = "uploaded"  # 已上传，未解析
STATUS_PARSING = "parsing"  # 解析中
STATUS_READY = "ready"  # 解析完成
STATUS_FAILED = "failed"  # 解析失败


class Project(Base):
    """尽调/研究项目：如"XX公司 IPO 尽调"。"""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    company_name: Mapped[str | None] = mapped_column(String(200))  # 标的公司名（可选）
    company_code: Mapped[str | None] = mapped_column(String(20))  # 证券代码（可选）
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

    files: Mapped[list["File"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class File(Base):
    """项目下的一份资料文件（招股书/年报/研报等）。"""

    __tablename__ = "files"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    original_name: Mapped[str] = mapped_column(String(500))  # 用户看到的文件名
    stored_name: Mapped[str] = mapped_column(String(100))  # 磁盘上的文件名（uuid）
    file_type: Mapped[str] = mapped_column(String(10))  # pdf / excel
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default=STATUS_UPLOADED, index=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    parse_progress: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    error: Mapped[str | None] = mapped_column(Text)
    # 印刷页码与 PDF 页序的偏移（M3 做页码映射时用；0 = 一致）
    page_offset: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

    project: Mapped[Project] = relationship(back_populates="files")
    pages: Mapped[list["Page"]] = relationship(back_populates="file", cascade="all, delete-orphan")


class Page(Base):
    """文件每页的文字（搜索、RAG、异常溯源的基础）。"""

    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id"), index=True)
    page_no: Mapped[int] = mapped_column(Integer)  # PDF 页序，从 1 开始
    text: Mapped[str] = mapped_column(Text, default="")

    file: Mapped[File] = relationship(back_populates="pages")


class FinancialLine(Base):
    """从文件中提取的原始财务行（出处四元组所在）。"""

    __tablename__ = "financial_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id"), index=True)
    indicator: Mapped[str] = mapped_column(String(100), index=True)  # 标准指标名
    period: Mapped[str] = mapped_column(String(30), index=True)  # 如"2025年度"
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(10))  # 万元/元/%
    # ---- 出处四元组 ----
    page_no: Mapped[int] = mapped_column(Integer)
    bbox: Mapped[str | None] = mapped_column(String(200))  # 页内坐标 "x0,y0,x1,y1"
    label: Mapped[str] = mapped_column(String(200))  # 原始行标签（原始文字）
    derived: Mapped[str | None] = mapped_column(String(200))  # 派生公式（如"净利润/营业收入"）


class Indicator(Base):
    """项目级标准化指标序列（跨文件按年份聚合后的最终值）。"""

    __tablename__ = "indicators"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    period: Mapped[str] = mapped_column(String(30))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(10))
    source_file_id: Mapped[int | None] = mapped_column(ForeignKey("files.id"))
    source_page: Mapped[int | None] = mapped_column(Integer)
    derived: Mapped[str | None] = mapped_column(String(200))
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Anomaly(Base):
    """发现的财务异常（M5 规则引擎产出）。"""

    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    rule_id: Mapped[str] = mapped_column(String(50))  # 规则标识
    title: Mapped[str] = mapped_column(String(200))  # 异常结论（人话）
    description: Mapped[str] = mapped_column(Text)  # 计算过程（中文公式+数据）
    severity: Mapped[str] = mapped_column(String(10), default="medium")  # low/medium/high
    data_json: Mapped[str] = mapped_column(Text)  # 涉及的数据点（含出处），JSON
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())


class Setting(Base):
    """用户设置（AI Key 加密后存这里，M7 用）。"""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class Comparable(Base):
    """项目添加的同行业可比公司（P1 同行对比）。"""

    __tablename__ = "comparables"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    code: Mapped[str] = mapped_column(String(20))  # 证券代码，如 601091
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())


class MarketCache(Base):
    """市场数据缓存（行情快照、全市场列表、个股财务，JSON 存储带抓取时间）。"""

    __tablename__ = "market_cache"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    data_json: Mapped[str] = mapped_column(Text, default="")
    fetched_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)
