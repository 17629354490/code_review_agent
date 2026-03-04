#!/usr/bin/env python3
"""扫描 report_agent 仓库并生成审查报告（需配置 LLM）。"""
import sys
from pathlib import Path

# 项目根
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from app.services.repo_scanner import scan_repo_to_diff
from app.services.llm_engine import get_llm_engine
from app.services.report_service import get_report_service


REPO_URL = "https://github.com/17629354490/report_agent"
BRANCH = "main"
OUTPUT_DIR = _root / "data" / "reports" / "report_agent_scan"


def main() -> None:
    print("拉取仓库...")
    diff_content, repo_slug = scan_repo_to_diff(REPO_URL, branch=BRANCH)
    if not diff_content.strip():
        print("无目标文件")
        sys.exit(1)
    print("审查中...")
    engine = get_llm_engine()
    report_svc = get_report_service()
    issues = engine.review_sync(diff_content, language_hint="python")
    report = report_svc.build_report(task_id="report_agent_scan", repo=repo_slug, issues=issues)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    md_path = OUTPUT_DIR / "report.md"
    json_path = OUTPUT_DIR / "report.json"
    md_path.write_text(report.raw_markdown or "未发现需要报告的问题。", encoding="utf-8")
    json_path.write_text(report.model_dump_json(indent=2, exclude_none=True), encoding="utf-8")
    print(f"报告已写入: {md_path}")
    print(f"JSON: {json_path}")


if __name__ == "__main__":
    main()
