import { Cpu, Trash2, BookOpen, Server } from 'lucide-react'

export function Sidebar({ onReset }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <Cpu size={22} />
        <span className="sidebar-title">DevOps AI</span>
      </div>

      <nav className="sidebar-nav">
        <button className="nav-item active">
          <BookOpen size={16} />
          Chat
        </button>
        <button className="nav-item" onClick={onReset} title="Clear conversation">
          <Trash2 size={16} />
          New Chat
        </button>
        <div className="nav-item disabled">
          <Server size={16} />
          K8s Connect
          <span className="badge">soon</span>
        </div>
      </nav>

      <div className="sidebar-footer">
        <p>RAG-powered by GPT-4o</p>
        <p>Vector DB: ChromaDB</p>
      </div>
    </aside>
  )
}
