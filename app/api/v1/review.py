"""审查相关 API：触发、任务状态、报告。"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.api.deps import require_api_key
from app.core.models import (
    ReviewTaskRequest,
    ReviewTaskResponse,
    ReviewTaskStatus,
    TaskStatus,
)
from app.storage.task_store import get_task_store
from app.services.report_service import get_report_service

router = APIRouter(prefix="/review", tags=["review"])


@router.post("/trigger", response_model=ReviewTaskResponse)
async def trigger_review(
    body: ReviewTaskRequest,
    _: None = Depends(require_api_key),
) -> ReviewTaskResponse:
    """触发一次代码审查。若提供 diff_content 则直接使用，否则需后续扩展拉取远程 diff。"""
    store = get_task_store()
    if not body.diff_content and not body.commit_sha:
        raise HTTPException(
            status_code=400,
            detail="请提供 diff_content（直接传 diff 文本）或 commit_sha（后续将支持拉取）",
        )
    diff_content = body.diff_content or ""
    # MVP：仅支持直接传 diff；commit_sha 仅作记录，不拉取
    task_id = store.create(
        repo=body.repo,
        pr_id=body.pr_id,
        commit_sha=body.commit_sha,
        branch=body.branch,
        diff_content=diff_content,
    )
    return ReviewTaskResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        message="任务已入队，请通过 GET /review/tasks/{task_id} 查询状态与报告。",
    )


@router.get("/tasks/{task_id}", response_model=ReviewTaskStatus)
async def get_task_status(
    task_id: str,
    _: None = Depends(require_api_key),
) -> ReviewTaskStatus:
    """查询审查任务状态。"""
    store = get_task_store()
    task = store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return ReviewTaskStatus(
        task_id=task["task_id"],
        status=TaskStatus(task["status"]),
        repo=task["repo"],
        pr_id=task.get("pr_id"),
        commit_sha=task.get("commit_sha"),
        triggered_at=task.get("triggered_at"),
        completed_at=task.get("completed_at"),
        report_url=task.get("report_url"),
        error_message=task.get("error_message"),
    )


@router.get("/reports/{task_id}")
async def get_report(
    task_id: str,
    format: str = "markdown",  # markdown | json
    _: None = Depends(require_api_key),
):
    """获取审查报告。format=markdown 返回 MD 文本，format=json 返回 JSON。"""
    store = get_task_store()
    task = store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.get("status") != TaskStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail="任务未完成或已失败，暂无报告")
    report_svc = get_report_service()
    content = report_svc.get_report_content(task_id, as_json=(format == "json"))
    if content is None:
        raise HTTPException(status_code=404, detail="报告文件不存在")
    if format == "json":
        return Response(content=content, media_type="application/json")
    return Response(content=content, media_type="text/markdown; charset=utf-8")
