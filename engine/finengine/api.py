"""REST API 路由（M2：项目/文件管理 + 解析流水线；M3：阅读器与校对；M5：异常检测）。

所有接口都在 require_token 中间件保护之下（见 main.py）。
"""

import json

from fastapi import APIRouter, Depends, File as FastAPIFile, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import SessionLocal
from .db.models import Anomaly, File, FinancialLine, Indicator, Page, Project
from .pipeline import create_file_record, start_parse
from .pipeline.parse_service import project_files_dir

router = APIRouter(prefix="/api")


def get_session():
    with SessionLocal() as session:
        yield session


class ProjectIn(BaseModel):
    name: str
    company_name: str | None = None
    company_code: str | None = None


def project_to_dict(p: Project) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "company_name": p.company_name,
        "company_code": p.company_code,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def file_to_dict(f: File) -> dict:
    return {
        "id": f.id,
        "project_id": f.project_id,
        "original_name": f.original_name,
        "file_type": f.file_type,
        "size_bytes": f.size_bytes,
        "status": f.status,
        "page_count": f.page_count,
        "parse_progress": f.parse_progress,
        "error": f.error,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


# ---------- 项目 ----------

@router.post("/projects")
def create_project(body: ProjectIn, session: Session = Depends(get_session)):
    p = Project(name=body.name, company_name=body.company_name, company_code=body.company_code)
    session.add(p)
    session.commit()
    session.refresh(p)
    return project_to_dict(p)


@router.get("/projects")
def list_projects(session: Session = Depends(get_session)):
    projects = session.execute(select(Project).order_by(Project.created_at.desc())).scalars().all()
    return [project_to_dict(p) for p in projects]


@router.get("/projects/{project_id}")
def get_project(project_id: int, session: Session = Depends(get_session)):
    p = session.get(Project, project_id)
    if p is None:
        raise HTTPException(404, "项目不存在")
    result = project_to_dict(p)
    files = session.execute(
        select(File).where(File.project_id == project_id).order_by(File.created_at.desc())
    ).scalars().all()
    result["files"] = [file_to_dict(f) for f in files]
    return result


@router.delete("/projects/{project_id}")
def delete_project(project_id: int, session: Session = Depends(get_session)):
    p = session.get(Project, project_id)
    if p is None:
        raise HTTPException(404, "项目不存在")
    session.delete(p)
    session.commit()
    return {"ok": True}


# ---------- 文件上传与解析 ----------

@router.post("/projects/{project_id}/files")
async def upload_file(
    project_id: int, file: UploadFile = FastAPIFile(...), session: Session = Depends(get_session)
):
    p = session.get(Project, project_id)
    if p is None:
        raise HTTPException(404, "项目不存在")
    name = file.filename or "未命名文件"
    suffix = (name.rsplit(".", 1)[-1].lower() if "." in name else "")
    if suffix not in ("pdf", "xlsx", "xls"):
        raise HTTPException(400, "仅支持 PDF 与 Excel 文件")
    data = await file.read()
    if not data:
        raise HTTPException(400, "文件为空")
    f = create_file_record(project_id, name, data, "excel" if suffix in ("xlsx", "xls") else "pdf")
    # 上传后自动开始解析
    start_parse(f.id)
    return file_to_dict(f)


@router.post("/files/{file_id}/parse")
def reparse_file(file_id: int, session: Session = Depends(get_session)):
    f = session.get(File, file_id)
    if f is None:
        raise HTTPException(404, "文件不存在")
    start_parse(file_id)
    return {"ok": True}


@router.get("/files/{file_id}")
def get_file(file_id: int, session: Session = Depends(get_session)):
    f = session.get(File, file_id)
    if f is None:
        raise HTTPException(404, "文件不存在")
    return file_to_dict(f)


@router.get("/files/{file_id}/pages/{page_no}")
def get_page_text(file_id: int, page_no: int, session: Session = Depends(get_session)):
    page = session.execute(
        select(Page).where(Page.file_id == file_id, Page.page_no == page_no)
    ).scalar_one_or_none()
    if page is None:
        raise HTTPException(404, "页面不存在")
    return {"file_id": file_id, "page_no": page_no, "text": page.text}


@router.get("/files/{file_id}/content")
def get_file_content(file_id: int, session: Session = Depends(get_session)):
    """PDF 原文内容（供界面 pdf.js 渲染；大文件走内存返回，P0 够用）。"""
    f = session.get(File, file_id)
    if f is None:
        raise HTTPException(404, "文件不存在")
    path = project_files_dir(f.project_id) / f.stored_name
    if not path.exists():
        raise HTTPException(404, "文件内容缺失")
    media = "application/pdf" if f.file_type == "pdf" else "application/octet-stream"
    return Response(content=path.read_bytes(), media_type=media)


@router.get("/files/{file_id}/lines")
def get_financial_lines(file_id: int, session: Session = Depends(get_session)):
    """文件级提取明细（校对界面数据源：含出处四元组与页内坐标）。"""
    rows = session.execute(
        select(FinancialLine)
        .where(FinancialLine.file_id == file_id)
        .order_by(FinancialLine.indicator, FinancialLine.period)
    ).scalars().all()
    return [
        {
            "id": r.id,
            "indicator": r.indicator,
            "period": r.period,
            "value": r.value,
            "unit": r.unit,
            "page_no": r.page_no,
            "bbox": r.bbox,
            "label": r.label,
            "derived": r.derived,
        }
        for r in rows
    ]


# ---------- 财务指标 ----------

@router.get("/projects/{project_id}/indicators")
def get_indicators(project_id: int, session: Session = Depends(get_session)):
    rows = session.execute(
        select(Indicator).where(Indicator.project_id == project_id).order_by(Indicator.name, Indicator.period)
    ).scalars().all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "period": r.period,
            "value": r.value,
            "unit": r.unit,
            "source_file_id": r.source_file_id,
            "source_page": r.source_page,
            "derived": r.derived,
        }
        for r in rows
    ]


class IndicatorUpdate(BaseModel):
    value: float | None = None
    unit: str | None = None


def analyze_project(project_id: int, session: Session) -> list[dict]:
    """运行规则引擎并把异常写入 Anomaly 表（供解析完成后自动调用）。"""
    from .rules import run_rules
    from .rules.engine import Point

    rows = session.execute(
        select(Indicator).where(Indicator.project_id == project_id)
    ).scalars().all()
    series: dict[str, dict[str, Point]] = {}
    for r in rows:
        series.setdefault(r.name, {})[r.period] = Point(
            value=r.value,
            unit=r.unit,
            source_file_id=r.source_file_id,
            source_page=r.source_page,
        )
    anomalies = run_rules(series)
    # 覆盖式存储：每次分析先清掉该项目旧异常
    old = session.execute(
        select(Anomaly).where(Anomaly.project_id == project_id)
    ).scalars().all()
    for a in old:
        session.delete(a)
    for a in anomalies:
        session.add(
            Anomaly(
                project_id=project_id,
                rule_id=a["rule_id"],
                title=a["title"],
                description=a["description"],
                severity=a["severity"],
                data_json=json.dumps(a["data_points"], ensure_ascii=False),
            )
        )
    session.commit()
    return anomalies


@router.patch("/indicators/{indicator_id}")
def update_indicator(indicator_id: int, body: IndicatorUpdate, session: Session = Depends(get_session)):
    """校对：修正指标数值或单位（人工校对是产品设计的一部分）。"""
    r = session.get(Indicator, indicator_id)
    if r is None:
        raise HTTPException(404, "指标不存在")
    if body.value is not None:
        r.value = body.value
    if body.unit is not None:
        r.unit = body.unit
    session.commit()
    return {"ok": True}


@router.delete("/indicators/{indicator_id}")
def delete_indicator(indicator_id: int, session: Session = Depends(get_session)):
    """校对：删除错误数据（如混入的子公司数据）。"""
    r = session.get(Indicator, indicator_id)
    if r is None:
        raise HTTPException(404, "指标不存在")
    session.delete(r)
    session.commit()
    return {"ok": True}


# ---------- 异常检测（M5） ----------

@router.post("/projects/{project_id}/analyze")
def analyze(project_id: int, session: Session = Depends(get_session)):
    """运行异常检测规则（可重复执行，覆盖旧结果）。"""
    p = session.get(Project, project_id)
    if p is None:
        raise HTTPException(404, "项目不存在")
    return {"anomalies": analyze_project(project_id, session)}


@router.get("/projects/{project_id}/anomalies")
def get_anomalies(project_id: int, session: Session = Depends(get_session)):
    rows = session.execute(
        select(Anomaly)
        .where(Anomaly.project_id == project_id)
        .order_by(Anomaly.severity.desc(), Anomaly.id.desc())
    ).scalars().all()
    return [
        {
            "id": r.id,
            "rule_id": r.rule_id,
            "title": r.title,
            "description": r.description,
            "severity": r.severity,
            "data_points": json.loads(r.data_json) if r.data_json else [],
        }
        for r in rows
    ]


# ---------- 全文搜索（M6） ----------

class SearchIn(BaseModel):
    query: str
    file_id: int | None = None


@router.post("/projects/{project_id}/search")
def search_project(project_id: int, body: SearchIn, session: Session = Depends(get_session)):
    from .search.fts import search as fts_search

    q = (body.query or "").strip()
    if len(q) < 2:
        return {"results": []}
    file_ids: list[int] = []
    if body.file_id is not None:
        file_ids = [body.file_id]
    else:
        file_ids = [
            f.id for f in session.execute(select(File).where(File.project_id == project_id)).scalars()
        ]
    if not file_ids:
        return {"results": []}
    results = fts_search(file_ids, q)
    # 补文件名（界面显示）
    names = {
        f.id: f.original_name
        for f in session.execute(select(File).where(File.id.in_(file_ids))).scalars()
    }
    for r in results:
        r["file_name"] = names.get(r["file_id"], "")
    return {"results": results}
