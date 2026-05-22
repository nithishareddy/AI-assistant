const BASE = '/api'

export async function* streamChat(messages, sessionId, attachments = []) {
  const response = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      messages,
      session_id: sessionId,
      stream: true,
      attachments,
    }),
  })

  if (!response.ok) {
    const err = await response.text()
    throw new Error(`Chat error ${response.status}: ${err}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const lines = buffer.split('\n')
    buffer = lines.pop() // incomplete line stays in buffer

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const payload = JSON.parse(line.slice(6))
          yield payload
        } catch {
          // skip malformed
        }
      }
    }
  }
}

export async function ingestText(content, source, docType = 'doc') {
  const response = await fetch(`${BASE}/ingest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, source, doc_type: docType }),
  })
  if (!response.ok) throw new Error(`Ingest error: ${response.status}`)
  return response.json()
}

export async function ingestFile(file, docType) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('doc_type', docType || 'doc')
  const response = await fetch(`${BASE}/ingest/file`, {
    method: 'POST',
    body: formData,
  })
  if (!response.ok) throw new Error(`File ingest error: ${response.status}`)
  return response.json()
}

export async function clearSession(sessionId) {
  await fetch(`${BASE}/chat/${sessionId}`, { method: 'DELETE' })
}

export async function fetchK8sLogs(namespace, podName, container = '', tailLines = 100) {
  const response = await fetch(`${BASE}/k8s/logs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ namespace, pod_name: podName, container, tail_lines: tailLines }),
  })
  if (!response.ok) throw new Error(`K8s logs error: ${response.status}`)
  return response.json()
}
