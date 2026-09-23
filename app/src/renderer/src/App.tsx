import { useEffect, useState } from 'react'

// 五个工作区（对应产品需求）：P0 各里程碑逐步填充
const WORKSPACES = ['项目档案', '财务指标', '异常发现', '全文搜索', 'AI 问答'] as const
type Workspace = (typeof WORKSPACES)[number]

const PLACEHOLDER: Record<Workspace, string> = {
  项目档案: '创建尽调项目、上传招股书/年报/研报（M2 里程碑上线）',
  财务指标: '10 项核心财务指标卡片与历年趋势图（M4 里程碑上线）',
  异常发现: '财务异常自动检测，每条异常溯源到原文页码（M5 里程碑上线）',
  全文搜索: '跨文件全文搜索，结果带页码与摘录（M6 里程碑上线）',
  'AI 问答': '基于上传资料的 AI 辅助分析，回答带出处、不编造（M7 里程碑上线）'
}

export default function App(): React.JSX.Element {
  const [active, setActive] = useState<Workspace>('项目档案')
  const [engineState, setEngineState] = useState<'检查中' | '已连接' | '未连接'>('检查中')
  const [version, setVersion] = useState('')

  useEffect(() => {
    window.finengine
      .health()
      .then((h) => {
        setEngineState(h.status === 'ok' ? '已连接' : '未连接')
        if (h.status === 'ok') setVersion(h.version ?? '')
      })
      .catch(() => setEngineState('未连接'))
  }, [])

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">FinResearch</span>
          <span className="subtitle">金融研究与尽调辅助软件</span>
        </div>
        <div className={`engine-state ${engineState === '已连接' ? 'ok' : engineState === '检查中' ? '' : 'off'}`}>
          <span className="dot" />
          数据引擎 {engineState}
          {version && <span className="engine-version">v{version}</span>}
        </div>
      </header>
      <div className="body">
        <nav className="sidebar">
          {WORKSPACES.map((w) => (
            <button
              key={w}
              className={w === active ? 'nav-item active' : 'nav-item'}
              onClick={() => setActive(w)}
            >
              {w}
            </button>
          ))}
        </nav>
        <main className="content">
          <h2>{active}</h2>
          <p className="placeholder">{PLACEHOLDER[active]}</p>
        </main>
      </div>
    </div>
  )
}
