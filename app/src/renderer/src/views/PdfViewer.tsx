import { useCallback, useEffect, useRef, useState } from 'react'
import * as pdfjsLib from 'pdfjs-dist'

// Vite 打包 worker 资源；版本需与 pdfjs-dist 匹配
pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url
).toString()

interface Props {
  bytes: ArrayBuffer
  fileName: string
  targetPage: number
  /** 页内高亮区域（PDF 坐标系 "x0,y0,x1,y1"），来自提取时的出处四元组 */
  bbox?: string | null
  onPageChange?: (page: number) => void
}

const RENDER_SCALE = 1.3

export default function PdfViewer({
  bytes,
  fileName,
  targetPage,
  bbox,
  onPageChange
}: Props): React.JSX.Element {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [pdf, setPdf] = useState<pdfjsLib.PDFDocumentProxy | null>(null)
  const [page, setPage] = useState(targetPage)
  const [highlightRect, setHighlightRect] = useState<{
    left: number
    top: number
    width: number
    height: number
  } | null>(null)

  useEffect(() => {
    let cancelled = false
    pdfjsLib
      .getDocument({ data: new Uint8Array(bytes) })
      .promise.then((doc) => {
        if (!cancelled) setPdf(doc)
      })
      .catch(() => {
        if (!cancelled) setPdf(null)
      })
    return () => {
      cancelled = true
      setPdf((old) => {
        old?.destroy().catch(() => undefined)
        return null
      })
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
    // 高亮区域：PDF 坐标 → 画布 CSS 坐标
    if (bbox) {
      const parts = bbox.split(',').map(Number)
      if (parts.length === 4 && parts.every((v) => Number.isFinite(v))) {
        const [x0, y0, x1, y1] = parts
        const [vx0, vy0] = viewport.convertToViewportPoint(x0, y0)
        const [vx1, vy1] = viewport.convertToViewportPoint(x1, y1)
        setHighlightRect({
          left: Math.min(vx0, vx1),
          top: Math.min(vy0, vy1),
          width: Math.abs(vx1 - vx0),
          height: Math.abs(vy1 - vy0)
        })
        return
      }
    }
    setHighlightRect(null)
  }, [pdf, page, bbox])

  useEffect(() => {
    renderPage().catch(() => undefined)
  }, [renderPage])

  const goTo = (p: number): void => {
    const clamped = Math.min(Math.max(p, 1), pdf?.numPages ?? 1)
    setPage(clamped)
    onPageChange?.(clamped)
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
          {highlightRect && <div className="pdf-highlight" style={highlightRect} />}
        </div>
      </div>
    </div>
  )
}
