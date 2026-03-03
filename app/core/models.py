"""API 与内部使用的数据模型。"""
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Issue(BaseModel):
    """单条审查问题。"""
    file_path: str
    line_start: int | None = None
    line_end: int | None = None
    rule_id: str
    severity: Severity = Severity.MEDIUM
    message: str
    suggestion: str | None = None
    source: str = "llm"  # llm | static


class ReviewTaskRequest(BaseModel):
    """触发审查的请求体。"""
    repo: str = Field(..., description="仓库标识，如 owner/repo")
    pr_id: int | None = Field(None, description="PR/MR 编号，与 commit_sha 二选一")
    commit_sha: str | None = Field(None, description="commit SHA，本地审查时使用")
    branch: str | None = Field(None, description="目标分支")
    diff_content: str | None = Field(None, description="直接传入 diff 文本，不拉取远程")
    diff_url: str | None = Field(None, description="diff 的 URL（可选）")


class ReviewTaskResponse(BaseModel):
    """触发审查的响应。"""
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    message: str = "任务已入队"


class ReviewTaskStatus(BaseModel):
    """任务状态查询响应。"""
    task_id: str
    status: TaskStatus
    repo: str
    pr_id: int | None = None
    commit_sha: str | None = None
    triggered_at: str | None = None  # ISO 格式
    completed_at: str | None = None  # ISO 格式
    report_url: str | None = None
    error_message: str | None = None


class ReviewReport(BaseModel):
    """审查报告。"""
    task_id: str
    repo: str
    pr_id: int | None = None
    commit_sha: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)  # 统计：按严重程度、规则等
    issues: list[Issue] = Field(default_factory=list)
    raw_markdown: str | None = None
    completed_at: datetime = Field(default_factory=datetime.utcnow)
