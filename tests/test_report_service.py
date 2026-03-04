"""报告服务单元测试。"""
from pathlib import Path

import pytest

from app.core.models import Issue, Severity
from app.services.report_service import ReportService


def test_build_report_empty_issues(report_service: ReportService):
    issues: list[Issue] = []
    report = report_service.build_report(task_id="t1", repo="owner/repo", issues=issues)
    assert report.task_id == "t1"
    assert report.repo == "owner/repo"
    assert report.summary["total"] == 0
    assert report.raw_markdown is not None
    assert "未发现需要报告的问题" in report.raw_markdown


def test_build_report_with_issues(report_service: ReportService):
    issues = [
        Issue(
            file_path="app/main.py",
            line_start=10,
            line_end=12,
            rule_id="style",
            severity=Severity.MEDIUM,
            message="建议添加类型注解",
            suggestion="def foo(x: int) -> str:",
        ),
    ]
    report = report_service.build_report(task_id="t2", repo="a/b", issues=issues)
    assert report.summary["total"] == 1
    assert report.summary["by_severity"]["medium"] == 1
    assert "app/main.py" in report.raw_markdown
    assert "10" in report.raw_markdown


def test_save_report(report_service: ReportService, temp_reports_dir: Path):
    report = report_service.build_report(task_id="task-1", repo="x/y", issues=[])
    report.raw_markdown = "# 审查结果\n无问题。"
    path = report_service.save_report(report)
    assert Path(path).exists()
    assert Path(path).read_text(encoding="utf-8") == "# 审查结果\n无问题。"


def test_get_report_content(report_service: ReportService):
    report = report_service.build_report(task_id="get-test", repo="r", issues=[])
    report_service.save_report(report)
    md = report_service.get_report_content("get-test", as_json=False)
    assert md is not None
    json_content = report_service.get_report_content("get-test", as_json=True)
    assert json_content is not None
    assert "get-test" in json_content


def test_get_report_path_not_exists(report_service: ReportService):
    assert report_service.get_report_path("nonexistent-id") is None
