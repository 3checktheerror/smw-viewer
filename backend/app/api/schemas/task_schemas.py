from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List


class TaskInfo(BaseModel):
    task_id: str


class TaskProgress(BaseModel):
    task_id: str
    status: str
    progress: int
    total: int
    result: Optional[Dict[str, Any]] = None


class TaskCreateResponse(BaseModel):
    task_id: str = Field(..., description="后台任务 ID")


class TaskProgressResponse(BaseModel):
    progress: int = Field(..., description="已完成数量")
    total: int = Field(..., description="总数量")
    status: str = Field(..., description="任务状态，例如 PENDING/RUNNING/SUCCESS/FAIL")
    result: Optional[Any] = Field(default=None, description="任务结果，任务完成时返回")
