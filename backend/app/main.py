from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.api import chat, ingest, k8s

settings = get_settings()

app = FastAPI(
    title="DevOps AI Assistant API",
    description="RAG-powered DevOps assistant for log analysis, YAML explanation, and incident debugging",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(ingest.router)
app.include_router(k8s.router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
