/** 预加载桥的类型声明（renderer 可见） */
export interface ProjectInfo {
  id: number
  name: string
  company_name: string | null
  company_code: string | null
  created_at: string | null
  files?: FileInfo[]
}

export interface FileInfo {
  id: number
  project_id: number
  original_name: string
  file_type: string
  size_bytes: number
  status: string // uploaded | parsing | ready | failed
  page_count: number
  parse_progress: number
  error: string | null
  created_at: string | null
}

export interface IndicatorInfo {
  id: number
  name: string
  period: string
  value: number
  unit: string
  source_file_id: number | null
  source_page: number | null
  derived: string | null
}

export interface FinancialLineInfo {
  id: number
  indicator: string
  period: string
  value: number
  unit: string
  page_no: number
  bbox: string | null
  label: string
  derived: string | null
}

export interface FinEngineBridge {
  health(): Promise<{ status: string; version?: string }>
  info(): Promise<Record<string, unknown> | null>
  listProjects(): Promise<ProjectInfo[]>
  createProject(payload: {
    name: string
    company_name?: string
    company_code?: string
  }): Promise<ProjectInfo>
  getProject(id: number): Promise<ProjectInfo>
  deleteProject(id: number): Promise<{ ok: boolean }>
  uploadFiles(projectId: number): Promise<FileInfo[] | null>
  getFile(id: number): Promise<FileInfo>
  getIndicators(projectId: number): Promise<IndicatorInfo[]>
  getFileContent(id: number): Promise<ArrayBuffer>
  getFileLines(id: number): Promise<FinancialLineInfo[]>
  updateIndicator(id: number, payload: { value?: number; unit?: string }): Promise<{ ok: boolean }>
  deleteIndicator(id: number): Promise<{ ok: boolean }>
  getAnomalies(projectId: number): Promise<unknown[]>
  analyzeProject(projectId: number): Promise<{ anomalies: unknown[] }>
  searchProject(projectId: number, query: string): Promise<{ results: unknown[] }>
  getAIProviders(): Promise<
    { id: string; name: string; default_model: string; register_url: string }[]
  >
  getAISettings(): Promise<{ provider: string; model: string; has_key: boolean }>
  saveAISettings(payload: {
    provider: string
    model?: string
    api_key?: string
    quick_provider?: string
    quick_model?: string
    quick_api_key?: string
  }): Promise<{ ok: boolean }>
  chatProject(projectId: number, question: string): Promise<unknown>
  searchStocks(q: string): Promise<{ results: { code: string; name: string }[] }>
  getComparables(projectId: number): Promise<{ id: number; code: string; name: string }[]>
  addComparable(projectId: number, payload: { code: string; name: string }): Promise<{ ok: boolean }>
  removeComparable(projectId: number, comparableId: number): Promise<{ ok: boolean }>
  getComparison(projectId: number, refresh: boolean): Promise<unknown>
  exportFile(projectId: number, type: 'anomalies' | 'indicators' | 'comparison'): Promise<string | null>
  fetchAnnouncements(projectId: number): Promise<unknown>
  getAnnouncements(projectId: number): Promise<unknown>
  summarizeAnnouncements(projectId: number): Promise<unknown>
  getRiskScore(projectId: number): Promise<unknown>
  getNotes(projectId: number): Promise<unknown>
  addNote(projectId: number, content: string): Promise<unknown>
  reflectNotes(projectId: number): Promise<unknown>
  valuationComparable(projectId: number): Promise<unknown>
  valuationDcf(projectId: number, inputs: unknown): Promise<unknown>
  getValuationRuns(projectId: number): Promise<unknown>
  getPriceHistory(code: string): Promise<unknown>
  getRules(): Promise<{
    rules: {
      rule_id: string
      title: string
      severity: string
      enabled: boolean
      params: { name: string; label: string; default: number; value: number }[]
    }[]
  }>
  saveRules(settings: Record<string, unknown>): Promise<{ ok: boolean }>
}

declare global {
  interface Window {
    finengine: FinEngineBridge
  }
}
