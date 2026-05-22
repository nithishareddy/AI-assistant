import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.models.schemas import ChatRequest
from app.rag.pipeline import (
    retrieve_context,
    build_messages_with_context,
    detect_k8s_intent,
    fetch_live_k8s_context,
)
from app.services.llm_service import chat_completion, chat_completion_stream

router = APIRouter(prefix="/chat", tags=["chat"])

# Simple in-memory session store (replace with Redis for production)
_sessions: dict[str, list[dict]] = {}


@router.post("")
async def chat(request: ChatRequest):
    session_id = request.session_id

    if session_id not in _sessions:
        _sessions[session_id] = []

    history = _sessions[session_id]
    new_message = request.messages[-1]
    history.append({"role": new_message.role.value, "content": new_message.content})

    user_query = new_message.content

    # 1. Detect if query needs live K8s data
    intent = detect_k8s_intent(user_query)
    live_context = None
    live_source_event = None

    if intent:
        label, data = await fetch_live_k8s_context(intent)
        live_context = (label, data)
        live_source_event = json.dumps({
            "type": "sources",
            "sources": [{
                "source": "minikube-cluster (live)",
                "doc_type": "k8s-live",
                "score": 1.0,
                "preview": data[:120] if data else "",
            }],
        })

    # 2. RAG retrieval from vector store
    context_chunks = await retrieve_context(user_query)

    # 3. Build prompt with live data + RAG context + inline attachments
    raw_attachments = [{"name": a.name, "content": a.content} for a in request.attachments]
    messages_with_ctx = build_messages_with_context(history, context_chunks, live_context, raw_attachments)

    if request.stream:
        async def event_stream():
            full_response = ""

            # Emit live K8s source badge first
            if live_source_event:
                yield f"data: {live_source_event}\n\n"

            # Emit RAG sources
            if context_chunks and not live_source_event:
                sources_payload = json.dumps({
                    "type": "sources",
                    "sources": [
                        {
                            "source": c["source"],
                            "doc_type": c["doc_type"],
                            "score": c["score"],
                            "preview": c["content"][:120],
                        }
                        for c in context_chunks
                    ],
                })
                yield f"data: {sources_payload}\n\n"

            async for token in chat_completion_stream(messages_with_ctx):
                full_response += token
                payload = json.dumps({"type": "token", "content": token})
                yield f"data: {payload}\n\n"

            history.append({"role": "assistant", "content": full_response})
            _sessions[session_id] = history[-40:]

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")
    else:
        response_text = await chat_completion(messages_with_ctx)
        history.append({"role": "assistant", "content": response_text})
        _sessions[session_id] = history[-40:]
        return {
            "response": response_text,
            "sources": context_chunks,
            "live_k8s": bool(live_context),
        }


@router.delete("/{session_id}")
async def clear_session(session_id: str):
    _sessions.pop(session_id, None)
    return {"cleared": True}
