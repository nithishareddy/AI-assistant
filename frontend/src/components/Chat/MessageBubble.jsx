import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

function CodeBlock({ inline, className, children, ...props }) {
  const match = /language-(\w+)/.exec(className || '')
  if (!inline && match) {
    return (
      <SyntaxHighlighter
        style={oneDark}
        language={match[1]}
        PreTag="div"
        customStyle={{ borderRadius: '8px', fontSize: '13px', margin: '8px 0' }}
        {...props}
      >
        {String(children).replace(/\n$/, '')}
      </SyntaxHighlighter>
    )
  }
  return (
    <code
      className="inline-code"
      {...props}
    >
      {children}
    </code>
  )
}

export function MessageBubble({ message }) {
  const isUser = message.role === 'user'

  return (
    <div className={`message-row ${isUser ? 'user-row' : 'assistant-row'}`}>
      <div className={`avatar ${isUser ? 'user-avatar' : 'assistant-avatar'}`}>
        {isUser ? 'U' : 'AI'}
      </div>
      <div className={`bubble ${isUser ? 'user-bubble' : 'assistant-bubble'} ${message.error ? 'error-bubble' : ''}`}>
        {isUser ? (
          <p className="user-text">{message.content}</p>
        ) : (
          <div className="markdown-body">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{ code: CodeBlock }}
            >
              {message.content || (message.streaming ? '' : '...')}
            </ReactMarkdown>
            {message.streaming && (
              <span className="cursor-blink">|</span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
