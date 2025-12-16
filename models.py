from pydantic import BaseModel
from enum import Enum
from typing import Optional


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TableFormat(str, Enum):
    """Table export format options"""
    AUTO = "auto"
    MARKDOWN = "markdown"
    HTML = "html"


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    message: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    message: str
    progress: Optional[int] = None
    error: Optional[str] = None
