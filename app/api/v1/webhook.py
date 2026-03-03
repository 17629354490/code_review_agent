"""Webhook 入口：GitHub / GitLab（MVP 为占位，后续实现拉 diff 与回写）。"""
import hmac
import hashlib
import json
from fastapi import APIRouter, Request, HTTPException, Header, Depends
from app.api.deps import require_api_key
from app.config import settings
from app.storage.task_store import get_task_store

router = APIRouter(prefix="/webhook", tags=["webhook"])


def _verify_github_signature(payload: bytes, signature: str | None) -> bool:
    secret = settings.webhook_github_secret
    if not secret or not signature:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _verify_gitlab_token(token: str | None) -> bool:
    return bool(settings.webhook_gitlab_secret and token == settings.webhook_gitlab_secret)


@router.post("/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(None),
    _: None = Depends(require_api_key),
):
    """接收 GitHub Webhook（如 pull_request）。MVP：仅解析事件并可选创建任务（需 body 中带 diff 或后续拉取）。"""
    body = await request.body()
    if settings.webhook_github_secret and not _verify_github_signature(body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    event = request.headers.get("X-GitHub-Event", "")
    if event == "ping":
        return {"ok": True, "message": "pong"}
    if event != "pull_request":
        return {"ok": True, "message": f"Ignored event: {event}"}
    action = data.get("action")
    if action not in ("opened", "synchronize", "reopened"):
        return {"ok": True, "message": f"Ignored action: {action}"}
    repo = data.get("repository", {}).get("full_name", "")
    pr_number = data.get("number")
    if not repo or pr_number is None:
        raise HTTPException(status_code=400, detail="Missing repo or PR number")
    # MVP：不拉取 diff，仅返回已接收；后续可在此调用 GitHub API 拉取 diff 并 create task
    store = get_task_store()
    task_id = store.create(
        repo=repo,
        pr_id=pr_number,
        commit_sha=None,
        branch=data.get("pull_request", {}).get("base", {}).get("ref"),
        diff_content="",  # TODO: fetch diff via GitHub API
    )
    return {"ok": True, "task_id": task_id, "message": "Task created (diff not fetched in MVP)"}


@router.post("/gitlab")
async def gitlab_webhook(
    request: Request,
    x_gitlab_token: str | None = Header(None),
    _: None = Depends(require_api_key),
):
    """接收 GitLab Merge Request 事件。MVP：仅解析并创建任务占位。"""
    if settings.webhook_gitlab_secret and not _verify_gitlab_token(x_gitlab_token):
        raise HTTPException(status_code=401, detail="Invalid token")
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    obj_attr = data.get("object_attributes", {})
    if obj_attr.get("target_branch") is None:
        return {"ok": True, "message": "Not a merge request event"}
    repo = data.get("project", {}).get("path_with_namespace", "")
    mr_iid = obj_attr.get("iid")
    if not repo or mr_iid is None:
        raise HTTPException(status_code=400, detail="Missing repo or MR iid")
    store = get_task_store()
    task_id = store.create(
        repo=repo,
        pr_id=mr_iid,
        commit_sha=obj_attr.get("last_commit", {}).get("id"),
        branch=obj_attr.get("target_branch"),
        diff_content="",  # TODO: fetch diff via GitLab API
    )
    return {"ok": True, "task_id": task_id, "message": "Task created (diff not fetched in MVP)"}
