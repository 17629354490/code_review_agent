"""编排层：拉取 diff、调用 LLM、聚合结果、生成报告、更新任务。"""
from app.core.models import Issue, ReviewReport, TaskStatus
from app.services.llm_engine import get_llm_engine
from app.services.report_service import get_report_service
from app.storage.task_store import get_task_store


class Orchestrator:
    """执行单次审查任务的完整流程。"""

    def run_task(self, task_id: str) -> None:
        """同步执行：取任务 -> 取 diff -> LLM 审查 -> 报告 -> 更新状态。"""
        store = get_task_store()
        task = store.get(task_id)
        if not task:
            return
        if task.get("status") != TaskStatus.PENDING.value:
            return
        store.set_running(task_id)
        diff = task.get("diff_content") or ""
        repo = task.get("repo", "")
        pr_id = task.get("pr_id")
        commit_sha = task.get("commit_sha")
        report_svc = get_report_service()
        try:
            if not diff.strip():
                store.set_failed(task_id, "无 diff 内容可审查")
                return
            engine = get_llm_engine()
            issues: list[Issue] = engine.review_sync(diff)
            report = report_svc.build_report(
                task_id=task_id,
                repo=repo,
                issues=issues,
                pr_id=pr_id,
                commit_sha=commit_sha,
            )
            report_path = report_svc.save_report(report)
            store.set_completed(task_id, report_path)
        except Exception as e:
            store.set_failed(task_id, str(e))
            raise


_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
