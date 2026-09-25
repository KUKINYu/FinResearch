"""解析流水线：上传文件 → 逐页提取文字 → 财务提取 → 数据入库。

进度机制：files.parse_progress 0-100（前 90% 为逐页文字提取，
后 10% 为财务提取），界面轮询即可显示进度条。
"""

import threading
import uuid
from pathlib import Path

import pdfplumber
from sqlalchemy import select

from .. import config
from ..db import SessionLocal
from ..db.models import (
    STATUS_FAILED,
    STATUS_PARSING,
    STATUS_READY,
    File,
    FinancialLine,
    Indicator,
    Page,
)
from ..extract import extract_document


def project_files_dir(project_id: int) -> Path:
    """项目文件的磁盘目录（原件只读存储，解析永不改原件）。"""
    d = config.data_dir() / "projects" / str(project_id) / "files"
    d.mkdir(parents=True, exist_ok=True)
    return d


def create_file_record(
    project_id: int, original_name: str, data: bytes, file_type: str
) -> File:
    """保存上传内容到磁盘并建 File 记录。"""
    stored = f"{uuid.uuid4().hex}.{file_type}"
    dest = project_files_dir(project_id) / stored
    dest.write_bytes(data)
    with SessionLocal() as session:
        f = File(
            project_id=project_id,
            original_name=original_name,
            stored_name=stored,
            file_type=file_type,
            size_bytes=len(data),
        )
        session.add(f)
        session.commit()
        session.refresh(f)
        return File(
            id=f.id,
            project_id=f.project_id,
            original_name=f.original_name,
            stored_name=f.stored_name,
            file_type=f.file_type,
            size_bytes=f.size_bytes,
            status=f.status,
            page_count=f.page_count,
            parse_progress=f.parse_progress,
            error=f.error,
        )


def parse_file(file_id: int) -> None:
    """解析一个文件（后台线程执行）。

    PDF：逐页提取文字存 pages 表，再跑财务提取存 financial_lines
    + indicators。Excel：M4 里程碑实现解析，这里直接置为就绪。
    """
    with SessionLocal() as session:
        f = session.get(File, file_id)
        if f is None:
            return
        f.status = STATUS_PARSING
        f.parse_progress = 0
        f.error = None
        session.commit()
        path = project_files_dir(f.project_id) / f.stored_name

    try:
        if f.file_type == "excel":
            _finish_excel(file_id)
        else:
            _parse_pdf(file_id, path)
    except Exception as e:  # noqa: BLE001 解析失败要落库供界面显示
        with SessionLocal() as session:
            f = session.get(File, file_id)
            f.status = STATUS_FAILED
            f.error = str(e)[:500]
            session.commit()


def _parse_pdf(file_id: int, path: Path) -> None:
    """PDF 解析：逐页文字（90% 进度）→ 财务提取（10% 进度）。"""
    with pdfplumber.open(path) as pdf:
        total = len(pdf.pages)
        with SessionLocal() as session:
            f = session.get(File, file_id)
            f.page_count = total
            # 重复解析：先清掉该文件的旧页面，避免翻倍
            old_pages = session.execute(select(Page).where(Page.file_id == file_id)).scalars().all()
            for p in old_pages:
                session.delete(p)
            session.commit()
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            with SessionLocal() as session:
                session.add(Page(file_id=file_id, page_no=i, text=text))
                f = session.get(File, file_id)
                f.parse_progress = int(i / total * 90)
                session.commit()

    # 财务提取
    with SessionLocal() as session:
        f = session.get(File, file_id)
        f.parse_progress = 92
        session.commit()
    _extract_financials(file_id, path)

    # 异常检测（M5：解析完成后自动跑规则引擎）+ 搜索索引（M6）
    with SessionLocal() as session:
        f = session.get(File, file_id)
        f.parse_progress = 97
        session.commit()
        try:
            from ..api import analyze_project

            analyze_project(f.project_id, session)
        except Exception as e:  # noqa: BLE001 规则失败不阻塞解析完成
            print(f"[finengine] 异常检测失败：{e}")
        try:
            from ..search.fts import build_index

            build_index()
        except Exception as e:  # noqa: BLE001
            print(f"[finengine] 搜索索引失败：{e}")
        try:
            from ..notes_service import add_data_update_note

            add_data_update_note(f.project_id, file_id)
        except Exception as e:  # noqa: BLE001
            print(f"[finengine] 研究笔记生成失败：{e}")

    with SessionLocal() as session:
        f = session.get(File, file_id)
        f.status = STATUS_READY
        f.parse_progress = 100
        session.commit()


def _extract_financials(file_id: int, path: Path) -> None:
    """跑财务提取器，结果写入 financial_lines 与 indicators。"""
    doc = extract_document(path)
    with SessionLocal() as session:
        f = session.get(File, file_id)
        project_id = f.project_id
        # 重复解析时先清掉该文件的旧提取结果
        old = session.execute(
            select(FinancialLine).where(FinancialLine.file_id == file_id)
        ).scalars().all()
        for line in old:
            session.delete(line)
        session.commit()
        lines = 0
        for indicator, periods in doc["indicators"].items():
            for period, dp in periods.items():
                session.add(
                    FinancialLine(
                        file_id=file_id,
                        indicator=indicator,
                        period=period,
                        value=dp.value,
                        unit=dp.unit,
                        page_no=dp.source.page,
                        bbox=(
                            ",".join(f"{v:.1f}" for v in dp.source.bbox)
                            if dp.source.bbox
                            else None
                        ),
                        label=dp.source.label,
                        derived=getattr(dp, "derived", None),
                    )
                )
                lines += 1
                # 项目级指标：跨文件聚合，同指标同期间首次出现优先
                existing = session.execute(
                    select(Indicator).where(
                        Indicator.project_id == project_id,
                        Indicator.name == indicator,
                        Indicator.period == period,
                    )
                ).scalar_one_or_none()
                if existing is None:
                    session.add(
                        Indicator(
                            project_id=project_id,
                            name=indicator,
                            period=period,
                            value=dp.value,
                            unit=dp.unit,
                            source_file_id=file_id,
                            source_page=dp.source.page,
                            derived=getattr(dp, "derived", None),
                        )
                    )
        f = session.get(File, file_id)
        f.parse_progress = 99
        session.commit()
        return lines


def _finish_excel(file_id: int) -> None:
    """Excel 解析（M4 实现），当前直接置为就绪。"""
    with SessionLocal() as session:
        f = session.get(File, file_id)
        f.status = STATUS_READY
        f.parse_progress = 100
        session.commit()


def start_parse(file_id: int) -> None:
    """启动后台解析线程。"""
    threading.Thread(target=parse_file, args=(file_id,), daemon=True).start()
