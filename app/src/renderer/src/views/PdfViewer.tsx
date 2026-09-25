import { useCallback, useEffect, useRef, useState } from 'react'
import * as pdfjsLib from 'pdfjs-dist'

// worker 资源两种模式分别处理：
// - 开发模式：用 public/pdf.worker.min.mjs（Vite 对 public 文件零转换——
//   此前走 node_modules 时 Vite 给 worker 注入了 /@vite/client 的 HMR 代码，
//   worker 加载即崩，PDF 永远"正在加载"。这是根因。）
// - 打包模式：用 Vite 打包后的资源（升级 pdfjs-dist 时需同步更新 public 副本）
import prodWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

pdfjsLib.GlobalWorkerOptions.workerSrc = import.meta.env.DEV
  ? new URL('/pdf.worker.min.mjs', window.location.origin).toString()
  : prodWorkerUrl

interface Props {
  bytes: ArrayBuffer
  fileName: string
  targetPage: number
  onPageChange?: (page: number) => void
}

const RENDER_SCALE = 1.3

export default function PdfViewer({
  bytes,
  fileName,
  targetPage,
  onPageChange
}: Props): React.JSX.Element {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [pdf, setPdf] = useState<pdfjsLib.PDFDocumentProxy | null>(null)
  const [loadError, setLoadError] = useState('')
  const [page, setPage] = useState(targetPage)

  useEffect(() => {
    let cancelled = false
    let doc: pdfjsLib.PDFDocumentProxy | null = null
    setLoadError('')
    setPdf(null)
    // 关键：复制一份数据再交给 pdf.js——它会用"转移"方式把缓冲区
    // 交给 worker（原 ArrayBuffer 随即失效）。React 开发模式下组件
    // 会挂载两次，第二次若用原缓冲就会报
    // "DataCloneError: ArrayBuffer is already detached"。
    const data = new Uint8Array(bytes.slice(0))
    pdfjsLib
      .getDocument({ data })
      .promise.then((d) => {
        if (cancelled) {
          d.destroy().catch(() => undefined)
          return
        }
        doc = d
        setPdf(d)
      })
      .catch((e: unknown) => {
        if (!cancelled) setLoadError(`PDF 加载失败：${String(e)}`)
      })
    return () => {
      cancelled = true
      if (doc) doc.destroy().catch(() => undefined)
    }
  }, [bytes])

  useEffect(() => {
    setPage(targetPage)
  }, [targetPage])

  const renderPage = useCallback(async (): Promise<void> => {
    const canvas = canvasRef.current
    if (!pdf || !canvas) return
    const p = await pdf.getPage(Math.min(Math.max(page, 1), pdf.numPages))
    const viewport = p.getViewport({ scale: RENDER_SCALE })
    const dpr = window.devicePixelRatio || 1
    canvas.width = viewport.width * dpr
    canvas.height = viewport.height * dpr
    canvas.style.width = `${viewport.width}px`
    canvas.style.height = `${viewport.height}px`
    await p.render({
      canvasContext: canvas.getContext('2d')!,
      viewport,
      transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : undefined
    }).promise
  }, [pdf, page])

  useEffect(() => {
    renderPage().catch(() => undefined)
  }, [renderPage])

  const goTo = (p: number): void => {
    const clamped = Math.min(Math.max(p, 1), pdf?.numPages ?? 1)
    setPage(clamped)
    onPageChange?.(clamped)
  }

  if (loadError) {
    return <div className="pdf-viewer-loading error-banner">{loadError}</div>
  }
  if (!pdf) {
    return <div className="pdf-viewer-loading">正在加载 {fileName}…</div>
  }

  return (
    <div className="pdf-viewer">
      <div className="pdf-toolbar">
        <button className="btn btn-sm" onClick={() => goTo(page - 1)} disabled={page <= 1}>
          ‹ 上一页
        </button>
        <span className="pdf-page-indicator">
          <input
            type="number"
            min={1}
            max={pdf.numPages}
            value={page}
            onChange={(e) => goTo(Number(e.target.value) || 1)}
          />
          / {pdf.numPages} 页
        </span>
        <button
          className="btn btn-sm"
          onClick={() => goTo(page + 1)}
          disabled={page >= pdf.numPages}
        >
          下一页 ›
        </button>
        <span className="pdf-file-name">{fileName}</span>
      </div>
      <div className="pdf-canvas-wrap">
        <div className="pdf-canvas-box">
          <canvas ref={canvasRef} />
        </div>
      </div>
    </div>
  )
}
