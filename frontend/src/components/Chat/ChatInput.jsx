import { useState, useRef, useEffect } from 'react'
import { Send, Square, Paperclip, X } from 'lucide-react'

const QUICK_PROMPTS = [
  'Why is my pod crashing?',
  'Explain this Helm chart',
  'Analyze these logs for errors',
  'What caused this deployment failure?',
  'How do I fix OOMKilled?',
  'Show me how to set resource limits',
]

const MAX_FILE_CHARS = 12000

export function ChatInput({ onSend, isStreaming, disabled }) {
  const [text, setText] = useState('')
  const [attachments, setAttachments] = useState([]) // [{name, content}]
  const textareaRef = useRef(null)
  const fileInputRef = useRef(null)

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`
    }
  }, [text])

  const handleSubmit = () => {
    const trimmed = text.trim()
    if (!trimmed || isStreaming) return
    onSend(trimmed, attachments)
    setText('')
    setAttachments([])
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const handleFileChange = (e) => {
    const files = Array.from(e.target.files || [])
    files.forEach((file) => {
      const reader = new FileReader()
      reader.onload = (ev) => {
        const content = (ev.target.result || '').slice(0, MAX_FILE_CHARS)
        setAttachments((prev) => {
          // avoid duplicates by name
          if (prev.find((a) => a.name === file.name)) return prev
          return [...prev, { name: file.name, content }]
        })
      }
      reader.readAsText(file)
    })
    // reset so the same file can be re-attached after removal
    e.target.value = ''
  }

  const removeAttachment = (name) => {
    setAttachments((prev) => prev.filter((a) => a.name !== name))
  }

  return (
    <div className="chat-input-wrapper">
      <div className="quick-prompts">
        {QUICK_PROMPTS.map((p) => (
          <button
            key={p}
            className="quick-prompt-btn"
            onClick={() => onSend(p, [])}
            disabled={isStreaming}
          >
            {p}
          </button>
        ))}
      </div>

      {attachments.length > 0 && (
        <div className="attachment-chips">
          {attachments.map((att) => (
            <span key={att.name} className="attachment-chip">
              <Paperclip size={11} />
              {att.name}
              <button
                className="attachment-remove"
                onClick={() => removeAttachment(att.name)}
                title="Remove attachment"
              >
                <X size={11} />
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="input-row">
        <button
          className="attach-btn"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled || isStreaming}
          title="Attach YAML or log file as reference"
        >
          <Paperclip size={17} />
        </button>
        <input
          ref={fileInputRef}
          type="file"
          hidden
          multiple
          accept=".yaml,.yml,.log,.txt,.json,.conf,.properties"
          onChange={handleFileChange}
        />

        <textarea
          ref={textareaRef}
          className="chat-textarea"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about logs, YAML configs, K8s issues… (Shift+Enter for newline)"
          rows={1}
          disabled={disabled}
        />
        <button
          className={`send-btn ${isStreaming ? 'stop-btn' : ''}`}
          onClick={handleSubmit}
          disabled={disabled || (!text.trim() && !isStreaming)}
          title={isStreaming ? 'Streaming…' : 'Send message'}
        >
          {isStreaming ? <Square size={18} /> : <Send size={18} />}
        </button>
      </div>
      <p className="input-hint">
        Enter to send · Shift+Enter for newline · Use <Paperclip size={11} style={{display:'inline',verticalAlign:'middle'}} /> to attach YAML or log files
      </p>
    </div>
  )
}
