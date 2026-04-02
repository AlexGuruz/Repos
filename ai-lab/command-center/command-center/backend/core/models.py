from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime
import uuid


EventType = Literal["action", "approval", "hardware", "feed", "repo", "chat"]
OpType = Literal["read", "write", "exec", "rag", "sys"]
StatusType = Literal["pending", "approved", "denied", "running", "done", "error"]


class ActionEvent(BaseModel):
    id: str = Field(default_factory=lambda: f"ACT-{uuid.uuid4().hex[:6].upper()}")
    type: EventType = "action"
    agent: str
    op: OpType
    detail: str
    bytes_moved: Optional[str] = None
    status: StatusType = "done"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ApprovalEvent(BaseModel):
    id: str = Field(default_factory=lambda: f"APR-{uuid.uuid4().hex[:6].upper()}")
    type: EventType = "approval"
    agent: str
    action: str
    detail: str
    repo_class: Optional[str] = None
    catalog_context: Optional[str] = None
    status: StatusType = "pending"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ApprovalResolution(BaseModel):
    id: str
    resolution: Literal["approved", "denied"]


class HardwareSnapshot(BaseModel):
    type: EventType = "hardware"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    agents: list[dict] = []
    gpu: Optional[dict] = None
    cpu_percent: float = 0.0
    ram_used_gb: float = 0.0
    ram_total_gb: float = 0.0


class ChatMessage(BaseModel):
    role: Literal["user", "ai", "sys"]
    text: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class RepoFileEvent(BaseModel):
    type: EventType = "repo"
    path: str
    agent: str
    op: OpType
    bytes_moved: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WSMessage(BaseModel):
    """Envelope sent over the WebSocket to all connected clients."""
    event: str  # action | approval | hardware | feed | repo | chat
    data: dict
