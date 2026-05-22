"""
Kafka consumer — reads 'help-center-docs' messages and writes them to ChromaDB.

Run: python kafka_consumer.py

Each message is chunked (paragraph-based, ~800 chars), embedded via OpenAI,
and upserted into the 'devops_knowledge' ChromaDB collection so the RAG
pipeline can retrieve help center docs answers.
"""

import json
import logging
import os
import time
import uuid
from textwrap import wrap

import chromadb
from dotenv import load_dotenv
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable
from openai import OpenAI

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../backend/.env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────────────
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
KAFKA_TOPIC = "help-center-docs"
KAFKA_GROUP = "help-center-consumer"

CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8001"))
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "devops_knowledge")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))
BATCH_SIZE = 50  # embed + upsert this many chunks at once


# ── Chunker ──────────────────────────────────────────────────────────────────
def chunk_text(text: str, source: str) -> list[dict]:
    """Split text into overlapping ~CHUNK_SIZE character chunks."""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks: list[dict] = []
    current = ""
    idx = 0

    for para in paragraphs:
        if len(current) + len(para) + 1 <= CHUNK_SIZE:
            current = (current + "\n" + para).strip()
        else:
            if current:
                chunks.append({
                    "id": f"{source}__chunk{idx}",
                    "content": current,
                    "source": source,
                    "doc_type": "doc",
                    "chunk_index": idx,
                })
                idx += 1
                # overlap: carry last CHUNK_OVERLAP chars into next chunk
                current = current[-CHUNK_OVERLAP:] + "\n" + para
            else:
                # single paragraph too large — hard split
                for part in wrap(para, CHUNK_SIZE):
                    chunks.append({
                        "id": f"{source}__chunk{idx}",
                        "content": part,
                        "source": source,
                        "doc_type": "doc",
                        "chunk_index": idx,
                    })
                    idx += 1
                current = ""

    if current:
        chunks.append({
            "id": f"{source}__chunk{idx}",
            "content": current,
            "source": source,
            "doc_type": "doc",
            "chunk_index": idx,
        })

    return chunks


# ── Embedder ────────────────────────────────────────────────────────────────
def embed_texts(openai_client: OpenAI, texts: list[str]) -> list[list[float]]:
    """Return embedding vectors for a list of texts."""
    response = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


# ── ChromaDB ─────────────────────────────────────────────────────────────────
def get_collection(chroma_client: chromadb.HttpClient):
    return chroma_client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


def upsert_chunks(collection, openai_client: OpenAI, chunks: list[dict]) -> int:
    """Embed and upsert chunks in batches. Returns count added."""
    total = 0
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        texts = [c["content"] for c in batch]
        embeddings = embed_texts(openai_client, texts)
        collection.upsert(
            ids=[c["id"] for c in batch],
            embeddings=embeddings,
            documents=texts,
            metadatas=[
                {
                    "source": c["source"],
                    "doc_type": c["doc_type"],
                    "chunk_index": c["chunk_index"],
                }
                for c in batch
            ],
        )
        total += len(batch)
    return total


# ── Client factories ─────────────────────────────────────────────────────────
def make_consumer() -> KafkaConsumer:
    while True:
        try:
            consumer = KafkaConsumer(
                KAFKA_TOPIC,
                bootstrap_servers=KAFKA_BROKER,
                group_id=KAFKA_GROUP,
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                value_deserializer=lambda b: json.loads(b.decode("utf-8")),
            )
            log.info("Connected to Kafka, topic=%s group=%s", KAFKA_TOPIC, KAFKA_GROUP)
            return consumer
        except NoBrokersAvailable:
            log.warning("Kafka not available, retrying in 5s…")
            time.sleep(5)


def make_chroma() -> chromadb.HttpClient:
    while True:
        try:
            client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
            client.heartbeat()
            log.info("Connected to ChromaDB at %s:%d", CHROMA_HOST, CHROMA_PORT)
            return client
        except Exception as exc:
            log.warning("ChromaDB not ready (%s), retrying in 5s…", exc)
            time.sleep(5)


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set — check backend/.env")

    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    chroma_client = make_chroma()
    collection = get_collection(chroma_client)
    consumer = make_consumer()

    log.info("Listening for messages on topic '%s'…", KAFKA_TOPIC)

    for message in consumer:
        doc = message.value
        url: str = doc.get("url", "unknown")
        title: str = doc.get("title", url)
        content: str = doc.get("content", "")

        if not content.strip():
            log.debug("Empty content for %s, skipping", url)
            continue

        source_label = title if title and title != url else url
        chunks = chunk_text(content, source=source_label)

        if not chunks:
            continue

        try:
            added = upsert_chunks(collection, openai_client, chunks)
            log.info(
                "Stored %d chunk(s) from '%s' (offset=%d)",
                added, source_label, message.offset,
            )
        except Exception as exc:
            log.error("Failed to store chunks for %s: %s", url, exc)


if __name__ == "__main__":
    main()
