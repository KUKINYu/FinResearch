import { useCallback, useEffect, useRef, useState } from 'react'
import * as echarts from 'echarts'
import ValuationPanel from './ValuationPanel'

interface StockHit {
  code: string
  name: string
}

interface Comparable {
  id: number
  code: string
  name: string
}

interface CompanyData {
  code: string
  name: string
  year: string | null
  financials: Record<string, number>
  valuation: { pe: number | null; pb: number | null; market_cap: number | null }
}

const INDICATORS: { key: string; label: string; format: (v: number | null) => string }[] = [
  { key: '营业收入', label: '营业收入（万元）', format: (v) => v === null ? '—' : v.toLocaleString('zh-CN', { maximumFractionDigits: 0 }) },
  { key: '归母净利润', label: '归母净利润（万元）', format: (v) => v === null ? '—' : v.toLocaleString('zh-CN', { maximumFractionDigits: 0 }) },
  { key: '毛利率', label: '毛利率（%）', format: (v) => v === null ? '—' : v.toFixed(2) },
  { key: '净利率', label: '净利率（%）', format: (v) => v === null ? '—' : v.toFixed(2) },
  { key: 'ROE', label: 'ROE（%）', format: (v) => v === null ? '—' : v.toFixed(2) },
  { key: '研发投入', label: '研发投入（万元）', format: (v) => v === null ? '—' : v.toLocaleString('zh-CN', { maximumFractionDigits: 0 }) },
  { key: 'pe', label: 'PE（动态）', format: (v) => v === null ? '—' : v.toFixed(1) },
  { key: 'pb', label: 'PB', format: (v) => v === null ? '—' : v.toFixed(2) },
  { key: 'market_cap', label: '总市值（亿元）', format: (v) => v === null ? '—' : (v / 1e8).toFixed(1) }
]

function getValue(c: CompanyData, key: string): number | null {
  if (key in c.valuation) {
    const v = c.valuation[key as keyof CompanyData['valuation']]
    return typeof v === 'number' ? v : null
  }
  const v = c.financials[key]
  return typeof v === 'number' ? v : null
}

export default function ComparisonView({
  projectId
}: {
  projectId: number | null
}): React.JSX.Element {
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState<StockHit[]>([])
  const [comparables, setComparables] = useState<Comparable[]>([])
  const [companies, setCompanies] = useState<CompanyData[]>([])
  const [chartKey, setChartKey] = useState('营业收入')
  const [loading, setLoading] = useState(false)
  const [fetchedAt, setFetchedAt] = useState('')
  const [error, setError] = useState('')
  const chartRef = useRef<HTMLDivElement>(null)
  // 股价走势（P1-8）：选中公司的归一化走势
  const [priceCode, setPriceCode] = useState('')
  const [priceData, setPriceData] = useState<{ date: string; close: number }[]>([])
  const priceChartRef = useRef<HTMLDivElement>(null)

  const loadComparables = useCallback(async (): Promise<void> => {
    if (projectId === null) return
    try {
      setComparables((await window.finengine.getComparables(projectId)) as Comparable[])
    } catch (e) {
      setError(String(e))
    }
  }, [projectId])

  useEffect(() => {
    loadComparables()
  }, [loadComparables])

  useEffect(() => {
    const timer = setTimeout(async () => {
      if (projectId === null || query.trim().length < 1) {
        setHits([])
        return
      }
      try {
        const resp = (await window.finengine.searchStocks(query.trim())) as { results: StockHit[] }
        setHits(resp.results ?? [])
      } catch {
        setHits([])
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [query, projectId])

  const addCompany = async (hit: StockHit): Promise<void> => {
    if (projectId === null) return
    try {
      await window.finengine.addComparable(projectId, hit)
      setQuery('')
      setHits([])
      await loadComparables()
    } catch (e) {
      setError(String(e))
    }
  }

  const removeCompany = async (c: Comparable): Promise<void> => {
    if (projectId === null) return
    try {
      await window.finengine.removeComparable(projectId, c.id)
      await loadComparables()
      setCompanies((prev) => prev.filter((x) => x.code !== c.code))
    } catch (e) {
      setError(String(e))
    }
  }

  const fetchComparison = async (refresh: boolean): Promise<void> => {
    if (projectId === null || comparables.length === 0) return
    setLoading(true)
    setError('')
    try {
      const resp = (await window.finengine.getComparison(projectId, refresh)) as {
        companies: CompanyData[]
        fetched_at?: string
        note?: string
      }
      setCompanies(resp.companies ?? [])
      setFetchedAt(resp.fetched_at ?? '')
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  // 图表
  // 股价走势图（P1-8）
  useEffect(() => {
    if (!priceChartRef.current || priceData.length === 0) return
    const chart = echarts.init(priceChartRef.current)
    chart.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 50, right: 20, top: 20, bottom: 30 },
      xAxis: {
        type: 'category',
        data: priceData.map((d) => d.date),
        axisLabel: { color: '#7a8aa0', formatter: (v: string) => v.slice(5) }
      },
      yAxis: {
        type: 'value',
        scale: true,
        axisLabel: { color: '#7a8aa0' },
        splitLine: { lineStyle: { color: '#eef2f7' } }
      },
      series: [
        {
          type: 'line',
          data: priceData.map((d) => d.close),
          showSymbol: false,
          lineStyle: { color: '#1B3A6B', width: 1.8 },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(74, 144, 217, 0.25)' },
              { offset: 1, color: 'rgba(74, 144, 217, 0.02)' }
            ])
          }
        }
      ]
    })
    const onResize = (): void => chart.resize()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      chart.dispose()
    }
  }, [priceData])

  useEffect(() => {
    if (!chartRef.current || companies.length === 0) return
    const chart = echarts.init(chartRef.current)
    const ind = INDICATORS.find((i) => i.key === chartKey)
    const names = companies.map((c) => c.name)
    const values = companies.map((c) => getValue(c, chartKey))
    chart.setOption({
      title: { text: `${ind?.label ?? chartKey}对比`, textStyle: { fontSize: 13, color: '#1B3A6B', fontWeight: 600 } },
      tooltip: { valueFormatter: (v: unknown) => (v === null ? '—' : Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 2 })) },
      grid: { left: 60, right: 20, top: 40, bottom: 30 },
      xAxis: { type: 'category', data: names, axisLabel: { color: '#7a8aa0', interval: 0, rotate: names.length > 4 ? 20 : 0 } },
      yAxis: { type: 'value', scale: true, axisLabel: { color: '#7a8aa0' }, splitLine: { lineStyle: { color: '#eef2f7' } } },
      series: [{
        type: 'bar',
        data: values,
        barMaxWidth: 60,
        itemStyle: { color: '#4A90D9', borderRadius: [4, 4, 0, 0] },
        label: { show: true, position: 'top', fontSize: 10, formatter: (p: { value: number | null }) => (p.value === null ? '' : Number(p.value).toLocaleString('zh-CN', { maximumFractionDigits: 2 })) }
      }]
    })
    const onResize = (): void => chart.resize()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      chart.dispose()
    }
  }, [companies, chartKey])

  if (projectId === null) {
    return (
      <div>
        <h2>同行对比</h2>
        <p className="placeholder">请先在「项目档案」中选择一个项目。</p>
      </div>
    )
  }

  return (
    <div className="comparison-view">
      <h2>同行业公司对比</h2>
      <p className="placeholder">
        搜索并添加同行业 A 股上市公司，对比财务指标与估值。数据来自公开行情与财报（本地缓存，点「刷新数据」更新）。
        市占率暂无免费数据源，需要时可在报告导出阶段人工补充。
      </p>
      {error && <div className="error-banner">{error}</div>}

      <div className="comp-search-row">
        <div className="comp-search-box">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="输入公司名称或代码，如：沈鼓集团 / 601091"
          />
          {hits.length > 0 && (
            <ul className="comp-suggestions">
              {hits.map((h) => (
                <li key={h.code} onClick={() => addCompany(h)}>
                  <span className="sugg-name">{h.name}</span>
                  <span className="sugg-code">{h.code}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <button
          className="btn btn-primary btn-sm"
          onClick={() => fetchComparison(true)}
          disabled={loading || comparables.length === 0}
        >
          {loading ? '获取数据中…' : '↻ 刷新数据'}
        </button>
        <button
          className="btn btn-sm"
          onClick={async () => {
            try {
              await window.finengine.exportFile(projectId, 'comparison')
            } catch (e) {
              setError(String(e))
            }
          }}
          disabled={companies.length === 0}
        >
          ⬇ 导出对比表（Excel）
        </button>
      </div>

      <div className="comp-chips">
        {comparables.map((c) => (
          <span key={c.id} className="comp-chip">
            {c.name}（{c.code}）
            <button onClick={() => removeCompany(c)} title="移除">×</button>
          </span>
        ))}
        {comparables.length === 0 && (
          <span className="placeholder">还没有可比公司——搜索并添加同行业公司开始对比。</span>
        )}
      </div>

      {companies.length > 0 && (
        <>
          <div className="comp-table-wrap">
            <table className="comp-table">
              <thead>
                <tr>
                  <th>指标（{companies[0]?.year ?? '-'}年）</th>
                  {companies.map((c) => (
                    <th key={c.code}>{c.name}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {INDICATORS.map((ind) => (
                  <tr key={ind.key} className={ind.key === chartKey ? 'comp-row-active' : ''} onClick={() => setChartKey(ind.key)}>
                    <td className="comp-indicator">{ind.label}</td>
                    {companies.map((c) => (
                      <td key={c.code}>{ind.format(getValue(c, ind.key))}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div ref={chartRef} className="comp-chart" />
          {fetchedAt && <p className="placeholder">数据获取时间：{fetchedAt.replace('T', ' ')}</p>}

          <div className="comp-price-section">
            <div className="pane-header">
              <h4>股价走势（近一年，前复权）</h4>
              <select
                value={priceCode}
                onChange={async (e) => {
                  const code = e.target.value
                  setPriceCode(code)
                  if (!code) {
                    setPriceData([])
                    return
                  }
                  try {
                    const resp = (await window.finengine.getPriceHistory(code)) as {
                      history: { date: string; close: number }[]
                    }
                    setPriceData(resp.history ?? [])
                  } catch {
                    setPriceData([])
                  }
                }}
              >
                <option value="">选择公司</option>
                {companies.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
            {priceData.length > 0 && <div ref={priceChartRef} className="comp-price-chart" />}
          </div>

          <div className="risk-section">
            <ValuationPanel projectId={projectId} />
          </div>
        </>
      )}
    </div>
  )
}
