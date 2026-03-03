"""规则服务：从配置加载规则集，供 LLM 与静态分析使用。"""
from pathlib import Path
from typing import Any

import yaml

from app.config import settings


class RuleService:
    """加载与提供规则集（MVP：单文件 YAML）。"""

    def __init__(self, config_path: Path | None = None):
        self._config_path = config_path or settings.rules_config_path
        self._rule_set: dict[str, Any] | None = None

    def load(self) -> dict[str, Any]:
        """加载规则集配置。"""
        if self._rule_set is not None:
            return self._rule_set
        path = self._config_path
        if not path.is_absolute():
            # 相对路径基于项目根（code_review_agent）
            path = Path(__file__).resolve().parent.parent.parent / path
        if not path.exists():
            self._rule_set = {"rule_set": {"name": "default"}, "rules": []}
            return self._rule_set
        with open(path, encoding="utf-8") as f:
            self._rule_set = yaml.safe_load(f) or {}
        return self._rule_set

    def get_rules_for_prompt(self) -> str:
        """返回供 LLM Prompt 使用的规则摘要文本。"""
        data = self.load()
        rules = data.get("rules") or []
        if not rules:
            return "审查维度：正确性、可读性、规范与风格、安全、性能。"
        lines = []
        for r in rules:
            if not r.get("enabled", True):
                continue
            rid = r.get("rule_id", "")
            name = r.get("name", rid)
            desc = r.get("description", "")
            sev = r.get("severity", "medium")
            lines.append(f"- [{sev}] {name}: {desc}")
        return "\n".join(lines) if lines else "通用代码审查最佳实践。"

    def get_rule_ids(self) -> list[str]:
        """返回已启用的规则 ID 列表。"""
        data = self.load()
        rules = data.get("rules") or []
        return [r["rule_id"] for r in rules if r.get("enabled", True)]


_rule_service: RuleService | None = None


def get_rule_service() -> RuleService:
    global _rule_service
    if _rule_service is None:
        _rule_service = RuleService()
    return _rule_service
