from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.models.schemas import IngestRequest, IngestResponse
from app.rag.pipeline import ingest_document
from app.rag.embedder import delete_by_source, list_sources

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=IngestResponse)
async def ingest_text(request: IngestRequest):
    try:
        count = await ingest_document(
            content=request.content,
            source=request.source,
            doc_type=request.doc_type,
            metadata=request.metadata,
        )
        return IngestResponse(success=True, chunks_added=count, source=request.source)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/file", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile = File(...),
    doc_type: str = Form("doc"),
):
    allowed_types = {"log", "yaml", "runbook", "doc", "swagger"}
    if doc_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"doc_type must be one of {allowed_types}")

    content_bytes = await file.read()
    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded text")

    # Auto-detect type from extension
    filename = file.filename or "uploaded_file"
    if filename.endswith((".yaml", ".yml")) and doc_type == "doc":
        doc_type = "yaml"
    elif filename.endswith(".log") and doc_type == "doc":
        doc_type = "log"
    elif filename.endswith(".json") and doc_type == "doc":
        doc_type = "swagger"

    try:
        count = await ingest_document(
            content=content,
            source=filename,
            doc_type=doc_type,
            metadata={"filename": filename},
        )
        return IngestResponse(success=True, chunks_added=count, source=filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sources")
def get_sources():
    return {"sources": list_sources()}


@router.delete("/source")
def delete_source(source: str):
    deleted = delete_by_source(source)
    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"No chunks found for source: {source}")
    return {"deleted_chunks": deleted, "source": source}
