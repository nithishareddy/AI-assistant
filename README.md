# AI-assistant

Imagine troubleshooting Kubernetes failures without running a single kubectl command. Along with handling regular natural language queries, this AI-powered assistant built using RAG (Retrieval-Augmented Generation) helps users diagnose cluster issues through conversational interactions. It can also learn from support docs to answer product specific questions, while analyzing logs, explaining YAML configurations, identifying root causes, and suggesting fixes automatically .

## Sample Demo

https://github.com/user-attachments/assets/4e09228f-4a86-4561-a71e-f5c177f27b9a

The above video explains these scenarios:

```bash
Scenario 1:
# If you have log files , you can attach it to the chat 

# Then ask: "Why is my pod crashing?"

Scenario 2:
# You can ask the AI assistant : List the pods in a namespace
# The assistant will run the necessary kubectl commands and lists all the pods in your cluster.

Scenario 3:
# You can ask the AI assistant to troubleshoot a failure directly  : Why <name-of-the-pod> in <namespace> namespace in not running?
# The assistant will access your cluster , logs and the kubernetes events to troubleshoot and then provides the root cause.
```

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
  ├── Support Docs, Logs,yamls ,API specs etc
  └── Kubernetes API   ← live pod logs + resources

```

## Quick Start

### Local Development


**Terminal 1 — ChromaDB**
```bash
cd backend
.venv/bin/chroma run --path ./chroma_data --host 127.0.0.1 --port 8001
```

**Terminal 2 — Backend**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # add your OPENAI_API_KEY
export $(grep -v '^#' .env | xargs)
export CHROMA_HOST=127.0.0.1 CHROMA_PORT=8001
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 3 — Frontend**
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173









