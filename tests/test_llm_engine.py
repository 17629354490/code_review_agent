"""LLM 引擎解析逻辑单元测试（不调用真实 API）。"""
import pytest

from app.core.models import Issue, Severity
from app.services.llm_engine import _parse_llm_response, _normalize_issue, _to_severity


def test_parse_llm_response_empty():
    assert _parse_llm_response('{"issues": []}') == []
    assert _parse_llm_response('{"issues":[]}') == []


def test_parse_llm_response_with_markdown_block():
    # 模拟 LLM 返回带 ```json 代码块的内容
    raw = '```json\n{"issues": [{"file_path": "a.py", "rule_id": "style", "severity": "low", "message": "test"}]}\n```'
    parsed = _parse_llm_response(raw)
    assert len(parsed) == 1
    assert parsed[0]["file_path"] == "a.py"
    assert parsed[0]["message"] == "test"


def test_parse_llm_response_invalid_json():
    assert _parse_llm_response("not json at all") == []
    assert _parse_llm_response("{}") == []
    assert _parse_llm_response('{"issues": null}') == []


def test_to_severity():
    assert _to_severity("critical") == Severity.CRITICAL
    assert _to_severity("HIGH") == Severity.HIGH
    assert _to_severity("unknown") == Severity.MEDIUM


def test_normalize_issue():
    raw = {
        "file_path": "app/main.py",
        "line_start": 1,
        "line_end": 5,
        "rule_id": "security",
        "severity": "high",
        "message": "硬编码密钥",
        "suggestion": "使用环境变量",
    }
    issue = _normalize_issue(raw)
    assert issue.file_path == "app/main.py"
    assert issue.line_start == 1
    assert issue.line_end == 5
    assert issue.rule_id == "security"
    assert issue.severity == Severity.HIGH
    assert issue.message == "硬编码密钥"
    assert issue.suggestion == "使用环境变量"
    assert issue.source == "llm"


def test_normalize_issue_minimal():
    issue = _normalize_issue({"message": "ok"})
    assert issue.file_path == ""
    assert issue.rule_id == "unknown"
    assert issue.severity == Severity.MEDIUM
    assert issue.message == "ok"
