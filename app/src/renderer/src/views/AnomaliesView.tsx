import { useCallback, useEffect, useState } from 'react'
import type { FileInfo } from '../types'
import PdfSourceModal from './PdfSourceModal'

interface AnomalyPoint {
  indicator: string
  period: string
  value: number
  unit: string
  source_file_id: number | null
  source_page: number | null
}

interface AnomalyInfo {
  id: number
  rule_id: string
  title: string
  description: string
  severity: string
  data_points: AnomalyPoint[]
}

interface RuleInfo {
  rule_id: string
  title: string
  severity: string
  enabled: boolean
  params: { name: string; label: string; default: number; value: number }[]
}

const SEVERITY_TEXT: Record<string, string> = { high: '高', medium: '中', low: '低' }

export default function AnomaliesView({
  projectId
}: {
  projectId: number | null
}): React.JSX.Element {
  const [anomalies, setAnomalies] = useState<AnomalyInfo[]>([])
  const [files, setFiles] = useState<Map<number, string>>(new Map())
  const [analyzing, setAnalyzing] = useState(false)
  const [rulesOpen, setRulesOpen] = useState(false)
  const [rules, setRules] = useState<RuleInfo[]>([])
  const [viewer, setViewer] = useState<{
    fileId: number
    fileName: string
    page: number
    bbox: string | null
  } | null>(null)
  const [error, setError] = useState('')

  const load = useCallback(async (): Promise<void> => {
    if (projectId === null) return
    try {
      setAnomalies(await window.finengine.getAnomalies(projectId))
      const detail = await window.finengine.getProject(projectId)
      const map = new Map<number, string>()
      for (const f of (detail.files ?? []) as FileInfo[]) map.set(f.id, f.original_name)
      setFiles(map)
    } catch (e) {
      setError(String(e))
    }
  }, [projectId])

  useEffect(() => {
    load()
  }, [load])

  const reanalyze = async (): Promise<void> => {
    if (projectId === null) return
    setAnalyzing(true)
    try {
      await window.finengine.analyzeProject(projectId)
      await load()
    } catch (e) {
      setError(String(e))
    } finally {
      setAnalyzing(false)
    }
  }

  const openRules = async (): Promise<void> => {
    try {
      const resp = (await window.finengine.getRules()) as { rules: RuleInfo[] }
      setRules(resp.rules ?? [])
      setRulesOpen(true)
    } catch (e) {
      setError(String(e))
    }
  }

  const saveRules = async (): Promise<void> => {
    const settings: Record<string, unknown> = {}
    for (const r of rules) {
      const params: Record<string, number> = {}
      for (const p of r.params) params[p.name] = p.value
      settings[r.rule_id] = { enabled: r.enabled, params }
    }
    try {
      await window.finengine.saveRules(settings)
      setRulesOpen(false)
      await reanalyze()
    } catch (e) {
      setError(String(e))
    }
  }

  const openSource = async (p: AnomalyPoint): Promise<void> => {
    if (p.source_file_id === null) return
    try {
      let bbox: string | null = null
      try {
        const lines = (await window.finengine.getFileLines(p.source_file_id)) as {
          indicator: string
          period: string
          bbox: string | null
        }[]
        const hit = lines.find((l) => l.indicator === p.indicator && l.period === p.period)
        bbox = hit?.bbox ?? null
      } catch {
        // 行明细失败不阻塞
      }
      setViewer({
        fileId: p.source_file_id,
        fileName: files.get(p.source_file_id) ?? '原始文件',
        page: p.source_page ?? 1,
        bbox
      })
    } catch (e) {
      setError(String(e))
    }
  }

  if (projectId === null) {
    return (
      <div>
        <h2>异常发现</h2>
        <p className="placeholder">请先在「项目档案」中选择一个项目。</p>
      </div>
    )
  }

  return (
    <div className="anomalies-view">
      <div className="anomalies-header">
        <h2>异常发现</h2>
        <div className="anomalies-actions">
          <button
            className="btn btn-sm"
            onClick={async () => {
              try {
                await window.finengine.exportFile(projectId, 'anomalies')
              } catch (e) {
                setError(String(e))
              }
            }}
            disabled={anomalies.length === 0}
          >
            ⬇ 导出异常清单（Word）
          </button>
          <button className="btn btn-sm" onClick={openRules}>
            ⚙ 规则设置
          </button>
          <button className="btn btn-primary btn-sm" onClick={reanalyze} disabled={analyzing}>
            {analyzing ? '分析中…' : '↻ 重新分析'}
          </button>
        </div>
      </div>
      <p className="placeholder">
        基于项目财务数据自动检测的异常。每条异常给出计算过程与数据出处，点击数据可跳回原文核对。
        可在「规则设置」中调整阈值或关闭不关心的规则。
      </p>
      {error && <div className="error-banner">{error}</div>}

      {rulesOpen && (
        <div className="rules-panel">
          <div className="pane-header">
            <h4>异常规则设置</h4>
            <button className="btn btn-primary btn-sm" onClick={saveRules}>
              保存并重新分析
            </button>
          </div>
          <ul className="rules-list">
            {rules.map((r) => (
              <li key={r.rule_id} className="rule-row">
                <label className="rule-toggle">
                  <input
                    type="checkbox"
                    checked={r.enabled}
                    onChange={(e) =>
                      setRules((prev) =>
                        prev.map((x) =>
                          x.rule_id === r.rule_id ? { ...x, enabled: e.target.checked } : x
                        )
                      )
                    }
                  />
                  <span className={`severity-badge severity-${r.severity}`}>
                    {SEVERITY_TEXT[r.severity] ?? r.severity}
                  </span>
                  <span className="rule-title">{r.title}</span>
                </label>
                <div className="rule-params">
                  {r.params.map((p) => (
                    <label key={p.name} className="rule-param">
                      {p.label}
                      <input
                        type="number"
                        step="any"
                        value={p.value}
                        disabled={!r.enabled}
                        onChange={(e) =>
                          setRules((prev) =>
                            prev.map((x) =>
                              x.rule_id === r.rule_id
                                ? {
                                    ...x,
                                    params: x.params.map((pp) =>
                                      pp.name === p.name
                                        ? { ...pp, value: Number(e.target.value) }
                                        : pp
                                    )
                                  }
                                : x
                            )
                          )
                        }
                      />
                    </label>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {anomalies.length === 0 ? (
        <p className="placeholder">
          未发现触发阈值的异常。可上传更多资料后重新分析。
        </p>
      ) : (
        <ul className="anomaly-list">
          {anomalies.map((a) => (
            <li key={a.id} className={`anomaly-card severity-${a.severity}`}>
              <div className="anomaly-title-row">
                <span className={`severity-badge severity-${a.severity}`}>
                  {SEVERITY_TEXT[a.severity] ?? a.severity}
                </span>
                <span className="anomaly-title">{a.title}</span>
              </div>
              <p className="anomaly-desc">{a.description}</p>
              <div className="anomaly-points">
                {a.data_points.map((p, i) => (
                  <button
                    key={i}
                    className="data-point-chip"
                    onClick={() => openSource(p)}
                    title="点击查看原文出处"
                  >
                    {p.indicator} {p.period}：{p.value.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}
                    {p.unit}
                    {p.source_page !== null && ` · 第${p.source_page}页`}
                  </button>
                ))}
              </div>
            </li>
          ))}
        </ul>
      )}

      {viewer && (
        <PdfSourceModal
          fileId={viewer.fileId}
          fileName={viewer.fileName}
          page={viewer.page}
          bbox={viewer.bbox}
          onClose={() => setViewer(null)}
        />
      )}
    </div>
  )
}
