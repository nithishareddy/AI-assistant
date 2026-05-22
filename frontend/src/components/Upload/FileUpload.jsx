import { useState, useRef } from 'react'
import { Upload, CheckCircle, AlertCircle, Loader } from 'lucide-react'
import { ingestFile, ingestText } from '../../services/api'

const DOC_TYPES = [
  { value: 'log', label: 'Log file' },
  { value: 'yaml', label: 'YAML / Helm' },
  { value: 'runbook', label: 'Runbook' },
  { value: 'doc', label: 'Documentation' },
]

export function FileUpload() {
  const [docType, setDocType] = useState('doc')
  const [status, setStatus] = useState(null) // null | 'loading' | 'ok' | 'error'
  const [message, setMessage] = useState('')
  const [pasteText, setPasteText] = useState('')
  const [pasteSource, setPasteSource] = useState('')
  const [dragging, setDragging] = useState(false)
  const fileRef = useRef(null)

  const handleFile = async (file) => {
    setStatus('loading')
    setMessage('')
    try {
      const result = await ingestFile(file, docType)
      setStatus('ok')
      setMessage(`Ingested ${result.chunks_added} chunks from "${result.source}"`)
    } catch (e) {
      setStatus('error')
      setMessage(e.message)
    }
  }

  const handlePaste = async () => {
    if (!pasteText.trim()) return
    setStatus('loading')
    setMessage('')
    try {
      const source = pasteSource.trim() || `paste-${Date.now()}`
      const result = await ingestText(pasteText, source, docType)
      setStatus('ok')
      setMessage(`Ingested ${result.chunks_added} chunks from "${result.source}"`)
      setPasteText('')
      setPasteSource('')
    } catch (e) {
      setStatus('error')
      setMessage(e.message)
    }
  }

  return (
    <div className="file-upload">
      <h3 className="section-title">Add to Knowledge Base</h3>

      <div className="doc-type-selector">
        {DOC_TYPES.map((dt) => (
          <button
            key={dt.value}
            className={`type-btn ${docType === dt.value ? 'active' : ''}`}
            onClick={() => setDocType(dt.value)}
          >
            {dt.label}
          </button>
        ))}
      </div>

      {/* File drop zone */}
      <div
        className={`drop-zone ${dragging ? 'dragging' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          const file = e.dataTransfer.files[0]
          if (file) handleFile(file)
        }}
        onClick={() => fileRef.current?.click()}
      >
        <Upload size={24} />
        <p>Drop file here or click to browse</p>
        <input
          ref={fileRef}
          type="file"
          hidden
          accept=".log,.yaml,.yml,.md,.txt,.json"
          onChange={(e) => e.target.files[0] && handleFile(e.target.files[0])}
        />
      </div>

      {/* Paste zone */}
      <div className="paste-zone">
        <input
          className="paste-source"
          placeholder="Source name (e.g. my-pod-logs)"
          value={pasteSource}
          onChange={(e) => setPasteSource(e.target.value)}
        />
        <textarea
          className="paste-textarea"
          placeholder="Paste logs, YAML, or docs here..."
          rows={6}
          value={pasteText}
          onChange={(e) => setPasteText(e.target.value)}
        />
        <button
          className="ingest-btn"
          onClick={handlePaste}
          disabled={!pasteText.trim() || status === 'loading'}
        >
          {status === 'loading' ? <Loader size={14} className="spin" /> : null}
          Ingest Text
        </button>
      </div>

      {status && (
        <div className={`ingest-status ${status}`}>
          {status === 'ok' && <CheckCircle size={14} />}
          {status === 'error' && <AlertCircle size={14} />}
          {status === 'loading' && <Loader size={14} className="spin" />}
          <span>{message || 'Processing...'}</span>
        </div>
      )}
    </div>
  )
}
