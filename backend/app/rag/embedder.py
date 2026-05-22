import chromadb
from openai import AsyncOpenAI
from app.config import get_settings
from app.rag.chunker import Chunk
import hashlib
import os

_client = None
_collection = None
_openai: AsyncOpenAI | None = None


def _get_openai() -> AsyncOpenAI:
    global _openai
    if _openai is None:
        settings = get_settings()
        _openai = AsyncOpenAI(api_key=settings.openai_api_key)
    return _openai


def _get_collection():
    global _client, _collection
    if _collection is None:
        settings = get_settings()
        _client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
        )
        _collection = _client.get_or_create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


async def embed_texts(texts: list[str]) -> list[list[float]]:
    settings = get_settings()
    client = _get_openai()
    response = await client.embeddings.create(
        model=settings.openai_embedding_model,
        input=texts,
    )
    return [item.embedding for item in response.data]


def _chunk_id(chunk: Chunk) -> str:
    raw = f"{chunk.source}::{chunk.chunk_index}::{chunk.content[:64]}"
    return hashlib.md5(raw.encode()).hexdigest()


async def add_chunks(chunks: list[Chunk]) -> int:
    if not chunks:
        return 0

    collection = _get_collection()
    texts = [c.content for c in chunks]
    embeddings = await embed_texts(texts)

    ids = [_chunk_id(c) for c in chunks]
    metadatas = [
        {
            "source": c.source,
            "doc_type": c.doc_type,
            "chunk_index": c.chunk_index,
            **{k: str(v) for k, v in c.metadata.items()},
        }
        for c in chunks
    ]

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas,
    )
    return len(chunks)


def delete_by_source(source: str) -> int:
    """Delete all chunks whose metadata source equals the given value. Returns count deleted."""
    collection = _get_collection()
    results = collection.get(where={"source": source}, include=["metadatas"])
    ids = results.get("ids", [])
    if ids:
        collection.delete(ids=ids)
    return len(ids)


def list_sources() -> list[dict]:
    """Return all unique sources with chunk count and doc_type."""
    collection = _get_collection()
    results = collection.get(include=["metadatas"], limit=10000)
    sources: dict[str, dict] = {}
    for meta in results.get("metadatas", []):
        src = meta.get("source", "unknown")
        dt  = meta.get("doc_type", "doc")
        if src not in sources:
            sources[src] = {"source": src, "doc_type": dt, "chunks": 0}
        sources[src]["chunks"] += 1
    return sorted(sources.values(), key=lambda x: x["chunks"], reverse=True)


async def query_similar(query: str, top_k: int = 5) -> list[dict]:
    collection = _get_collection()
    embeddings = await embed_texts([query])

    results = collection.query(
        query_embeddings=embeddings,
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for doc, meta, dist in zip(docs, metas, distances):
        hits.append(
            {
                "content": doc,
                "source": meta.get("source", ""),
                "doc_type": meta.get("doc_type", ""),
                "score": round(1 - dist, 4),
            }
        )
    return hits
