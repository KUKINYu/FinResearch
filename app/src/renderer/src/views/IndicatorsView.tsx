import { useCallback, useEffect, useMemo, useState } from 'react'
import type { FileInfo, IndicatorInfo } from '../types'
import PdfViewer from './PdfViewer'

// 核心指标的展示顺序（与产品需求一致），其余指标按字母序排在后面
const CORE_ORDER = [
  '营业收入',
  '净利润',
  '归属于母公司股东的净利润',
  '毛利率',
  '净利率',
  '加权平均净资产收益率',
  '经营活动产生的现金流量净额',
  '应收账款',
  '存货',
  '有息负债',
  '研发费用'
]

function sortPeriods(periods: string[]): string[] {
  return [...periods].sort((a, b) => {
    const ya = Number(a.match(/(\d{4})/)?.[1] ?? 0)
    const yb = Number(b.match(/(\d{4})/)?.[1] ?? 0)
    if (ya !== yb) return yb - ya
    const aInterim = a.includes('1-6月') ? 1 : 0
    const bInterim = b.includes('1-6月') ? 1 : 0
    return aInterim - bInterim // 同年：整年在前
  })
}

function formatValue(v: number): string {
  return v.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

interface ViewerState {
  fileId: number
  fileName: string
  page: number
  bbox: string | null
  bytes: ArrayBuffer
}

export default function IndicatorsView({
  projectId
}: {
  projectId: number | null
}): React.JSX.Element {
  const [indicators, setIndicators] = useState<IndicatorInfo[]>([])
  const [files, setFiles] = useState<Map<number, string>>(new Map())
  const [editing, setEditing] = useState<{ id: number; draft: string } | null>(null)
  const [viewer, setViewer] = useState<ViewerState | null>(null)
  const [loadingViewer, setLoadingViewer] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async (): Promise<void> => {
    if (projectId === null) return
    try {
      setIndicators(await window.finengine.getIndicators(projectId))
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

  const rows = useMemo(() => {
    const byName = new Map<string, IndicatorInfo[]>()
    for (const ind of indicators) {
      const list = byName.get(ind.name) ?? []
      list.push(ind)
      byName.set(ind.name, list)
    }
    const ordered = [
      ...CORE_ORDER.filter((n) => byName.has(n)),
      ...[...byName.keys()].filter((n) => !CORE_ORDER.includes(n)).sort()
    ]
    return { byName, ordered }
  }, [indicators])

  const periods = useMemo(
    () => sortPeriods([...new Set(indicators.map((i) => i.period))]),
    [indicators]
  )

  const saveEdit = async (id: number): Promise<void> => {
    if (!editing) return
    const value = Number(editing.draft.replace(/,/g, ''))
    if (Number.isFinite(value)) {
      try {
        await window.finengine.updateIndicator(id, { value })
      } catch (e) {
        setError(String(e))
      }
    }
    setEditing(null)
    await load()
  }

  const removeCell = async (id: number, name: string, period: string): Promise<void> => {
    if (!confirm(`删除「${name} ${period}」这条数据？\n（可能来自子公司等其他口径，删除前建议先点出处核对原文）`)) return
    try {
      await window.finengine.deleteIndicator(id)
    } catch (e) {
      setError(String(e))
    }
    await load()
  }

  const openSource = async (ind: IndicatorInfo): Promise<void> => {
    if (ind.source_file_id === null) return
    try {
      setLoadingViewer(true)
      const bytes = await window.finengine.getFileContent(ind.source_file_id)
      let bbox: string | null = null
      try {
        const lines = (await window.finengine.getFileLines(ind.source_file_id)) as {
          indicator: string
          period: string
          bbox: string | null
        }[]
        const hit = lines.find((l) => l.indicator === ind.name && l.period === ind.period)
        bbox = hit?.bbox ?? null
      } catch {
        // 行明细获取失败不阻塞阅读器
      }
      setViewer({
        fileId: ind.source_file_id,
        fileName: files.get(ind.source_file_id) ?? '原始文件',
        page: ind.source_page ?? 1,
        bbox,
        bytes
      })
    } catch (e) {
      setError(String(e))
    } finally {
      setLoadingViewer(false)
    }
  }

  if (projectId === null) {
    return (
      <div>
        <h2>财务指标</h2>
        <p className="placeholder">请先在「项目档案」中选择一个项目。</p>
      </div>
    )
  }

  return (
    <div className="indicators-view">
      <div className="indicators-header">
        <h2>财务指标</h2>
        <p className="placeholder">
          提取结果自动生成，建议逐项核对：每条数据可点「出处」跳回原文验证；双击数值可修正；悬停单元格可删除错误数据（如混入的子公司数据）。
        </p>
      </div>
      {error && <div className="error-banner">{error}</div>}
      {indicators.length === 0 ? (
        <p className="placeholder">还没有财务数据。请在「项目档案」中上传招股书或年报，解析完成后这里会出现指标表。</p>
      ) : (
        <div className="indicator-table-wrap">
          <table className="indicator-table">
            <thead>
              <tr>
                <th className="col-indicator">指标</th>
                {periods.map((p) => (
                  <th key={p}>{p}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.ordered.map((name) => (
                <tr key={name}>
                  <td className="col-indicator">
                    {name}
                    {(rows.byName.get(name) ?? []).some((i) => i.derived) && (
                      <span className="derived-mark" title="由其他数据计算得出">※</span>
                    )}
                  </td>
                  {periods.map((period) => {
                    const ind = (rows.byName.get(name) ?? []).find((i) => i.period === period)
                    if (!ind) return <td key={period} className="cell-empty">—</td>
                    return (
                      <td key={period} className="cell-value">
                        {editing?.id === ind.id ? (
                          <input
                            className="cell-input"
                            autoFocus
                            value={editing.draft}
                            onChange={(e) => setEditing({ id: ind.id, draft: e.target.value })}
                            onBlur={() => saveEdit(ind.id)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') saveEdit(ind.id)
                              if (e.key === 'Escape') setEditing(null)
                            }}
                          />
                        ) : (
                          <>
                            <span
                              className="cell-number"
                              onDoubleClick={() =>
                                setEditing({ id: ind.id, draft: String(ind.value) })
                              }
                              title={ind.derived ? `计算方式：${ind.derived}` : '双击修改'}
                            >
                              {formatValue(ind.value)}
                              <span className="cell-unit">{ind.unit}</span>
                            </span>
                            <button
                              className="cell-delete"
                              title="删除此数据"
                              onClick={() => removeCell(ind.id, ind.name, ind.period)}
                            >
                              ×
                            </button>
                            {ind.source_page !== null && (
                              <button
                                className="source-link"
                                onClick={() => openSource(ind)}
                                disabled={loadingViewer}
                                title="跳转到原文出处"
                              >
                                出处：第{ind.source_page}页
                              </button>
                            )}
                          </>
                        )}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {viewer && (
        <div className="viewer-overlay" onClick={() => setViewer(null)}>
          <div className="viewer-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="viewer-close-row">
              <span className="viewer-title">原文核对</span>
              <button className="btn btn-sm" onClick={() => setViewer(null)}>
                关闭
              </button>
            </div>
            <PdfViewer
              bytes={viewer.bytes}
              fileName={viewer.fileName}
              targetPage={viewer.page}
              bbox={viewer.bbox}
            />
          </div>
        </div>
      )}
    </div>
  )
}
