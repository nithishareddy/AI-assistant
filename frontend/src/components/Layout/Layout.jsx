import { useState } from 'react'
import { PanelLeftOpen, PanelLeftClose } from 'lucide-react'
import { Sidebar } from '../Sidebar/Sidebar'
import { ChatWindow } from '../Chat/ChatWindow'
import { ChatInput } from '../Chat/ChatInput'
import { useChat } from '../../hooks/useChat'

export function Layout() {
  const { messages, isStreaming, sources, sendMessage, reset } = useChat()
  const [sidebarOpen, setSidebarOpen] = useState(true)

  return (
    <div className="layout">
      {sidebarOpen && <Sidebar onReset={reset} />}

      <div className="main-area">
        <header className="topbar">
          <button
            className="icon-btn"
            onClick={() => setSidebarOpen((p) => !p)}
            title="Toggle sidebar"
          >
            {sidebarOpen ? <PanelLeftClose size={20} /> : <PanelLeftOpen size={20} />}
          </button>
          <span className="topbar-title">DevOps AI Assistant</span>
          <span className="topbar-subtitle">RAG · GPT-4o · ChromaDB</span>
        </header>

        <ChatWindow messages={messages} isStreaming={isStreaming} sources={sources} />

        <ChatInput onSend={sendMessage} isStreaming={isStreaming} disabled={false} />
      </div>
    </div>
  )
}
