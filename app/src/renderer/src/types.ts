/** 与 preload/index.d.ts 对应的界面数据类型（避免组件直接依赖全局声明） */
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
  status: string
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
