"""存储层：任务状态与报告索引。"""
from .task_store import TaskStore, get_task_store

__all__ = ["TaskStore", "get_task_store"]
