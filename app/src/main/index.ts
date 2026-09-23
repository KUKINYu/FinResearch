import { app, BrowserWindow, ipcMain } from 'electron'
import { spawn, type ChildProcess } from 'node:child_process'
import { join } from 'node:path'
import { existsSync } from 'node:fs'

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
async function engineRequest(path: string): Promise<unknown> {
  const res = await fetch(`http://127.0.0.1:${engine.port}${path}`, {
    headers: { 'X-FinEngine-Token': engine.token }
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
