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
  ├── Help or support center website Docs  ← Kafka pipeline (scraper → kafka → consumer)
  └── Kubernetes API   ← live pod logs + resources

Kafka Pipeline
  scraper.py  →  help-center-docs (topic)  →  kafka_consumer.py  →  ChromaDB
```

## Quick Start

### Local Development

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

**Terminal 6 — Scraper** *(scrapes the help or support center website docs → publishes to Kafka every 5s)*
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


## Sample Data

Load the included sample data to test immediately:

```bash
# attach files from sample_data folder in the chat

# Then ask: "Why is my pod crashing?"
```
