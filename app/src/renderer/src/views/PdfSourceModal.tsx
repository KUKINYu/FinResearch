import { useEffect, useState } from 'react'
import PdfViewer from './PdfViewer'

interface Props {
  fileId: number
  fileName: string
  page: number
  onClose: () => void
}

/** 原文核对弹窗：加载文件内容并跳转到指定页。 */
export default function PdfSourceModal({
  fileId,
  fileName,
  page,
  onClose
}: Props): React.JSX.Element {
  const [bytes, setBytes] = useState<ArrayBuffer | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    window.finengine
      .getFileContent(fileId)
      .then((b) => {
        if (!cancelled) setBytes(b)
      })
      .catch((e) => {
        if (!cancelled) setError(String(e))
      })
    return () => {
      cancelled = true
    }
  }, [fileId])

  return (
    <div className="viewer-overlay" onClick={onClose}>
      <div className="viewer-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="viewer-close-row">
          <span className="viewer-title">原文核对</span>
          <button className="btn btn-sm" onClick={onClose}>
            关闭
          </button>
        </div>
        {error && <div className="error-banner">{error}</div>}
        {bytes && <PdfViewer bytes={bytes} fileName={fileName} targetPage={page} />}
      </div>
    </div>
  )
}
