import { useEffect, useRef } from 'react'
import * as echarts from 'echarts'

export interface TrendPoint {
  period: string
  value: number
  unit: string
}

interface Props {
  indicatorName: string
  data: TrendPoint[]
}

/** 单指标历年趋势折线图（金融终端风格配色）。 */
export default function TrendChart({ indicatorName, data }: Props): React.JSX.Element {
  const chartRef = useRef<HTMLDivElement>(null)
  const chartInstance = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    if (!chartRef.current) return
    chartInstance.current = echarts.init(chartRef.current)
    const onResize = (): void => chartInstance.current?.resize()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      chartInstance.current?.dispose()
      chartInstance.current = null
    }
  }, [])

  useEffect(() => {
    const chart = chartInstance.current
    if (!chart) return
    const unit = data[0]?.unit ?? ''
    const isPercent = unit === '%'
    chart.setOption(
      {
        title: {
          text: `${indicatorName}趋势（单位：${unit}）`,
          textStyle: { fontSize: 13, color: '#1B3A6B', fontWeight: 600 }
        },
        tooltip: {
          trigger: 'axis',
          valueFormatter: (v: unknown) =>
            `${Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 2 })}${isPercent ? '%' : ''}`
        },
        grid: { left: 70, right: 30, top: 44, bottom: 34 },
        xAxis: {
          type: 'category',
          data: data.map((d) => d.period),
          axisLabel: { color: '#7a8aa0' },
          axisLine: { lineStyle: { color: '#e3e8ef' } }
        },
        yAxis: {
          type: 'value',
          scale: true,
          axisLabel: {
            color: '#7a8aa0',
            formatter: (v: number) =>
              `${v.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}${isPercent ? '%' : ''}`
          },
          splitLine: { lineStyle: { color: '#eef2f7' } }
        },
        series: [
          {
            type: 'line',
            data: data.map((d) => d.value),
            smooth: true,
            symbolSize: 7,
            lineStyle: { color: '#1B3A6B', width: 2.5 },
            itemStyle: { color: '#4A90D9', borderColor: '#1B3A6B', borderWidth: 1.5 },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(74, 144, 217, 0.28)' },
                { offset: 1, color: 'rgba(74, 144, 217, 0.02)' }
              ])
            },
            markPoint: {
              data: [
                { type: 'max', name: '最大值' },
                { type: 'min', name: '最小值' }
              ],
              label: { fontSize: 10, color: '#1B3A6B' },
              symbolSize: 32
            }
          }
        ]
      },
      { notMerge: true }
    )
  }, [indicatorName, data])

  return <div ref={chartRef} className="trend-chart" />
}
