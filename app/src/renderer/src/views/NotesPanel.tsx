import { useCallback, useEffect, useState } from 'react'

interface Note {
  id: number
  kind: string
  content: string
  created_at: string
}

const KIND_LABEL: Record<string, string> = {
  manual: '手记',
  data_update: '数据更新',
  reflection: 'AI 反思'
}

export default function NotesPanel({
  projectId
}: {
  projectId: number | null
}): React.JSX.Element | null {
  const [notes, setNotes] = useState<Note[]>([])
  const [draft, setDraft] = useState('')
  const [reflecting, setReflecting] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async (): Promise<void> => {
    if (projectId === null) return
    try {
      const resp = (await window.finengine.getNotes(projectId)) as { notes: Note[] }
      setNotes(resp.notes ?? [])
    } catch (e) {
      setError(String(e))
    }
  }, [projectId])

  useEffect(() => {
    load()
  }, [load])

  const add = async (): Promise<void> => {
    if (projectId === null || !draft.trim()) return
    try {
      await window.finengine.addNote(projectId, draft.trim())
      setDraft('')
      await load()
    } catch (e) {
      setError(String(e))
    }
  }

  const reflect = async (): Promise<void> => {
    if (projectId === null) return
    setReflecting(true)
    setError('')
    try {
      const resp = (await window.finengine.reflectNotes(projectId)) as { ok: boolean; error?: string }
      if (!resp.ok) setError(resp.error ?? '反思生成失败（需先在 AI 设置中配置 Key）')
      await load()
    } catch (e) {
      setError(String(e))
    } finally {
      setReflecting(false)
    }
  }

  if (projectId === null) return null

  return (
    <div className="notes-panel">
      <div className="pane-header">
        <h4>研究笔记</h4>
        <button className="btn btn-sm" onClick={reflect} disabled={reflecting}>
          {reflecting ? '生成中…' : '✨ AI 反思（对比历史结论与最新数据）'}
        </button>
      </div>
      {error && <div className="error-banner">{error}</div>}
      <div className="note-input-row">
        <input
          placeholder="写一条研究手记，如：重点关注大客户集中度风险…"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && add()}
        />
        <button className="btn btn-primary btn-sm" onClick={add} disabled={!draft.trim()}>
          添加
        </button>
      </div>
      <ul className="notes-list">
        {notes.map((n) => (
          <li key={n.id} className={`note-item note-${n.kind}`}>
            <div className="note-head">
              <span className="note-kind">{KIND_LABEL[n.kind] ?? n.kind}</span>
              <span className="note-time">{n.created_at}</span>
            </div>
            <p className="note-content">{n.content}</p>
          </li>
        ))}
        {notes.length === 0 && (
          <li className="placeholder">
            还没有笔记。上传新资料后会自动生成"数据更新"笔记；也可以手写研究结论。
          </li>
        )}
      </ul>
    </div>
  )
}
