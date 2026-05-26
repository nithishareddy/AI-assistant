import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.models.schemas import ChatRequest
from app.rag.pipeline import (
    retrieve_context,
    build_messages_with_context,
    K8S_TOOLS,
    execute_tool_call,
)
from app.services.llm_service import (
    chat_completion,
    chat_completion_stream,
    chat_completion_with_tools,
)

router = APIRouter(prefix="/chat", tags=["chat"])

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
    raw_attachments = [{"name": a.name, "content": a.content} for a in request.attachments]

    # RAG retrieval
    context_chunks = await retrieve_context(user_query)

    # Build messages with RAG context (no live K8s injected — tools handle that now)
    messages = build_messages_with_context(history, context_chunks, None, raw_attachments)

    if request.stream:
        async def event_stream():
            full_response = ""

            # Phase 1: ask LLM with tools — it decides what (if anything) to fetch
            response_msg = await chat_completion_with_tools(messages, K8S_TOOLS)

            if response_msg.tool_calls:
                # Emit a source badge for each tool invoked
                tool_sources = [
                    {
                        "source": f"live-k8s:{tc.function.name}({tc.function.arguments})",
                        "doc_type": "k8s-live",
                        "score": 1.0,
                        "preview": "",
                    }
                    for tc in response_msg.tool_calls
                ]
                yield f"data: {json.dumps({'type': 'sources', 'sources': tool_sources})}\n\n"

                # Execute every tool call
                tool_result_messages = []
                for tc in response_msg.tool_calls:
                    args = json.loads(tc.function.arguments)
                    result = await execute_tool_call(tc.function.name, args)

                    # Update source preview with actual result snippet
                    for s in tool_sources:
                        if tc.function.name in s["source"]:
                            s["preview"] = result[:120]

                    tool_result_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })

                # Build the follow-up message list:
                # original messages + assistant's tool-call turn + tool results
                assistant_turn = {
                    "role": "assistant",
                    "content": response_msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in response_msg.tool_calls
                    ],
                }
                followup_messages = messages + [assistant_turn] + tool_result_messages

                # Phase 2: stream the final answer with tool results in context
                async for token in chat_completion_stream(followup_messages):
                    full_response += token
                    yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

            else:
                # No tools needed — emit RAG sources and stream response directly
                if context_chunks:
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

                # Phase 1 already has the answer; stream it via a second call
                async for token in chat_completion_stream(messages):
                    full_response += token
                    yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

            history.append({"role": "assistant", "content": full_response})
            _sessions[session_id] = history[-40:]

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    else:
        response_msg = await chat_completion_with_tools(messages, K8S_TOOLS)

        if response_msg.tool_calls:
            tool_result_messages = []
            for tc in response_msg.tool_calls:
                args = json.loads(tc.function.arguments)
                result = await execute_tool_call(tc.function.name, args)
                tool_result_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
            assistant_turn = {
                "role": "assistant",
                "content": response_msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in response_msg.tool_calls
                ],
            }
            followup_messages = messages + [assistant_turn] + tool_result_messages
            response_text = await chat_completion(followup_messages)
        else:
            response_text = response_msg.content or ""

        history.append({"role": "assistant", "content": response_text})
        _sessions[session_id] = history[-40:]
        return {
            "response": response_text,
            "sources": context_chunks,
            "live_k8s": bool(response_msg.tool_calls),
        }


@router.delete("/{session_id}")
async def clear_session(session_id: str):
    _sessions.pop(session_id, None)
    return {"cleared": True}
