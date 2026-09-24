import { useEffect, useState } from 'react'
import ProjectsView from './views/ProjectsView'
import IndicatorsView from './views/IndicatorsView'
import AnomaliesView from './views/AnomaliesView'
import SearchView from './views/SearchView'
import ChatView from './views/ChatView'
import ComparisonView from './views/ComparisonView'

// 六个工作区（P1 新增同行对比）
const WORKSPACES = ['项目档案', '财务指标', '异常发现', '全文搜索', 'AI 问答', '同行对比'] as const
type Workspace = (typeof WORKSPACES)[number]

export default function App(): React.JSX.Element {
  const [active, setActive] = useState<Workspace>('项目档案')
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null)
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
          {active === '项目档案' && (
            <ProjectsView selectedId={selectedProjectId} onSelect={setSelectedProjectId} />
          )}
          {active === '财务指标' && <IndicatorsView projectId={selectedProjectId} />}
          {active === '异常发现' && <AnomaliesView projectId={selectedProjectId} />}
          {active === '全文搜索' && <SearchView projectId={selectedProjectId} />}
          {active === 'AI 问答' && <ChatView projectId={selectedProjectId} />}
          {active === '同行对比' && <ComparisonView projectId={selectedProjectId} />}
        </main>
      </div>
    </div>
  )
}
