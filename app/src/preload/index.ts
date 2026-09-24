import { contextBridge, ipcRenderer } from 'electron'

// 界面只通过这个桥与主进程/引擎通信（不直接接触引擎端口与令牌）
contextBridge.exposeInMainWorld('finengine', {
  health: (): Promise<unknown> => ipcRenderer.invoke('engine:health'),
  info: (): Promise<unknown> => ipcRenderer.invoke('engine:info'),
  // M2：项目/文件管理
  listProjects: (): Promise<unknown> => ipcRenderer.invoke('engine:projects:list'),
  createProject: (payload: unknown): Promise<unknown> =>
    ipcRenderer.invoke('engine:projects:create', payload),
  getProject: (id: number): Promise<unknown> => ipcRenderer.invoke('engine:projects:get', id),
  deleteProject: (id: number): Promise<unknown> => ipcRenderer.invoke('engine:projects:delete', id),
  uploadFiles: (projectId: number): Promise<unknown> =>
    ipcRenderer.invoke('engine:files:upload', projectId),
  getFile: (id: number): Promise<unknown> => ipcRenderer.invoke('engine:files:get', id),
  getIndicators: (projectId: number): Promise<unknown> =>
    ipcRenderer.invoke('engine:indicators:get', projectId),
  // M3：阅读器与校对
  getFileContent: (id: number): Promise<ArrayBuffer> =>
    ipcRenderer.invoke('engine:file:content', id),
  getFileLines: (id: number): Promise<unknown> => ipcRenderer.invoke('engine:file:lines', id),
  updateIndicator: (id: number, payload: unknown): Promise<unknown> =>
    ipcRenderer.invoke('engine:indicators:update', id, payload),
  deleteIndicator: (id: number): Promise<unknown> =>
    ipcRenderer.invoke('engine:indicators:delete', id),
  // M5：异常检测
  getAnomalies: (projectId: number): Promise<unknown> =>
    ipcRenderer.invoke('engine:anomalies:get', projectId),
  analyzeProject: (projectId: number): Promise<unknown> =>
    ipcRenderer.invoke('engine:analyze', projectId),
  // M6：全文搜索
  searchProject: (projectId: number, query: string): Promise<unknown> =>
    ipcRenderer.invoke('engine:search', projectId, query),
  // M7：AI 问答
  getAIProviders: (): Promise<unknown> => ipcRenderer.invoke('engine:ai:providers'),
  getAISettings: (): Promise<unknown> => ipcRenderer.invoke('engine:ai:settings:get'),
  saveAISettings: (payload: unknown): Promise<unknown> =>
    ipcRenderer.invoke('engine:ai:settings:save', payload),
  chatProject: (projectId: number, question: string): Promise<unknown> =>
    ipcRenderer.invoke('engine:ai:chat', projectId, question),
  // P1：同行对比
  searchStocks: (q: string): Promise<unknown> => ipcRenderer.invoke('engine:market:search', q),
  getComparables: (projectId: number): Promise<unknown> =>
    ipcRenderer.invoke('engine:comparables:get', projectId),
  addComparable: (projectId: number, payload: unknown): Promise<unknown> =>
    ipcRenderer.invoke('engine:comparables:add', projectId, payload),
  removeComparable: (projectId: number, comparableId: number): Promise<unknown> =>
    ipcRenderer.invoke('engine:comparables:remove', projectId, comparableId),
  getComparison: (projectId: number, refresh: boolean): Promise<unknown> =>
    ipcRenderer.invoke('engine:comparison:get', projectId, refresh),
  // P1：导出
  exportFile: (projectId: number, type: string): Promise<string | null> =>
    ipcRenderer.invoke('engine:export:save', projectId, type)
})
