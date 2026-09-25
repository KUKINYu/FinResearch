import { useCallback, useEffect, useRef, useState } from 'react'
import * as echarts from 'echarts'

interface Dimension {
  name: string
  score: number
  basis: string
}

interface RiskScore {
  dimensions: Dimension[]
  overall: number
  level: string
  generated_at: string
}

const LEVEL_CLASS: Record<string, string> = {
  风险较低: 'level-low',
  风险中等: 'level-mid',
  风险偏高: 'level-high',
  风险较高: 'level-critical'
}

export default function RiskScoreCard({
  projectId
}: {
  projectId: number | null
}): React.JSX.Element | null {
  const [score, setScore] = useState<RiskScore | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const chartRef = useRef<HTMLDivElement>(null)

  const load = useCallback(async (): Promise<void> => {
    if (projectId === null) return
    setLoading(true)
    setError('')
    try {
      setScore((await window.finengine.getRiskScore(projectId)) as RiskScore)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (!chartRef.current || !score) return
    const chart = echarts.init(chartRef.current)
    chart.setOption({
      radar: {
        indicator: score.dimensions.map((d) => ({ name: d.name, max: 5, min: 1 })),
        radius: '65%',
        axisName: { color: '#1f2d3d', fontSize: 12 },
        splitLine: { lineStyle: { color: '#e3e8ef' } },
        splitArea: { areaStyle: { color: ['#f5f7fa', '#fff'] } }
      },
      series: [
        {
          type: 'radar',
          data: [
            {
              value: score.dimensions.map((d) => d.score),
              areaStyle: { color: 'rgba(74, 144, 217, 0.25)' },
              lineStyle: { color: '#1B3A6B', width: 2 },
              itemStyle: { color: '#4A90D9' }
            }
          ]
        }
      ]
    })
    const onResize = (): void => chart.resize()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      chart.dispose()
    }
  }, [score])

  if (projectId === null) return null

  return (
    <div className="risk-card">
      <div className="pane-header">
        <h4>尽调风险评分卡</h4>
        <button className="btn btn-sm" onClick={load} disabled={loading}>
          {loading ? '计算中…' : '↻ 重新计算'}
        </button>
      </div>
      {error && <div className="error-banner">{error}</div>}
      {score && (
        <>
          <div className="risk-overall">
            <span className={`risk-level-badge ${LEVEL_CLASS[score.level] ?? ''}`}>
              {score.level}
            </span>
            <span className="risk-total">{score.overall} / 5</span>
            <span className="risk-time">{score.generated_at}</span>
          </div>
          <div className="risk-body">
            <div ref={chartRef} className="risk-radar" />
            <ul className="risk-dims">
              {score.dimensions.map((d) => (
                <li key={d.name}>
                  <span className="risk-dim-name">
                    {d.name}
                    <b>{d.score}</b>
                  </span>
                  <span className="risk-dim-basis">{d.basis}</span>
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </div>
  )
}
