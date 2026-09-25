import { useCallback, useState } from 'react'
import PdfSourceModal from './PdfSourceModal'

interface SearchResult {
  file_id: number
  page_no: number
  snippet: string
  matched_term: string
  score: number
  file_name: string
}

export default function SearchView({
  projectId
}: {
  projectId: number | null
}): React.JSX.Element {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [searched, setSearched] = useState(false)
  const [searching, setSearching] = useState(false)
  const [viewer, setViewer] = useState<{
    fileId: number
    fileName: string
    page: number
  } | null>(null)
  const [error, setError] = useState('')

  const doSearch = useCallback(async (): Promise<void> => {
    if (projectId === null || query.trim().length < 2) return
    setSearching(true)
    setError('')
    try {
      const resp = (await window.finengine.searchProject(projectId, query.trim())) as {
        results: SearchResult[]
      }
      setResults(resp.results ?? [])
      setSearched(true)
    } catch (e) {
      setError(String(e))
    } finally {
      setSearching(false)
    }
  }, [projectId, query])

  if (projectId === null) {
    return (
      <div>
        <h2>全文搜索</h2>
        <p className="placeholder">请先在「项目档案」中选择一个项目。</p>
      </div>
    )
  }

  return (
    <div className="search-view">
      <h2>全文搜索</h2>
      <p className="placeholder">
        在项目全部资料中搜索关键词（如"主要客户""应收账款"），结果带页码与上下文，点击可跳回原文。
        已内置金融术语同义词：搜"主要客户"会同时匹配"前五大客户"等写法。
      </p>
      <div className="search-bar">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && doSearch()}
          placeholder="输入关键词，如：主要客户、应收账款、毛利率…"
          autoFocus
        />
        <button className="btn btn-primary" onClick={doSearch} disabled={searching}>
          {searching ? '搜索中…' : '搜索'}
        </button>
      </div>
      {error && <div className="error-banner">{error}</div>}

      {searched && (
        <div className="search-results">
          <p className="result-count">共 {results.length} 条结果</p>
          {results.length === 0 && (
            <p className="placeholder">没有找到相关内容。换个关键词试试（支持同义词匹配）。</p>
          )}
          <ul className="result-list">
            {results.map((r, i) => (
              <li key={i} className="result-item" onClick={() => setViewer({
                fileId: r.file_id,
                fileName: r.file_name,
                page: r.page_no
              })}>
                <div className="result-head">
                  <span className="result-page">第 {r.page_no} 页</span>
                  <span className="result-file">{r.file_name}</span>
                </div>
                <p className="result-snippet">{r.snippet}</p>
              </li>
            ))}
          </ul>
        </div>
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
