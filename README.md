# AI-assistant

An AI assistant with RAG (Retrieval-Augmented Generation) that helps engineers debug Kubernetes issues, analyze logs, explain YAML configs, and suggest fixes — all through a chat interface.

## Architecture

```
React Chat UI (Vite + React 18)
       ↓  SSE streaming  [+ file attachments via + button]
FastAPI Backend (Python)
       ↓
RAG Pipeline
  ├── Chunker     → splits logs/YAML/docs intelligently
  ├── Embedder    → OpenAI text-embedding-3-small
  └── Retriever   → ChromaDB cosine similarity search (HTTP server)
       ↓
OpenAI GPT-4o (with DevOps system prompt)
       ↑
Knowledge Base (ChromaDB)
  ├── Help center website Docs  ← Kafka pipeline (scraper → kafka → consumer)
  └── Kubernetes API   ← live pod logs + resources

Kafka Pipeline
  scraper.py  →  help-center-docs (topic)  →  kafka_consumer.py  →  ChromaDB
```

## Quick Start

### Option 1: Docker Compose (work-in-progress)

```bash
cp backend/.env.example backend/.env
# Edit backend/.env and add your OPENAI_API_KEY

docker-compose up --build
```

Open http://localhost:5173

### Option 2: Local Development

Open **6 terminal tabs** and run each command in order. Wait for each service to be ready before starting the next.

**Terminal 1 — Kafka**
```bash
brew install kafka      # skip if already installed
brew services start kafka
```

**Terminal 2 — ChromaDB**
```bash
cd backend
.venv/bin/chroma run --path ./chroma_data --host 127.0.0.1 --port 8001
```

**Terminal 3 — Backend**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # add your OPENAI_API_KEY
export $(grep -v '^#' .env | xargs)
export CHROMA_HOST=127.0.0.1 CHROMA_PORT=8001
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 4 — Frontend**
```bash
cd frontend
npm install
npm run dev
```

**Terminal 5 — Kafka Consumer** *(reads Kafka topic → writes to ChromaDB)*
```bash
cd scripts
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
CHROMA_HOST=127.0.0.1 CHROMA_PORT=8001 python kafka_consumer.py
```

**Terminal 6 — Scraper** *(scrapes the help center website docs → publishes to Kafka every 5s)*
```bash
cd scripts
source .venv/bin/activate
python scraper.py
```

Open http://localhost:5173

> **Start order matters:** Kafka → ChromaDB → Backend → Frontend / Consumer / Scraper

#### Managing the Knowledge Base

```bash
# List all sources currently in ChromaDB
GET  http://localhost:8000/ingest/sources

# Remove a specific source
DELETE http://localhost:8000/ingest/source?source=<source-name>
```

## Features

| Feature | Description |
|---|---|
| Streaming chat | Real-time token streaming via SSE |
| RAG retrieval | Retrieves relevant context before answering |
| File attachments | Attach `.yaml` / `.log` files via `+` button as inline query context |
| Source attribution | See which docs were used to answer |
| Quick prompts | One-click common DevOps questions |
| K8s integration | Fetch live pod logs + resources via K8s API |
| Session memory | Maintains conversation history per session |
| Kafka pipeline | Scraper publishes the help center website docs to Kafka every 5s; consumer ingests to ChromaDB |
| Knowledge base API | `GET /ingest/sources` and `DELETE /ingest/source` to manage ChromaDB content |

## API Reference

```
POST   /chat                  — Streaming chat with RAG (+ optional attachments)
POST   /ingest                — Ingest text into vector DB
POST   /ingest/file           — Upload and ingest a file
GET    /ingest/sources        — List all sources in ChromaDB with chunk counts
DELETE /ingest/source         — Remove all chunks for a given source (?source=name)
DELETE /chat/{session_id}     — Clear conversation history
POST   /k8s/logs              — Fetch and ingest K8s pod logs
POST   /k8s/resource          — Fetch and ingest K8s resource YAML
GET    /k8s/namespaces        — List K8s namespaces
GET    /health                — Health check
```

## Sample Data

Load the included sample data to test immediately:

```bash
# Ingest sample OOMKilled logs
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "content": "'"$(cat sample_data/logs/sample_pod_logs.txt)"'",
    "source": "order-service-logs",
    "doc_type": "log"
  }'

# Then ask: "Why is my pod crashing?"
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | required | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o` | Chat model |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model |
| `CHROMA_HOST` | `localhost` | ChromaDB host |
| `CHROMA_PORT` | `8001` | ChromaDB port |
| `CHROMA_COLLECTION` | `devops_knowledge` | Collection name |
| `K8S_IN_CLUSTER` | `false` | Use in-cluster K8s config |
| `K8S_KUBECONFIG` | `` | Path to kubeconfig |
| `CHUNK_SIZE` | `800` | Characters per chunk |
| `RETRIEVAL_TOP_K` | `5` | Top K results from vector search |

## Project Structure

```
devops-ai-assistant/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI route handlers
│   │   │   ├── chat.py   # SSE streaming chat
│   │   │   ├── ingest.py # Document ingestion
│   │   │   └── k8s.py    # Kubernetes integration
│   │   ├── rag/
│   │   │   ├── chunker.py   # Smart chunking by doc type
│   │   │   ├── embedder.py  # ChromaDB + OpenAI embeddings
│   │   │   └── pipeline.py  # RAG orchestration + prompts
│   │   ├── services/
│   │   │   ├── llm_service.py  # OpenAI chat client
│   │   │   └── k8s_service.py  # Kubernetes client
│   │   ├── models/schemas.py   # Pydantic models
│   │   ├── config.py           # Settings via env
│   │   └── main.py             # FastAPI app
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── Chat/       # ChatWindow, MessageBubble, ChatInput
│       │   ├── Sidebar/    # Navigation + file upload
│       │   ├── Upload/     # FileUpload with drag-and-drop
│       │   └── Layout/     # Top-level layout
│       ├── hooks/useChat.js   # Streaming chat state hook
│       ├── services/api.js    # Backend API client
│       └── index.css          # Dark theme design system
├── scripts/
│   ├── scraper.py          # Crawls help center website docs → publishes to Kafka every 5s
│   ├── kafka_consumer.py   # Reads Kafka topic → chunks + embeds → ChromaDB
│   └── requirements.txt    # kafka-python-ng, beautifulsoup4, chromadb, openai
├── sample_data/
│   ├── logs/          # Sample OOMKilled pod logs
│   ├── yamls/         # Sample K8s deployment YAML
│   └── runbooks/      # Sample incident runbooks
└── docker-compose.yml
```
