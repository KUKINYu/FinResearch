import { useCallback, useEffect, useState } from 'react'
import type { FileInfo, IndicatorInfo, ProjectInfo } from '../types'
import NotesPanel from './NotesPanel'

const STATUS_TEXT: Record<string, string> = {
  uploaded: '已上传',
  parsing: '解析中',
  ready: '已就绪',
  failed: '失败'
}

function formatSize(bytes: number): string {
  if (bytes > 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024).toFixed(0)} KB`
}

export default function ProjectsView({
  selectedId,
  onSelect
}: {
  selectedId: number | null
  onSelect: (id: number | null) => void
}): React.JSX.Element {
  const [projects, setProjects] = useState<ProjectInfo[]>([])
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState('')
  const [newCompany, setNewCompany] = useState('')
  const [detail, setDetail] = useState<ProjectInfo | null>(null)
  const [indicators, setIndicators] = useState<IndicatorInfo[]>([])
  const [error, setError] = useState('')

  const loadProjects = useCallback(async () => {
    try {
      setProjects(await window.finengine.listProjects())
    } catch (e) {
      setError(String(e))
    }
  }, [])

  useEffect(() => {
    loadProjects()
  }, [loadProjects])

  const loadDetail = useCallback(async (id: number) => {
    try {
      const d = await window.finengine.getProject(id)
      setDetail(d)
      setIndicators(await window.finengine.getIndicators(id))
    } catch (e) {
      setError(String(e))
    }
  }, [])

  useEffect(() => {
    if (selectedId !== null) loadDetail(selectedId)
  }, [selectedId, loadDetail])

  // 有文件在解析时每 2 秒刷新状态（进度条）
  useEffect(() => {
    const hasParsing = detail?.files?.some(
      (f) => f.status === 'parsing' || f.status === 'uploaded'
    )
    if (!hasParsing || selectedId === null) return
    const timer = setInterval(() => loadDetail(selectedId), 2000)
    return () => clearInterval(timer)
  }, [detail, selectedId, loadDetail])

  const createProject = async (): Promise<void> => {
    if (!newName.trim()) return
    try {
      const p = await window.finengine.createProject({
        name: newName.trim(),
        company_name: newCompany.trim() || undefined
      })
      setCreating(false)
      setNewName('')
      setNewCompany('')
      await loadProjects()
      onSelect(p.id)
    } catch (e) {
      setError(String(e))
    }
  }

  const upload = async (): Promise<void> => {
    if (selectedId === null) return
    try {
      await window.finengine.uploadFiles(selectedId)
      await loadDetail(selectedId)
    } catch (e) {
      setError(String(e))
    }
  }

  const removeProject = async (id: number): Promise<void> => {
    if (!confirm('确认删除该项目及其全部资料？此操作不可恢复。')) return
    try {
      await window.finengine.deleteProject(id)
      if (selectedId === id) {
        onSelect(null)
        setDetail(null)
      }
      await loadProjects()
    } catch (e) {
      setError(String(e))
    }
  }

  return (
    <div className="projects-view">
      <div className="project-pane">
        <div className="pane-header">
          <h3>研究项目</h3>
          <button className="btn btn-primary btn-sm" onClick={() => setCreating(!creating)}>
            {creating ? '取消' : '＋ 新建项目'}
          </button>
        </div>
        {creating && (
          <div className="create-form">
            <input
              placeholder="项目名称（如：XX公司 IPO 尽调）"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              autoFocus
            />
            <input
              placeholder="标的公司名称（可选）"
              value={newCompany}
              onChange={(e) => setNewCompany(e.target.value)}
            />
            <button className="btn btn-primary btn-sm" onClick={createProject}>
              创建
            </button>
          </div>
        )}
        <ul className="project-list">
          {projects.map((p) => (
            <li
              key={p.id}
              className={p.id === selectedId ? 'project-item active' : 'project-item'}
              onClick={() => onSelect(p.id)}
            >
              <div className="project-name">{p.name}</div>
              <div className="project-company">
                {p.company_name || '未填写公司'} {p.company_code && `(${p.company_code})`}
              </div>
            </li>
          ))}
          {projects.length === 0 && <li className="project-empty">还没有项目，点右上角新建</li>}
        </ul>
      </div>

      <div className="project-detail">
        {error && <div className="error-banner">{error}</div>}
        {!detail && (
          <p className="placeholder">选择左侧项目，或新建一个项目开始你的尽调工作。</p>
        )}
        {detail && (
          <>
            <div className="detail-header">
              <h3>{detail.name}</h3>
              <button className="btn btn-sm" onClick={() => removeProject(detail.id)}>
                删除项目
              </button>
            </div>
            {detail.company_name && (
              <p className="detail-company">
                标的公司：{detail.company_name} {detail.company_code && `（${detail.company_code}）`}
              </p>
            )}

            <div className="files-section">
              <div className="pane-header">
                <h4>资料文件（{detail.files?.length ?? 0}）</h4>
                <button className="btn btn-primary btn-sm" onClick={upload}>
                  ⬆ 上传 PDF / Excel
                </button>
              </div>
              <ul className="file-list">
                {(detail.files ?? []).map((f: FileInfo) => (
                  <li key={f.id} className="file-item">
                    <span className="file-type-badge">{f.file_type.toUpperCase()}</span>
                    <div className="file-info">
                      <div className="file-name">{f.original_name}</div>
                      <div className="file-meta">
                        {formatSize(f.size_bytes)}
                        {f.page_count > 0 && ` · ${f.page_count} 页`}
                      </div>
                      {(f.status === 'parsing' || f.status === 'uploaded') && (
                        <div className="progress-bar">
                          <div className="progress-fill" style={{ width: `${f.parse_progress}%` }} />
                        </div>
                      )}
                      {f.status === 'failed' && <div className="file-error">{f.error}</div>}
                    </div>
                    <span className={`status-badge status-${f.status}`}>
                      {STATUS_TEXT[f.status] ?? f.status}
                    </span>
                  </li>
                ))}
                {(detail.files ?? []).length === 0 && (
                  <li className="file-empty">
                    还没有文件。上传招股说明书、年报、研报等 PDF 或 Excel 资料，
                    上传后会自动解析并提取财务数据。
                  </li>
                )}
              </ul>
            </div>

            {indicators.length > 0 && (
              <div className="indicator-preview">
                <h4>已提取财务数据（{indicators.length} 条）</h4>
                <p className="placeholder">
                  完整指标看板与趋势图见「财务指标」工作区。
                </p>
              </div>
            )}

            <div className="notes-section">
              <NotesPanel projectId={detail.id} />
            </div>
          </>
        )}
      </div>
    </div>
  )
}
