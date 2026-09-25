"""FinResearch MCP 服务器（P1-6）。

让 Claude Desktop / Cursor 等任意支持 MCP 的客户端直接调用
FinResearch 的分析能力（项目、指标、异常、搜索、问答、无头分析）。

启动（engine 目录）：
  .venv\\Scripts\\python -m finengine.mcp_server
或运行 scripts\\run-mcp.bat

客户端配置示例（Claude Desktop claude_desktop_config.json）：
{
  "mcpServers": {
    "finresearch": {
      "command": "F:/于劭然/Fintech/engine/.venv/Scripts/python.exe",
      "args": ["-m", "finengine.mcp_server"]
    }
  }
}
"""

import sys
from pathlib import Path

from fastmcp import FastMCP

mcp = FastMCP("FinResearch 金融研究与尽调辅助")


@mcp.tool
def list_projects() -> list[dict]:
    """列出全部研究项目。"""
    from .db import SessionLocal
    from .db.models import Project

    with SessionLocal() as session:
        projects = session.query(Project).order_by(Project.id.desc()).all()
        return [
            {"id": p.id, "name": p.name, "company_name": p.company_name, "company_code": p.company_code}
            for p in projects
        ]


@mcp.tool
def get_indicators(project_id: int) -> list[dict]:
    """项目财务指标（含出处页码）。"""
    from .db import SessionLocal
    from .db.models import Indicator

    with SessionLocal() as session:
        rows = session.query(Indicator).filter_by(project_id=project_id).all()
        return [
            {
                "name": r.name,
                "period": r.period,
                "value": r.value,
                "unit": r.unit,
                "source_page": r.source_page,
            }
            for r in rows
        ]


@mcp.tool
def get_anomalies(project_id: int) -> list[dict]:
    """项目财务异常清单（含计算过程与出处）。"""
    import json

    from .db import SessionLocal
    from .db.models import Anomaly

    with SessionLocal() as session:
        rows = session.query(Anomaly).filter_by(project_id=project_id).all()
        return [
            {
                "title": r.title,
                "severity": r.severity,
                "description": r.description,
                "data_points": json.loads(r.data_json) if r.data_json else [],
            }
            for r in rows
        ]


@mcp.tool
def search_documents(project_id: int, query: str) -> list[dict]:
    """项目内全文搜索（带页码与摘录，支持金融同义词）。"""
    from .db import SessionLocal
    from .db.models import File
    from .search.fts import search as fts_search

    with SessionLocal() as session:
        file_ids = [f.id for f in session.query(File).filter_by(project_id=project_id).all()]
    if not file_ids:
        return []
    return fts_search(file_ids, query, limit=10)


@mcp.tool
def ask_question(project_id: int, question: str) -> dict:
    """基于项目上传资料的 AI 问答（回答带出处页码，防编造；需先在软件内配置 AI Key）。"""
    from .ai.qa import answer_question

    return answer_question(project_id, question)


@mcp.tool
def get_risk_score(project_id: int) -> dict:
    """项目尽调风险评分卡（五维打分 + 依据）。"""
    from .risk_score import compute_risk_score

    return compute_risk_score(project_id)


@mcp.tool
def analyze_document(path: str, project_name: str = "") -> dict:
    """无头分析一份金融文档（PDF/Excel）：创建项目、解析、返回指标与异常。

    path 必须是本机文件路径。返回项目 id 与提取到的指标数。
    """
    from .db import SessionLocal
    from .db.models import Project
    from .pipeline.parse_service import create_file_record, parse_file
    from .api import analyze_project

    path_obj = Path(path)
    if not path_obj.exists():
        return {"ok": False, "error": f"文件不存在：{path}"}
    suffix = path_obj.suffix.lower().lstrip(".")
    if suffix not in ("pdf", "xlsx", "xls"):
        return {"ok": False, "error": "仅支持 PDF / Excel"}
    with SessionLocal() as session:
        p = Project(name=project_name or f"{path_obj.stem} 分析")
        session.add(p)
        session.commit()
        session.refresh(p)
        project_id = p.id
        f = create_file_record(
            project_id,
            path_obj.name,
            path_obj.read_bytes(),
            "excel" if suffix in ("xlsx", "xls") else "pdf",
        )
    parse_file(f.id)  # 同步解析（完成后自动跑异常检测与笔记）
    with SessionLocal() as session:
        session.expire_all()
        from .db.models import FinancialLine, Anomaly

        line_count = session.query(FinancialLine).filter_by(file_id=f.id).count()
        anomaly_count = session.query(Anomaly).filter_by(project_id=project_id).count()
    return {
        "ok": True,
        "project_id": project_id,
        "file_id": f.id,
        "financial_lines": line_count,
        "anomalies": anomaly_count,
        "hint": "用 get_indicators / get_anomalies 查看详情；资料仅存本机。",
    }


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
