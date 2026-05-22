from pydantic import BaseModel, Field
from typing import Literal
from enum import Enum


class Role(str, Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


class Message(BaseModel):
    role: Role
    content: str


class Attachment(BaseModel):
    name: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    session_id: str = "default"
    stream: bool = True
    attachments: list[Attachment] = Field(default_factory=list)


class IngestRequest(BaseModel):
    content: str
    source: str
    doc_type: Literal["log", "yaml", "runbook", "doc", "swagger"] = "doc"
    metadata: dict = Field(default_factory=dict)


class IngestResponse(BaseModel):
    success: bool
    chunks_added: int
    source: str


class K8sLogsRequest(BaseModel):
    namespace: str = "default"
    pod_name: str
    container: str = ""
    tail_lines: int = 100


class K8sResourceRequest(BaseModel):
    namespace: str = "default"
    resource_type: Literal["pod", "deployment", "service", "configmap", "ingress"] = "pod"
    name: str = ""


class SourceChunk(BaseModel):
    content: str
    source: str
    doc_type: str
    score: float
