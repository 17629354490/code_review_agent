"""任务存储（MVP：内存），记录任务状态与元数据。"""
from datetime import datetime, timezone
from typing import Any
import uuid

from app.core.models import TaskStatus

# 单任务记录
TaskRecord = dict[str, Any]


class TaskStore:
    """内存任务表，支持 get/set/list。"""

    def __init__(self):
        self._tasks: dict[str, TaskRecord] = {}

    def create(
        self,
        repo: str,
        pr_id: int | None = None,
        commit_sha: str | None = None,
        branch: str | None = None,
        diff_content: str | None = None,
    ) -> str:
        """创建任务，返回 task_id。"""
        task_id = str(uuid.uuid4())
        self._tasks[task_id] = {
            "task_id": task_id,
            "repo": repo,
            "pr_id": pr_id,
            "commit_sha": commit_sha,
            "branch": branch,
            "diff_content": diff_content,
            "status": TaskStatus.PENDING.value,
            "triggered_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "report_url": None,
            "error_message": None,
        }
        return task_id

    def get(self, task_id: str) -> TaskRecord | None:
        return self._tasks.get(task_id)

    def set_status(
        self,
        task_id: str,
        status: TaskStatus,
        report_url: str | None = None,
        error_message: str | None = None,
    ) -> None:
        r = self._tasks.get(task_id)
        if not r:
            return
        r["status"] = status.value
        if status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            r["completed_at"] = datetime.now(timezone.utc).isoformat()
        if report_url is not None:
            r["report_url"] = report_url
        if error_message is not None:
            r["error_message"] = error_message

    def set_running(self, task_id: str) -> None:
        self.set_status(task_id, TaskStatus.RUNNING)

    def set_completed(self, task_id: str, report_url: str) -> None:
        self.set_status(task_id, TaskStatus.COMPLETED, report_url=report_url)

    def set_failed(self, task_id: str, error_message: str) -> None:
        self.set_status(task_id, TaskStatus.FAILED, error_message=error_message)

    def get_pending_task_id(self) -> str | None:
        """取一个待处理任务 ID（FIFO 简单实现）。"""
        for tid, r in self._tasks.items():
            if r.get("status") == TaskStatus.PENDING.value:
                return tid
        return None

    def get_diff_content(self, task_id: str) -> str | None:
        r = self.get(task_id)
        return (r or {}).get("diff_content")


_task_store: TaskStore | None = None


def get_task_store() -> TaskStore:
    global _task_store
    if _task_store is None:
        _task_store = TaskStore()
    return _task_store
