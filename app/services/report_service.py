"""报告服务：生成 Markdown/JSON 报告并持久化。"""
from pathlib import Path
from datetime import datetime

from app.config import settings
from app.core.models import Issue, ReviewReport, Severity


def _severity_summary(issues: list[Issue]) -> dict[str, int]:
    summary = {s.value: 0 for s in Severity}
    for i in issues:
        summary[i.severity.value] = summary.get(i.severity.value, 0) + 1
    return summary


def _issues_to_markdown(issues: list[Issue]) -> str:
    if not issues:
        return "未发现需要报告的问题。"
    lines = ["## 审查结果\n", "| 严重程度 | 文件 | 行号 | 规则 | 描述 | 建议 |", "|----------|------|------|------|------|------|"]
    for i in issues:
        line_range = ""
        if i.line_start is not None:
            line_range = str(i.line_start)
            if i.line_end is not None and i.line_end != i.line_start:
                line_range += f"-{i.line_end}"
        sugg = (i.suggestion or "-")[:80]
        if len(i.suggestion or "") > 80:
            sugg += "..."
        lines.append(f"| {i.severity.value} | {i.file_path} | {line_range} | {i.rule_id} | {i.message[:100]} | {sugg} |")
    return "\n".join(lines)


class ReportService:
    """生成并存储审查报告。"""

    def __init__(self, reports_dir: Path | None = None):
        self._reports_dir = reports_dir or settings.reports_dir
        if not self._reports_dir.is_absolute():
            self._reports_dir = Path(__file__).resolve().parent.parent.parent / self._reports_dir
        self._reports_dir.mkdir(parents=True, exist_ok=True)

    def build_report(
        self,
        task_id: str,
        repo: str,
        issues: list[Issue],
        pr_id: int | None = None,
        commit_sha: str | None = None,
    ) -> ReviewReport:
        """构建报告对象。"""
        summary = {
            "total": len(issues),
            "by_severity": _severity_summary(issues),
        }
        raw_md = _issues_to_markdown(issues)
        return ReviewReport(
            task_id=task_id,
            repo=repo,
            pr_id=pr_id,
            commit_sha=commit_sha,
            summary=summary,
            issues=issues,
            raw_markdown=raw_md,
            completed_at=datetime.utcnow(),
        )

    def save_report(self, report: ReviewReport) -> str:
        """将报告写入目录，返回可访问路径（相对或绝对）。"""
        safe_id = report.task_id.replace("/", "_").replace("\\", "_")
        base = self._reports_dir / safe_id
        base.mkdir(parents=True, exist_ok=True)
        md_path = base / "report.md"
        json_path = base / "report.json"
        md_path.write_text(report.raw_markdown or "", encoding="utf-8")
        json_path.write_text(
            report.model_dump_json(indent=2, exclude_none=True),
            encoding="utf-8",
        )
        return str(md_path)

    def get_report_path(self, task_id: str) -> Path | None:
        """获取某任务的报告目录。"""
        safe_id = task_id.replace("/", "_").replace("\\", "_")
        base = self._reports_dir / safe_id
        if not base.exists():
            return None
        md = base / "report.md"
        return md if md.exists() else None

    def get_report_content(self, task_id: str, as_json: bool = False) -> str | None:
        """读取已保存的报告内容。"""
        safe_id = task_id.replace("/", "_").replace("\\", "_")
        base = self._reports_dir / safe_id
        if as_json:
            p = base / "report.json"
        else:
            p = base / "report.md"
        if not p.exists():
            return None
        return p.read_text(encoding="utf-8")


_report_service: ReportService | None = None


def get_report_service() -> ReportService:
    global _report_service
    if _report_service is None:
        _report_service = ReportService()
    return _report_service
