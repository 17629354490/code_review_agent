"""后台 Worker：从任务存储中取 PENDING 任务并交给编排层执行。"""
import logging
import threading
import time

from app.config import settings
from app.services.orchestrator import Orchestrator
from app.storage.task_store import get_task_store

logger = logging.getLogger(__name__)


def _run_worker_once(orch: Orchestrator) -> bool:
    """执行一轮：取一个 PENDING 任务并处理。返回是否处理了任务。"""
    store = get_task_store()
    task_id = store.get_pending_task_id()
    if not task_id:
        return False
    try:
        orch.run_task(task_id)
        return True
    except Exception as e:
        logger.exception("Worker run_task failed: %s", e)
        store.set_failed(task_id, str(e))
        return True


def run_worker_loop(stop_event: threading.Event | None = None):
    """在后台线程中循环拉取并执行任务。"""
    orch = Orchestrator()
    interval = settings.worker_poll_interval_seconds
    while True:
        if stop_event and stop_event.is_set():
            break
        try:
            _run_worker_once(orch)
        except Exception as e:
            logger.exception("Worker loop error: %s", e)
        time.sleep(interval)


def start_background_worker() -> threading.Thread:
    """启动后台 Worker 线程。"""
    stop = threading.Event()
    t = threading.Thread(target=run_worker_loop, args=(stop,), daemon=True)
    t.start()
    return t
