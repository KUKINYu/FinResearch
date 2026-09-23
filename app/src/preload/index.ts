import { contextBridge, ipcRenderer } from 'electron'

// 界面只通过这个桥与主进程/引擎通信（不直接接触引擎端口与令牌）
contextBridge.exposeInMainWorld('finengine', {
  health: (): Promise<unknown> => ipcRenderer.invoke('engine:health'),
  info: (): Promise<unknown> => ipcRenderer.invoke('engine:info')
})
