import { useCallback, useEffect, useState } from 'react'

interface ComparableResult {
  ok: boolean
  error?: string
  basis?: string
  peer_rows?: { peer: string; pe: number | null; implied_value_wan: number | null }[]
  avg_pe?: number
  implied_range_wan?: number[]
  implied_avg_wan?: number
}

interface DCFResult {
  ok: boolean
  error?: string
  custom?: {
    equity_value_wan: number
    per_share: number | null
    assumptions: Record<string, number>
  }
  scenarios?: Record<
    string,
    { assumptions: Record<string, number>; equity_value_wan: number; per_share: number | null }
  >
}

interface RunRecord {
  id: number
  method: string
  inputs: Record<string, number>
  inputs_hash: string
  created_at: string
}

const WAN = (v: number | null | undefined): string =>
  v === null || v === undefined ? '—' : `${v.toLocaleString('zh-CN', { maximumFractionDigits: 0 })} 万元`

export default function ValuationPanel({
  projectId
}: {
  projectId: number | null
}): React.JSX.Element | null {
  const [comp, setComp] = useState<ComparableResult | null>(null)
  const [dcf, setDcf] = useState<DCFResult | null>(null)
  const [runs, setRuns] = useState<RunRecord[]>([])
  const [loadingComp, setLoadingComp] = useState(false)
  const [loadingDcf, setLoadingDcf] = useState(false)
  const [error, setError] = useState('')
  // DCF 输入（默认：中性假设示例）
  const [form, setForm] = useState({
    base_fcf: '50000',
    growth: '0.12',
    wacc: '0.10',
    terminal_growth: '0.02',
    shares: '10000'
  })

  const loadRuns = useCallback(async (): Promise<void> => {
    if (projectId === null) return
    try {
      const resp = (await window.finengine.getValuationRuns(projectId)) as { runs: RunRecord[] }
      setRuns(resp.runs ?? [])
    } catch {
      /* 忽略 */
    }
  }, [projectId])

  useEffect(() => {
    loadRuns()
  }, [loadRuns])

  const runComparable = async (): Promise<void> => {
    if (projectId === null) return
    setLoadingComp(true)
    setError('')
    try {
      setComp((await window.finengine.valuationComparable(projectId)) as ComparableResult)
      await loadRuns()
    } catch (e) {
      setError(String(e))
    } finally {
      setLoadingComp(false)
    }
  }

  const runDcf = async (): Promise<void> => {
    if (projectId === null) return
    setLoadingDcf(true)
    setError('')
    try {
      setDcf(
        (await window.finengine.valuationDcf(projectId, {
          base_fcf: Number(form.base_fcf),
          growth: Number(form.growth),
          wacc: Number(form.wacc),
          terminal_growth: Number(form.terminal_growth),
          shares: Number(form.shares)
        })) as DCFResult
      )
      await loadRuns()
    } catch (e) {
      setError(String(e))
    } finally {
      setLoadingDcf(false)
    }
  }

  if (projectId === null) return null

  const input = (key: keyof typeof form, label: string): React.JSX.Element => (
    <label className="val-field">
      {label}
      <input value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
    </label>
  )

  return (
    <div className="valuation-panel">
      <div className="pane-header">
        <h4>估值测算</h4>
      </div>
      {error && <div className="error-banner">{error}</div>}

      <div className="val-methods">
        <div className="val-method-card">
          <h5>可比公司法（PE）</h5>
          <p className="placeholder">
            标的归母净利润 × 可比公司 PE。可比公司在「同行对比」中添加（需已拉取行情数据）。
          </p>
          <button className="btn btn-primary btn-sm" onClick={runComparable} disabled={loadingComp}>
            {loadingComp ? '测算中…' : '开始测算'}
          </button>
          {comp?.ok && (
            <div className="val-result">
              <p>{comp.basis}</p>
              <p>
                可比 PE 均值 <b>{comp.avg_pe}</b>，隐含市值区间{' '}
                <b>
                  {WAN(comp.implied_range_wan?.[0])} ~ {WAN(comp.implied_range_wan?.[1])}
                </b>
                ，均值 <b>{WAN(comp.implied_avg_wan)}</b>
              </p>
              <ul className="val-peer-list">
                {(comp.peer_rows ?? []).map((r, i) => (
                  <li key={i}>
                    {r.peer}：PE {r.pe ?? '—'} → 隐含 {WAN(r.implied_value_wan)}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {comp && !comp.ok && <div className="error-banner">{comp.error}</div>}
        </div>

        <div className="val-method-card">
          <h5>DCF 两阶段模型</h5>
          <div className="val-form">
            {input('base_fcf', '基期自由现金流（万元）')}
            {input('growth', '显性期增速（如 0.12）')}
            {input('wacc', '折现率 WACC（如 0.10）')}
            {input('terminal_growth', '永续增速（如 0.02）')}
            {input('shares', '总股本（万股）')}
          </div>
          <button className="btn btn-primary btn-sm" onClick={runDcf} disabled={loadingDcf}>
            {loadingDcf ? '测算中…' : '测算（含保守/中性/乐观三情景）'}
          </button>
          {dcf?.ok && (
            <div className="val-result">
              <p>
                你的假设：企业价值 <b>{WAN(dcf.custom?.equity_value_wan)}</b>
                {dcf.custom?.per_share !== null && dcf.custom?.per_share !== undefined && (
                  <>，每股 <b>{dcf.custom?.per_share} 元</b></>
                )}
              </p>
              <table className="val-scenarios">
                <thead>
                  <tr>
                    <th>情景</th>
                    <th>企业价值</th>
                    <th>每股</th>
                  </tr>
                </thead>
                <tbody>
                  {(Object.entries(dcf.scenarios ?? {}) as [string, { equity_value_wan: number; per_share: number | null }][]).map(
                    ([name, s]) => (
                      <tr key={name}>
                        <td>{name}</td>
                        <td>{WAN(s.equity_value_wan)}</td>
                        <td>{s.per_share ?? '—'} 元</td>
                      </tr>
                    )
                  )}
                </tbody>
              </table>
            </div>
          )}
          {dcf && !dcf.ok && <div className="error-banner">{dcf.error}</div>}
        </div>
      </div>

      {runs.length > 0 && (
        <div className="val-history">
          <h5>测算历史（输入已版本化，可追溯）</h5>
          <ul>
            {runs.slice(0, 6).map((r) => (
              <li key={r.id}>
                <span className="val-run-method">{r.method === 'dcf' ? 'DCF' : '可比公司'}</span>
                <span className="val-run-hash">指纹 {r.inputs_hash}</span>
                <span className="val-run-time">{r.created_at}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
