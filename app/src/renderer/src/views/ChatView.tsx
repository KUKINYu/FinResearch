import { useCallback, useEffect, useRef, useState } from 'react'
import PdfSourceModal from './PdfSourceModal'

interface ProviderInfo {
  id: string
  name: string
  default_model: string
  register_url: string
}

interface AISettings {
  provider: string
  model: string
  has_key: boolean
  quick_provider: string
  quick_model: string
  has_quick_key: boolean
}

interface ChatSource {
  file_id: number
  page_no: number
  snippet: string
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: ChatSource[]
  usage?: { prompt_tokens: number; completion_tokens: number; model: string }
  error?: boolean
}

export default function ChatView({
  projectId
}: {
  projectId: number | null
}): React.JSX.Element {
  const [providers, setProviders] = useState<ProviderInfo[]>([])
  const [settings, setSettings] = useState<AISettings | null>(null)
  const [setupOpen, setSetupOpen] = useState(false)
  const [selProvider, setSelProvider] = useState('deepseek')
  const [selModel, setSelModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [quickProvider, setQuickProvider] = useState('')
  const [quickModel, setQuickModel] = useState('')
  const [quickKey, setQuickKey] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const [viewer, setViewer] = useState<{
    fileId: number
    fileName: string
    page: number
  } | null>(null)
  const [error, setError] = useState('')
  const listRef = useRef<HTMLDivElement>(null)

  const loadProviders = useCallback(async () => {
    try {
      const ps = (await window.finengine.getAIProviders()) as ProviderInfo[]
      setProviders(ps)
      const s = (await window.finengine.getAISettings()) as AISettings
      setSettings(s)
      setSelProvider(s.provider || 'deepseek')
      setSelModel(s.model)
      setQuickProvider(s.quick_provider)
      setQuickModel(s.quick_model)
    } catch (e) {
      setError(String(e))
    }
  }, [])

  useEffect(() => {
    loadProviders()
  }, [loadProviders])

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight })
  }, [messages])

  const saveSettings = async (): Promise<void> => {
    try {
      await window.finengine.saveAISettings({
        provider: selProvider,
        model: selModel,
        api_key: apiKey,
        quick_provider: quickProvider,
        quick_model: quickModel,
        quick_api_key: quickKey
      })
      setSetupOpen(false)
      setApiKey('')
      await loadProviders()
    } catch (e) {
      setError(String(e))
    }
  }

  const ask = async (): Promise<void> => {
    if (projectId === null || question.trim().length < 2 || busy) return
    const q = question.trim()
    setQuestion('')
    setMessages((m) => [...m, { role: 'user', content: q }])
    setBusy(true)
    setError('')
    try {
      const resp = (await window.finengine.chatProject(projectId, q)) as {
        ok: boolean
        answer?: string
        error?: string
        sources?: ChatSource[]
        usage?: ChatMessage['usage']
      }
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          content: resp.ok ? (resp.answer ?? '') : (resp.error ?? '调用失败'),
          sources: resp.sources,
          usage: resp.usage,
          error: !resp.ok
        }
      ])
    } catch (e) {
      setMessages((m) => [...m, { role: 'assistant', content: String(e), error: true }])
    } finally {
      setBusy(false)
    }
  }

  const openSource = (s: ChatSource): void => {
    setViewer({ fileId: s.file_id, fileName: '原始文件', page: s.page_no })
  }

  if (projectId === null) {
    return (
      <div>
        <h2>AI 问答</h2>
        <p className="placeholder">请先在「项目档案」中选择一个项目。</p>
      </div>
    )
  }

  const needsSetup = settings !== null && (!settings.provider || !settings.has_key)

  return (
    <div className="chat-view">
      <div className="chat-header">
        <h2>AI 问答</h2>
        <button className="btn btn-sm" onClick={() => setSetupOpen(!setupOpen)}>
          ⚙ AI 设置
        </button>
      </div>
      <p className="placeholder">
        回答严格基于你上传的资料，每个结论标注出处页码；资料中没有的内容不会编造。
        使用你自己的 API Key（BYOK），费用由你的账号承担，资料只把相关片段发给 AI。
      </p>
      {error && <div className="error-banner">{error}</div>}

      {setupOpen && (
        <div className="ai-setup-panel">
          <h4>配置 AI 服务（BYOK）</h4>
          <div className="setup-row">
            <label>服务商</label>
            <select
              value={selProvider}
              onChange={(e) => {
                setSelProvider(e.target.value)
                const p = providers.find((x) => x.id === e.target.value)
                setSelModel(p?.default_model ?? '')
              }}
            >
              {providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            {providers.find((p) => p.id === selProvider) && (
              <a
                className="register-link"
                href={providers.find((p) => p.id === selProvider)!.register_url}
                target="_blank"
                rel="noreferrer"
              >
                去注册获取 Key
              </a>
            )}
          </div>
          <div className="setup-row">
            <label>模型</label>
            <input value={selModel} onChange={(e) => setSelModel(e.target.value)} />
          </div>
          <div className="setup-row">
            <label>API Key</label>
            <input
              type="password"
              placeholder={settings?.has_key ? '已保存（留空则不修改）' : '粘贴你的 API Key'}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
          </div>
          <p className="setup-note">—— 以下为「快速任务模型」配置（可选）：公告摘要、风险小结等轻量任务用它，可省 token ——</p>
          <div className="setup-row">
            <label>快速模型</label>
            <select
              value={quickProvider}
              onChange={(e) => {
                setQuickProvider(e.target.value)
                const p = providers.find((x) => x.id === e.target.value)
                if (p) setQuickModel(p.default_model)
              }}
            >
              <option value="">不单独配置（用上面的模型）</option>
              {providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
          {quickProvider && (
            <>
              <div className="setup-row">
                <label>快速 Key</label>
                <input
                  type="password"
                  placeholder={settings?.has_quick_key ? '已保存（留空则不修改）' : '粘贴快速模型 API Key'}
                  value={quickKey}
                  onChange={(e) => setQuickKey(e.target.value)}
                />
              </div>
              <div className="setup-row">
                <label>模型名</label>
                <input value={quickModel} onChange={(e) => setQuickModel(e.target.value)} />
              </div>
            </>
          )}
          <div className="setup-actions">
            <button className="btn btn-primary btn-sm" onClick={saveSettings}>
              保存
            </button>
            <button className="btn btn-sm" onClick={() => setSetupOpen(false)}>
              取消
            </button>
          </div>
          <p className="setup-note">
            Key 使用 Windows 系统级加密存储在本机，不会上传给任何服务器。
          </p>
        </div>
      )}

      {needsSetup && !setupOpen ? (
        <div className="chat-need-setup">
          <p>使用 AI 问答前，需要先配置你自己的 AI 服务 Key（不配置也能使用其他全部功能）。</p>
          <button className="btn btn-primary" onClick={() => setSetupOpen(true)}>
            去配置 AI 服务
          </button>
        </div>
      ) : (
        <>
          <div className="chat-list" ref={listRef}>
            {messages.length === 0 && (
              <p className="placeholder">
                试试问："这家公司的毛利率变化原因是什么？""应收账款增长较快的原因？"
              </p>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`chat-msg chat-${m.role}${m.error ? ' chat-error' : ''}`}>
                <div className="chat-bubble">{m.content}</div>
                {m.sources && m.sources.length > 0 && (
                  <div className="chat-sources">
                    <span className="chat-sources-label">引用来源：</span>
                    {m.sources.map((s, j) => (
                      <button key={j} className="data-point-chip" onClick={() => openSource(s)}>
                        第 {s.page_no} 页
                      </button>
                    ))}
                  </div>
                )}
                {m.usage && (
                  <div className="chat-usage">
                    {m.usage.model} · 输入 {m.usage.prompt_tokens} tokens · 输出{' '}
                    {m.usage.completion_tokens} tokens
                  </div>
                )}
              </div>
            ))}
            {busy && <div className="chat-msg chat-assistant">分析中…（检索资料并生成回答）</div>}
          </div>
          <div className="chat-input-row">
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && ask()}
              placeholder="基于本项目资料提问…"
              disabled={busy}
            />
            <button className="btn btn-primary" onClick={ask} disabled={busy || question.trim().length < 2}>
              发送
            </button>
          </div>
        </>
      )}

      {viewer && (
        <PdfSourceModal
          fileId={viewer.fileId}
          fileName={viewer.fileName}
          page={viewer.page}

          onClose={() => setViewer(null)}
        />
      )}
    </div>
  )
}
