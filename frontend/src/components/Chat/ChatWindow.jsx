import { useEffect, useRef } from 'react'
import { MessageBubble } from './MessageBubble'
import { Bot } from 'lucide-react'

const WELCOME = `## Welcome to DevOps AI Assistant

I can help you with:

- **Log Analysis** — Paste your pod/container logs and I'll find the root cause
- **YAML Explanation** — Drop any Kubernetes or Helm YAML for a detailed breakdown
- **Incident Debugging** — Describe your issue and I'll guide you step-by-step
- **Fix Suggestions** — Get corrected configs with explanations

Upload files via the sidebar or just start chatting.`

export function ChatWindow({ messages, isStreaming, sources }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="chat-window">
      {messages.length === 0 ? (
        <div className="welcome-screen">
          <div className="welcome-icon">
            <Bot size={48} />
          </div>
          <div className="welcome-markdown">
            <h2>DevOps AI Assistant</h2>
            <p>Powered by GPT-4o + RAG — your intelligent SRE companion</p>
            <ul>
              <li>Log Analysis — Paste pod/container logs for root cause</li>
              <li>YAML Explanation — Break down any K8s or Helm YAML</li>
              <li>Incident Debugging — Step-by-step guided debugging</li>
              <li>Fix Suggestions — Get corrected configs with explanations</li>
            </ul>
            <p className="welcome-hint">Upload files via the sidebar or start chatting below.</p>
          </div>
        </div>
      ) : (
        <div className="messages-list">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
        </div>
      )}

      {sources.length > 0 && (
        <div className="sources-bar">
          <span className="sources-label">Sources used:</span>
          {sources.map((s, i) => (
            <span key={i} className={`source-chip doc-type-${s.doc_type}`} title={s.preview}>
              {s.source.split('/').pop()} ({Math.round(s.score * 100)}%)
            </span>
          ))}
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  )
}
