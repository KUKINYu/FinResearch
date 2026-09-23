"""REST API 路由（M2：项目/文件管理 + 解析流水线）。

所有接口都在 require_token 中间件保护之下（见 main.py）。
"""

from fastapi import APIRouter, Depends, File as FastAPIFile, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import SessionLocal
from .db.models import File, Indicator, Page, Project
from .pipeline import create_file_record, start_parse

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


# ---------- 财务指标 ----------

@router.get("/projects/{project_id}/indicators")
def get_indicators(project_id: int, session: Session = Depends(get_session)):
    rows = session.execute(
        select(Indicator).where(Indicator.project_id == project_id).order_by(Indicator.name, Indicator.period)
    ).scalars().all()
    return [
        {
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
