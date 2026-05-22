import re
import json
import yaml
from dataclasses import dataclass
from app.config import get_settings


@dataclass
class Chunk:
    content: str
    source: str
    doc_type: str
    chunk_index: int
    metadata: dict


def chunk_yaml(content: str, source: str, metadata: dict) -> list[Chunk]:
    """Split YAML into per-resource chunks."""
    resources = re.split(r"\n---\n", content.strip())
    chunks = []
    for i, resource in enumerate(resources):
        resource = resource.strip()
        if resource:
            chunks.append(
                Chunk(
                    content=resource,
                    source=source,
                    doc_type="yaml",
                    chunk_index=i,
                    metadata={**metadata, "resource_index": i},
                )
            )
    return chunks if chunks else [Chunk(content=content, source=source, doc_type="yaml", chunk_index=0, metadata=metadata)]


def chunk_logs(content: str, source: str, metadata: dict) -> list[Chunk]:
    """Split logs into time-window chunks (every N lines)."""
    settings = get_settings()
    lines = content.strip().splitlines()
    window_size = 50  # lines per chunk
    overlap = 10

    chunks = []
    start = 0
    chunk_index = 0
    while start < len(lines):
        end = min(start + window_size, len(lines))
        window = "\n".join(lines[start:end])
        chunks.append(
            Chunk(
                content=window,
                source=source,
                doc_type="log",
                chunk_index=chunk_index,
                metadata={**metadata, "line_start": start, "line_end": end},
            )
        )
        chunk_index += 1
        start += window_size - overlap

    return chunks


def chunk_text(content: str, source: str, doc_type: str, metadata: dict) -> list[Chunk]:
    """Split generic text by paragraphs, respecting chunk_size."""
    settings = get_settings()
    chunk_size = settings.chunk_size
    overlap = settings.chunk_overlap

    paragraphs = re.split(r"\n{2,}", content.strip())
    chunks: list[Chunk] = []
    current = ""
    chunk_index = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) + 1 <= chunk_size:
            current = f"{current}\n\n{para}".strip()
        else:
            if current:
                chunks.append(
                    Chunk(
                        content=current,
                        source=source,
                        doc_type=doc_type,
                        chunk_index=chunk_index,
                        metadata=metadata,
                    )
                )
                chunk_index += 1
                # carry overlap: last N chars
                current = current[-overlap:] + "\n\n" + para if overlap else para
            else:
                current = para

    if current.strip():
        chunks.append(
            Chunk(
                content=current.strip(),
                source=source,
                doc_type=doc_type,
                chunk_index=chunk_index,
                metadata=metadata,
            )
        )

    return chunks


def chunk_swagger(content: str, source: str, metadata: dict) -> list[Chunk]:
    """Split OpenAPI/Swagger spec into per-endpoint chunks."""
    try:
        spec = json.loads(content)
    except json.JSONDecodeError:
        try:
            spec = yaml.safe_load(content)
        except Exception:
            return chunk_text(content, source, "swagger", metadata)

    if not isinstance(spec, dict):
        return chunk_text(content, source, "swagger", metadata)

    info = spec.get("info", {})
    api_title = info.get("title", "API")
    api_version = info.get("version", "")
    base_url = ""
    servers = spec.get("servers", [])
    if servers:
        base_url = servers[0].get("url", "")

    paths = spec.get("paths", {})
    chunks = []
    chunk_index = 0

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete", "options", "head"):
            operation = path_item.get(method)
            if not operation:
                continue

            summary = operation.get("summary", "")
            description = operation.get("description", "")
            tags = operation.get("tags", [])
            parameters = operation.get("parameters", [])
            request_body = operation.get("requestBody", {})
            responses = operation.get("responses", {})

            # Build a human-readable text block per endpoint
            lines = [
                f"API: {api_title} {api_version}",
                f"Endpoint: {method.upper()} {base_url}{path}",
            ]
            if tags:
                lines.append(f"Tags: {', '.join(tags)}")
            if summary:
                lines.append(f"Summary: {summary}")
            if description:
                lines.append(f"Description: {description}")

            if parameters:
                lines.append("Parameters:")
                for p in parameters:
                    name = p.get("name", "")
                    location = p.get("in", "")
                    required = p.get("required", False)
                    p_desc = p.get("description", "")
                    schema = p.get("schema", {})
                    p_type = schema.get("type", "")
                    lines.append(f"  - {name} ({location}, {'required' if required else 'optional'}, type={p_type}): {p_desc}")

            if request_body:
                rb_desc = request_body.get("description", "")
                rb_required = request_body.get("required", False)
                lines.append(f"Request Body: {'required' if rb_required else 'optional'} — {rb_desc}")

            if responses:
                lines.append("Responses:")
                for status, resp in responses.items():
                    resp_desc = resp.get("description", "") if isinstance(resp, dict) else ""
                    lines.append(f"  {status}: {resp_desc}")

            chunk_text_content = "\n".join(lines)
            chunks.append(
                Chunk(
                    content=chunk_text_content,
                    source=source,
                    doc_type="swagger",
                    chunk_index=chunk_index,
                    metadata={
                        **metadata,
                        "path": path,
                        "method": method.upper(),
                        "api_title": api_title,
                        "tags": ", ".join(tags),
                    },
                )
            )
            chunk_index += 1

    return chunks if chunks else chunk_text(content, source, "swagger", metadata)


def chunk_document(content: str, source: str, doc_type: str, metadata: dict) -> list[Chunk]:
    if doc_type == "yaml":
        return chunk_yaml(content, source, metadata)
    elif doc_type == "log":
        return chunk_logs(content, source, metadata)
    elif doc_type == "swagger":
        return chunk_swagger(content, source, metadata)
    else:
        return chunk_text(content, source, doc_type, metadata)
