"""Pytest  fixtures：临时报告目录、Mock 等。"""
import tempfile
from pathlib import Path

import pytest

@pytest.fixture
def temp_reports_dir(tmp_path: Path):
    """临时报告目录，用于不污染 data/reports。"""
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True)
    return reports_dir


@pytest.fixture
def report_service(temp_reports_dir: Path):
    """使用临时目录的 ReportService。"""
    from app.services.report_service import ReportService
    return ReportService(reports_dir=temp_reports_dir)
