import { app, BrowserWindow, dialog, ipcMain } from 'electron'
import { spawn, type ChildProcess } from 'node:child_process'
import { join } from 'node:path'
import { existsSync, readFileSync, writeFileSync } from 'node:fs'

// 引擎握手信息：解析引擎 stdout 的 ready 行得到
let engine = { port: 0, token: '' }
let engineProc: ChildProcess | null = null

/**
 * 引擎启动命令：
 * - 开发模式：engine/.venv 的 python（setup.bat 创建），否则系统 python
 * - 打包后：resources/engine/finengine.exe
 */
function engineCommand(): { cmd: string; args: string[]; cwd: string } {
  const engineDir = app.isPackaged
    ? join(process.resourcesPath, 'engine')
    : join(app.getAppPath(), '..', 'engine')
  if (app.isPackaged) {
    return { cmd: join(engineDir, 'finengine.exe'), args: ['serve'], cwd: engineDir }
  }
  const venvPython = join(engineDir, '.venv', 'Scripts', 'python.exe')
  const python = existsSync(venvPython) ? venvPython : 'python'
  return { cmd: python, args: ['-m', 'finengine', 'serve'], cwd: engineDir }
}

/** 拉起引擎进程，等待 stdout 的 ready 行（{"event":"ready","port":N,"token":"..."}） */
function startEngine(): Promise<{ port: number; token: string }> {
  return new Promise((resolve, reject) => {
    const { cmd, args, cwd } = engineCommand()
    const proc = spawn(cmd, args, { cwd, windowsHide: true })
    engineProc = proc
    const timer = setTimeout(() => reject(new Error('引擎启动超时（60 秒）')), 60_000)
    proc.stdout.on('data', (buf: Buffer) => {
      for (const line of buf.toString().split('\n')) {
        try {
          const msg = JSON.parse(line)
          if (msg.event === 'ready') {
            clearTimeout(timer)
            engine = { port: msg.port, token: msg.token }
            resolve(engine)
          }
        } catch {
          // 非 JSON 行（如日志）忽略
        }
      }
    })
    proc.stderr.on('data', (d) => console.error('[finengine]', String(d)))
    proc.on('exit', (code) => {
      clearTimeout(timer)
      reject(new Error(`引擎进程退出（code=${code}）`))
    })
  })
}

/** 调用引擎 API（界面不直接接触端口/令牌，统一走主进程） */
async function engineRequest(
  path: string,
  options?: { method?: string; body?: unknown }
): Promise<unknown> {
  const res = await fetch(`http://127.0.0.1:${engine.port}${path}`, {
    method: options?.method ?? 'GET',
    headers: {
      'X-FinEngine-Token': engine.token,
      ...(options?.body !== undefined ? { 'Content-Type': 'application/json' } : {})
    },
    body: options?.body !== undefined ? JSON.stringify(options.body) : undefined
  })
  if (!res.ok) throw new Error(`引擎请求失败（HTTP ${res.status}）`)
  return res.json()
}

function createWindow(): void {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 1024,
    minHeight: 700,
    title: 'FinResearch — 金融研究与尽调辅助软件',
    autoHideMenuBar: true,
    backgroundColor: '#f5f7fa',
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      sandbox: false
    }
  })
  // electron-vite 开发模式注入渲染进程地址；打包后加载构建产物
  if (process.env['ELECTRON_RENDERER_URL']) {
    win.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    win.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

app.whenReady().then(async () => {
  try {
    await startEngine()
    console.log(`[finengine] 引擎就绪 127.0.0.1:${engine.port}`)
  } catch (err) {
    console.error('[finengine] 启动失败：', err)
  }

  ipcMain.handle('engine:health', async () => {
    try {
      const result = await engineRequest('/api/health')
      console.log('[finengine] 界面已发起健康检查并得到引擎响应，链路打通')
      return result
    } catch {
      return { status: 'offline' }
    }
  })
  ipcMain.handle('engine:info', async () => {
    try {
      return await engineRequest('/api/info')
    } catch {
      return null
    }
  })

  // ---- M2：项目/文件管理 ----
  ipcMain.handle('engine:projects:list', () => engineRequest('/api/projects'))
  ipcMain.handle('engine:projects:create', (_e, payload: unknown) =>
    engineRequest('/api/projects', { method: 'POST', body: payload })
  )
  ipcMain.handle('engine:projects:get', (_e, id: number) => engineRequest(`/api/projects/${id}`))
  ipcMain.handle('engine:projects:delete', (_e, id: number) =>
    engineRequest(`/api/projects/${id}`, { method: 'DELETE' })
  )
  ipcMain.handle('engine:files:get', (_e, id: number) => engineRequest(`/api/files/${id}`))
  ipcMain.handle('engine:indicators:get', (_e, projectId: number) =>
    engineRequest(`/api/projects/${projectId}/indicators`)
  )
  // M3：阅读器与校对
  ipcMain.handle('engine:file:content', async (_e, id: number) => {
    const res = await fetch(`http://127.0.0.1:${engine.port}/api/files/${id}/content`, {
      headers: { 'X-FinEngine-Token': engine.token }
    })
    if (!res.ok) throw new Error(`读取文件失败（HTTP ${res.status}）`)
    return await res.arrayBuffer()
  })
  ipcMain.handle('engine:file:lines', (_e, id: number) => engineRequest(`/api/files/${id}/lines`))
  ipcMain.handle('engine:indicators:update', (_e, id: number, payload: unknown) =>
    engineRequest(`/api/indicators/${id}`, { method: 'PATCH', body: payload })
  )
  ipcMain.handle('engine:indicators:delete', (_e, id: number) =>
    engineRequest(`/api/indicators/${id}`, { method: 'DELETE' })
  )
  // M5：异常检测
  ipcMain.handle('engine:anomalies:get', (_e, projectId: number) =>
    engineRequest(`/api/projects/${projectId}/anomalies`)
  )
  ipcMain.handle('engine:analyze', (_e, projectId: number) =>
    engineRequest(`/api/projects/${projectId}/analyze`, { method: 'POST' })
  )
  // M6：全文搜索
  ipcMain.handle('engine:search', (_e, projectId: number, query: string) =>
    engineRequest(`/api/projects/${projectId}/search`, { method: 'POST', body: { query } })
  )
  // M7：AI 问答（BYOK）
  ipcMain.handle('engine:ai:providers', () => engineRequest('/api/ai/providers'))
  ipcMain.handle('engine:ai:settings:get', () => engineRequest('/api/settings/ai'))
  ipcMain.handle('engine:ai:settings:save', (_e, payload: unknown) =>
    engineRequest('/api/settings/ai', { method: 'POST', body: payload })
  )
  ipcMain.handle('engine:ai:chat', (_e, projectId: number, question: string) =>
    engineRequest(`/api/projects/${projectId}/chat`, { method: 'POST', body: { question } })
  )
  // P1：同行对比
  ipcMain.handle('engine:market:search', (_e, q: string) =>
    engineRequest(`/api/market/search?q=${encodeURIComponent(q)}`)
  )
  ipcMain.handle('engine:comparables:get', (_e, projectId: number) =>
    engineRequest(`/api/projects/${projectId}/comparables`)
  )
  ipcMain.handle('engine:comparables:add', (_e, projectId: number, payload: unknown) =>
    engineRequest(`/api/projects/${projectId}/comparables`, { method: 'POST', body: payload })
  )
  ipcMain.handle('engine:comparables:remove', (_e, projectId: number, comparableId: number) =>
    engineRequest(`/api/projects/${projectId}/comparables/${comparableId}`, { method: 'DELETE' })
  )
  ipcMain.handle('engine:comparison:get', (_e, projectId: number, refresh: boolean) =>
    engineRequest(`/api/projects/${projectId}/comparison?refresh=${refresh ? 1 : 0}`)
  )
  // P1：规则设置
  ipcMain.handle('engine:rules:get', () => engineRequest('/api/rules'))
  ipcMain.handle('engine:rules:save', (_e, settings: unknown) =>
    engineRequest('/api/rules', { method: 'POST', body: { settings } })
  )
  // P1：公告监控 / 风险评分卡 / 研究笔记
  ipcMain.handle('engine:announcements:fetch', (_e, projectId: number) =>
    engineRequest(`/api/projects/${projectId}/announcements/fetch`, { method: 'POST' })
  )
  ipcMain.handle('engine:announcements:get', (_e, projectId: number) =>
    engineRequest(`/api/projects/${projectId}/announcements`)
  )
  ipcMain.handle('engine:announcements:summarize', (_e, projectId: number) =>
    engineRequest(`/api/projects/${projectId}/announcements/summarize`, { method: 'POST' })
  )
  ipcMain.handle('engine:riskscore:get', (_e, projectId: number) =>
    engineRequest(`/api/projects/${projectId}/riskscore`)
  )
  ipcMain.handle('engine:notes:get', (_e, projectId: number) =>
    engineRequest(`/api/projects/${projectId}/notes`)
  )
  ipcMain.handle('engine:notes:add', (_e, projectId: number, content: string) =>
    engineRequest(`/api/projects/${projectId}/notes`, { method: 'POST', body: { content } })
  )
  ipcMain.handle('engine:notes:reflect', (_e, projectId: number) =>
    engineRequest(`/api/projects/${projectId}/notes/reflect`, { method: 'POST' })
  )
  // P1：成果导出（引擎生成文件 → 保存对话框 → 写盘）
  ipcMain.handle(
    'engine:export:save',
    async (_e, projectId: number, type: 'anomalies' | 'indicators' | 'comparison') => {
      const names: Record<string, string> = {
        anomalies: '异常清单.docx',
        indicators: '财务指标表.docx',
        comparison: '同行对比.xlsx'
      }
      const res = await fetch(
        `http://127.0.0.1:${engine.port}/api/projects/${projectId}/export/${type}`,
        { headers: { 'X-FinEngine-Token': engine.token } }
      )
      if (!res.ok) throw new Error(`导出失败（HTTP ${res.status}）`)
      const buffer = Buffer.from(await res.arrayBuffer())
      const result = await dialog.showSaveDialog({
        title: '导出文件',
        defaultPath: names[type],
        filters: [
          { name: '文档', extensions: [type === 'comparison' ? 'xlsx' : 'docx'] }
        ]
      })
      if (result.canceled || !result.filePath) return null
      writeFileSync(result.filePath, buffer)
      return result.filePath
    }
  )
  ipcMain.handle('engine:files:upload', async (_e, projectId: number) => {
    const result = await dialog.showOpenDialog({
      title: '选择要上传的资料（PDF / Excel）',
      properties: ['openFile', 'multiSelections'],
      filters: [
        { name: '金融文档', extensions: ['pdf', 'xlsx', 'xls'] },
        { name: '所有文件', extensions: ['*'] }
      ]
    })
    if (result.canceled || result.filePaths.length === 0) return null
    const uploaded = []
    for (const filePath of result.filePaths) {
      const name = filePath.split(/[\\/]/).pop() || '未命名文件'
      const buffer = readFileSync(filePath)
      const form = new FormData()
      form.append('file', new Blob([buffer]), name)
      const res = await fetch(`http://127.0.0.1:${engine.port}/api/projects/${projectId}/files`, {
        method: 'POST',
        headers: { 'X-FinEngine-Token': engine.token },
        body: form
      })
      if (!res.ok) throw new Error(`上传失败（HTTP ${res.status}）`)
      uploaded.push(await res.json())
    }
    return uploaded
  })

  createWindow()
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

app.on('will-quit', () => {
  engineProc?.kill()
})
