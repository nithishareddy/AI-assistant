import json
from app.rag.chunker import chunk_document
from app.rag.embedder import add_chunks, query_similar
from app.config import get_settings

SYSTEM_PROMPT = """You are a senior DevOps engineer and SRE expert assistant.

You have deep expertise in:
- Kubernetes, Helm, Docker
- CI/CD pipelines (GitHub Actions, Jenkins, ArgoCD)
- Log analysis and incident debugging
- Infrastructure as Code (Terraform, Ansible)
- Monitoring (Prometheus, Grafana, Datadog)
- Cloud platforms (AWS, GCP, Azure)

When analyzing issues, always provide:
1. **Root Cause** — What went wrong and why
2. **Evidence** — Specific log lines, config fields, or metrics that confirm it
3. **Fix** — Concrete steps or corrected YAML/config
4. **Prevention** — How to avoid recurrence

Format code blocks with the appropriate language tag (yaml, bash, json, etc.).
Be concise but thorough. If you need more context, ask targeted follow-up questions."""

K8S_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_pods",
            "description": (
                "List all pods in the Kubernetes cluster, optionally filtered by namespace. "
                "Use when the user asks to see pods, check pod status, or find what is running."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {
                        "type": "string",
                        "description": "Namespace to filter by. Leave empty for all namespaces.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "diagnose_pod",
            "description": (
                "Fetch logs, events, and container status for a specific pod. "
                "Use when the user mentions a pod name or asks why a pod is crashing, "
                "failing, restarting, or in CrashLoopBackOff / OOMKilled state."
            ),
            "parameters": {
                "type": "object",
                "required": ["pod_name"],
                "properties": {
                    "pod_name": {
                        "type": "string",
                        "description": "Full pod name, e.g. go-hpa-app-74cb644f7-hrj8h",
                    },
                    "namespace": {
                        "type": "string",
                        "description": "Namespace the pod is in. Leave empty to search all namespaces.",
                    },
                },
            },
        },
    },
]


async def execute_tool_call(name: str, args: dict) -> str:
    from app.services.k8s_service import list_all_pods, format_pods_table, describe_pod_with_logs
    try:
        if name == "list_pods":
            pods = list_all_pods(namespace=args.get("namespace", ""))
            return format_pods_table(pods)
        if name == "diagnose_pod":
            return await describe_pod_with_logs(
                pod_name=args.get("pod_name", ""),
                namespace=args.get("namespace", ""),
            )
        return f"Unknown tool: {name}"
    except Exception as e:
        return f"Tool `{name}` failed: {e}"


async def ingest_document(content: str, source: str, doc_type: str, metadata: dict) -> int:
    chunks = chunk_document(content, source, doc_type, metadata)
    return await add_chunks(chunks)


async def retrieve_context(query: str) -> list[dict]:
    settings = get_settings()
    return await query_similar(query, top_k=settings.retrieval_top_k)


def build_context_block(chunks: list[dict]) -> str:
    if not chunks:
        return ""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        header = f"[{i}] Source: {chunk['source']} (type={chunk['doc_type']}, relevance={chunk['score']})"
        parts.append(f"{header}\n{chunk['content']}")
    return "\n\n---\n\n".join(parts)


def build_attachment_block(attachments: list[dict]) -> str:
    """Build a context block from user-attached files (name + content)."""
    if not attachments:
        return ""
    parts = []
    for att in attachments:
        name = att.get("name", "attachment")
        content = att.get("content", "").strip()
        if content:
            parts.append(f"### Attached file: {name}\n\n```\n{content}\n```")
    return "\n\n".join(parts)


def build_messages_with_context(
    messages: list[dict],
    context_chunks: list[dict],
    live_context: tuple[str, str] | None = None,
    attachments: list[dict] | None = None,
) -> list[dict]:
    system_content = SYSTEM_PROMPT

    # Live K8s data goes first — it's real-time and highest priority
    if live_context and live_context[1]:
        label, data = live_context
        system_content += f"\n\n## {label}\n\n{data}"

    if context_chunks:
        context_block = build_context_block(context_chunks)
        system_content += f"\n\n## Relevant Context from Knowledge Base\n\n{context_block}"

    if attachments:
        att_block = build_attachment_block(attachments)
        if att_block:
            system_content += f"\n\n## Files Attached by User (use as primary reference)\n\n{att_block}"

    result = [{"role": "system", "content": system_content}]
    result.extend(messages)
    return result
