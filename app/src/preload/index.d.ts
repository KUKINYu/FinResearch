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
}

declare global {
  interface Window {
    finengine: FinEngineBridge
  }
}
