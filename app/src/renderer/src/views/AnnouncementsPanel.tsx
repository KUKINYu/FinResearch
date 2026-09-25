import { useCallback, useEffect, useState } from 'react'

interface AnnouncementItem {
  id: number
  title: string
  date: string | null
  url: string | null
  source: string
  negative: boolean
}

interface AnnouncementData {
  near: AnnouncementItem[]
  month: AnnouncementItem[]
  older: AnnouncementItem[]
  total: number
}

const LAYERS: { key: 'near' | 'month' | 'older'; label: string; hint: string }[] = [
  { key: 'near', label: '近 3 天', hint: '权重最高' },
  { key: 'month', label: '近 30 天', hint: '' },
  { key: 'older', label: '更早', hint: '' }
]

export default function AnnouncementsPanel({
  projectId,
  hasCompanyCode
}: {
  projectId: number | null
  hasCompanyCode: boolean
}): React.JSX.Element | null {
  const [data, setData] = useState<AnnouncementData | null>(null)
  const [loading, setLoading] = useState(false)
  const [summarizing, setSummarizing] = useState(false)
  const [summary, setSummary] = useState('')
  const [error, setError] = useState('')

  const load = useCallback(async (): Promise<void> => {
    if (projectId === null) return
    try {
      setData((await window.finengine.getAnnouncements(projectId)) as AnnouncementData)
    } catch (e) {
      setError(String(e))
    }
  }, [projectId])

  useEffect(() => {
    load()
  }, [load])

  const fetch = async (): Promise<void> => {
    if (projectId === null) return
    setLoading(true)
    setError('')
    try {
      const resp = (await window.finengine.fetchAnnouncements(projectId)) as {
        ok: boolean
        error?: string
      }
      if (!resp.ok) setError(resp.error ?? '拉取失败')
      await load()
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  const summarize = async (): Promise<void> => {
    if (projectId === null) return
    setSummarizing(true)
    setError('')
    try {
      const resp = (await window.finengine.summarizeAnnouncements(projectId)) as {
        ok: boolean
        answer?: string
        error?: string
      }
      if (resp.ok) {
        setSummary(resp.answer ?? '')
      } else {
        setError(resp.error ?? '摘要失败')
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setSummarizing(false)
    }
  }

  if (projectId === null) return null

  return (
    <div className="announce-panel">
      <div className="pane-header">
        <h4>公告与舆情监控</h4>
        <div className="announce-actions">
          {!hasCompanyCode && (
            <span className="placeholder">需先在项目档案填写标的公司证券代码</span>
          )}
          <button
            className="btn btn-sm"
            onClick={summarize}
            disabled={summarizing || (data?.total ?? 0) === 0}
          >
            {summarizing ? '摘要生成中…' : '✨ AI 摘要（最近发生了什么）'}
          </button>
          <button
            className="btn btn-primary btn-sm"
            onClick={fetch}
            disabled={loading || !hasCompanyCode}
          >
            {loading ? '拉取中（可能较慢）…' : '↻ 拉取公告'}
          </button>
        </div>
      </div>
      {error && <div className="error-banner">{error}</div>}
      {summary && (
        <div className="announce-summary">
          <b>AI 摘要：</b>
          <span style={{ whiteSpace: 'pre-wrap' }}>{summary}</span>
        </div>
      )}
      {data && data.total === 0 && (
        <p className="placeholder">
          还没有公告数据。点击「拉取公告」获取该公司近期公告与新闻（负面事项自动标记）。
        </p>
      )}
      {data && data.total > 0 && (
        <div className="announce-layers">
          {LAYERS.map((layer) =>
            data[layer.key].length === 0 ? null : (
              <div key={layer.key} className="announce-layer">
                <div className="announce-layer-title">
                  {layer.label}
                  {layer.hint && <em>{layer.hint}</em>}
                  <span className="announce-count">{data[layer.key].length} 条</span>
                </div>
                <ul>
                  {data[layer.key].slice(0, 12).map((a) => (
                    <li key={a.id} className={a.negative ? 'announce-item negative' : 'announce-item'}>
                      {a.negative && <span className="neg-badge">⚠ 负面</span>}
                      <span className="announce-source">{a.source}</span>
                      <span className="announce-title">{a.title}</span>
                      <span className="announce-date">{a.date}</span>
                      {a.url && (
                        <a href={a.url} target="_blank" rel="noreferrer" className="announce-link">
                          原文
                        </a>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )
          )}
        </div>
      )}
    </div>
  )
}
