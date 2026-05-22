import { useState, useCallback, useRef } from 'react'
import { v4 as uuidv4 } from 'uuid'
import { streamChat, clearSession } from '../services/api'

export function useChat() {
  const [messages, setMessages] = useState([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [sources, setSources] = useState([])
  const sessionId = useRef(uuidv4())
  const abortRef = useRef(false)

  const sendMessage = useCallback(async (userText, attachments = []) => {
    if (!userText.trim() || isStreaming) return

    const userMsg = { role: 'user', content: userText, id: uuidv4() }
    const assistantId = uuidv4()

    setMessages((prev) => [
      ...prev,
      userMsg,
      { role: 'assistant', content: '', id: assistantId, streaming: true },
    ])
    setSources([])
    setIsStreaming(true)
    abortRef.current = false

    try {
      const history = [...messages, userMsg].map((m) => ({
        role: m.role,
        content: m.content,
      }))

      for await (const payload of streamChat(history, sessionId.current, attachments)) {
        if (abortRef.current) break

        if (payload.type === 'sources') {
          setSources(payload.sources)
        } else if (payload.type === 'token') {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: m.content + payload.content }
                : m
            )
          )
        } else if (payload.type === 'done') {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, streaming: false } : m
            )
          )
        }
      }
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content: `Error: ${err.message}`,
                streaming: false,
                error: true,
              }
            : m
        )
      )
    } finally {
      setIsStreaming(false)
    }
  }, [messages, isStreaming])

  const reset = useCallback(async () => {
    abortRef.current = true
    await clearSession(sessionId.current)
    sessionId.current = uuidv4()
    setMessages([])
    setSources([])
    setIsStreaming(false)
  }, [])

  return { messages, isStreaming, sources, sendMessage, reset }
}
