"""LLM 审查引擎：构建 Prompt、调用模型、解析为 Issue 列表。"""
import json
import re
from typing import Any

from openai import AsyncOpenAI, OpenAI

from app.config import settings
from app.core.models import Issue, Severity
from app.services.rule_service import get_rule_service

# 输出 JSON 的 schema 说明，便于模型遵循
ISSUES_JSON_SCHEMA = """
请以 JSON 格式返回，且只返回一个 JSON 对象，不要包含 markdown 代码块或其它说明。格式如下：
{
  "issues": [
    {
      "file_path": "文件路径，与 diff 中一致",
      "line_start": 行号（数字，可选）,
      "line_end": 行号（数字，可选）,
      "rule_id": "规则ID：correctness|readability|style|security|performance",
      "severity": "critical|high|medium|low|info",
      "message": "问题描述",
      "suggestion": "修改建议或示例代码（可选）"
    }
  ]
}
若无问题，返回 {"issues": []}。
"""


def _build_system_prompt(rules_text: str) -> str:
    return f"""你是一位严格的代码审查专家。请根据以下规则对给出的代码变更（unified diff）进行审查。

审查规则：
{rules_text}

要求：
1. 只审查 diff 中实际变更的代码，不要臆测未展示的上下文。
2. 问题需具体到文件和行号（若 diff 中能确定）。
3. 建议要可执行，尽量给出修改示例。
4. 若没有发现问题，请返回空 issues 数组。
5. 严格按指定 JSON 格式输出，不要输出其他内容。
"""


def _build_user_prompt(diff_content: str, language_hint: str = "") -> str:
    hint = f"\n语言/框架提示：{language_hint}\n" if language_hint else ""
    return f"""请审查以下代码变更（unified diff）：{hint}

```
{diff_content}
```

{ISSUES_JSON_SCHEMA}
"""


def _parse_llm_response(text: str) -> list[dict[str, Any]]:
    """从模型返回文本中解析出 issues 列表。"""
    text = text.strip()
    # 去掉可能的 markdown 代码块
    if "```json" in text:
        text = re.sub(r"^.*?```json\s*", "", text)
    if "```" in text:
        text = re.sub(r"\s*```.*$", "", text)
    text = text.strip()
    try:
        data = json.loads(text)
        return data.get("issues") or []
    except json.JSONDecodeError:
        return []


def _to_severity(s: str) -> Severity:
    try:
        return Severity(s.lower())
    except ValueError:
        return Severity.MEDIUM


def _normalize_issue(raw: dict[str, Any]) -> Issue:
    return Issue(
        file_path=str(raw.get("file_path", "")),
        line_start=raw.get("line_start"),
        line_end=raw.get("line_end"),
        rule_id=str(raw.get("rule_id", "unknown")),
        severity=_to_severity(str(raw.get("severity", "medium"))),
        message=str(raw.get("message", "")),
        suggestion=raw.get("suggestion"),
        source="llm",
    )


class LLMReviewEngine:
    """调用 LLM 对 diff 进行审查，返回结构化 Issue 列表。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self._api_key = api_key or settings.llm_api_key
        self._base_url = base_url or settings.llm_base_url
        self._model = model or settings.llm_model
        self._client: OpenAI | None = None
        self._aclient: AsyncOpenAI | None = None

    def _get_client(self) -> OpenAI:
        if self._client is None:
            kwargs = {}
            if self._api_key:
                kwargs["api_key"] = self._api_key
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = OpenAI(**kwargs)
        return self._client

    def _get_async_client(self) -> AsyncOpenAI:
        if self._aclient is None:
            kwargs = {}
            if self._api_key:
                kwargs["api_key"] = self._api_key
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._aclient = AsyncOpenAI(**kwargs)
        return self._aclient

    def review_sync(self, diff_content: str, language_hint: str = "") -> list[Issue]:
        """同步审查。"""
        rule_svc = get_rule_service()
        rules_text = rule_svc.get_rules_for_prompt()
        system = _build_system_prompt(rules_text)
        user = _build_user_prompt(diff_content, language_hint)
        client = self._get_client()
        resp = client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=settings.llm_max_tokens,
            timeout=settings.llm_timeout_seconds,
        )
        content = (resp.choices[0].message.content or "").strip()
        raw_issues = _parse_llm_response(content)
        return [_normalize_issue(i) for i in raw_issues]

    async def review_async(self, diff_content: str, language_hint: str = "") -> list[Issue]:
        """异步审查。"""
        rule_svc = get_rule_service()
        rules_text = rule_svc.get_rules_for_prompt()
        system = _build_system_prompt(rules_text)
        user = _build_user_prompt(diff_content, language_hint)
        client = self._get_async_client()
        resp = await client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=settings.llm_max_tokens,
            timeout=settings.llm_timeout_seconds,
        )
        content = (resp.choices[0].message.content or "").strip()
        raw_issues = _parse_llm_response(content)
        return [_normalize_issue(i) for i in raw_issues]


_llm_engine: LLMReviewEngine | None = None


def get_llm_engine() -> LLMReviewEngine:
    global _llm_engine
    if _llm_engine is None:
        _llm_engine = LLMReviewEngine()
    return _llm_engine
