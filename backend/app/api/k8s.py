from fastapi import APIRouter, HTTPException
from app.models.schemas import K8sLogsRequest, K8sResourceRequest
from app.services.k8s_service import get_pod_logs, get_resource, list_namespaces
from app.rag.pipeline import ingest_document

router = APIRouter(prefix="/k8s", tags=["kubernetes"])


@router.get("/namespaces")
async def namespaces():
    return {"namespaces": await list_namespaces()}


@router.post("/logs")
async def pod_logs(request: K8sLogsRequest):
    logs = await get_pod_logs(
        namespace=request.namespace,
        pod_name=request.pod_name,
        container=request.container,
        tail_lines=request.tail_lines,
    )
    # Auto-ingest fetched logs into the RAG vector store
    source = f"k8s://logs/{request.namespace}/{request.pod_name}"
    await ingest_document(
        content=logs,
        source=source,
        doc_type="log",
        metadata={
            "namespace": request.namespace,
            "pod": request.pod_name,
            "container": request.container,
        },
    )
    return {"logs": logs, "ingested": True, "source": source}


@router.post("/resource")
async def k8s_resource(request: K8sResourceRequest):
    import json
    resource = await get_resource(
        namespace=request.namespace,
        resource_type=request.resource_type,
        name=request.name,
    )
    if "error" in resource:
        raise HTTPException(status_code=400, detail=resource["error"])

    # Ingest resource YAML into vector store
    source = f"k8s://{request.resource_type}/{request.namespace}/{request.name}"
    await ingest_document(
        content=json.dumps(resource, indent=2),
        source=source,
        doc_type="yaml",
        metadata={
            "namespace": request.namespace,
            "resource_type": request.resource_type,
            "name": request.name,
        },
    )
    return {"resource": resource, "ingested": True}
