"""命令行入口：本地审查 diff 或调用 API。"""
import sys
from pathlib import Path

import typer

# 将项目根加入 path，便于从任意目录运行 python -m cli.main
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

app = typer.Typer(help="代码审查智能体 CLI")


def _load_diff(diff_path: str | None, stdin: bool) -> str:
    if stdin:
        return sys.stdin.read()
    if not diff_path:
        typer.echo("请指定 --diff 文件或使用 --stdin 从标准输入读取 diff。", err=True)
        raise typer.Exit(1)
    path = Path(diff_path)
    if not path.exists():
        typer.echo(f"文件不存在: {path}", err=True)
        raise typer.Exit(1)
    return path.read_text(encoding="utf-8", errors="replace")


@app.command()
def review(
    diff: str | None = typer.Option(None, "--diff", "-d", help="diff 文件路径"),
    stdin: bool = typer.Option(False, "--stdin", help="从标准输入读取 diff"),
    repo: str = typer.Option("local", "--repo", "-r", help="仓库标识，用于报告"),
    language: str = typer.Option("", "--language", "-l", help="语言/框架提示，如 python, react"),
    output: str | None = typer.Option(None, "--output", "-o", help="报告输出路径（默认打印到 stdout）"),
):
    """对本地 diff 执行审查（调用 LLM，不经过 API 服务）。"""
    diff_content = _load_diff(diff, stdin)
    if not diff_content.strip():
        typer.echo("Diff 内容为空。", err=True)
        raise typer.Exit(1)
    typer.echo("正在审查...", err=True)
    from app.services.llm_engine import get_llm_engine
    from app.services.report_service import get_report_service
    from app.core.models import Issue

    engine = get_llm_engine()
    report_svc = get_report_service()
    issues: list[Issue] = engine.review_sync(diff_content, language_hint=language)
    report = report_svc.build_report(task_id="cli", repo=repo, issues=issues)
    md = report.raw_markdown or "未发现需要报告的问题。"
    if output:
        Path(output).write_text(md, encoding="utf-8")
        typer.echo(f"报告已写入: {output}", err=True)
    else:
        print(md)


@app.command()
def trigger(
    diff: str | None = typer.Option(None, "--diff", "-d", help="diff 文件路径"),
    stdin: bool = typer.Option(False, "--stdin", help="从标准输入读取 diff"),
    repo: str = typer.Option(..., "--repo", "-r", help="仓库标识，如 owner/repo"),
    api_url: str = typer.Option("http://127.0.0.1:8000", "--api-url", help="API 服务地址"),
    pr_id: int | None = typer.Option(None, "--pr", help="PR 编号（可选）"),
):
    """通过 API 触发审查任务（需服务已启动）。"""
    diff_content = _load_diff(diff, stdin)
    import httpx
    payload = {"repo": repo, "diff_content": diff_content}
    if pr_id is not None:
        payload["pr_id"] = pr_id
    with httpx.Client(timeout=30.0) as client:
        r = client.post(f"{api_url.rstrip('/')}/api/v1/review/trigger", json=payload)
    r.raise_for_status()
    data = r.json()
    typer.echo(f"任务已创建: task_id={data.get('task_id')}")
    typer.echo(f"查询状态: GET {api_url}/api/v1/review/tasks/{data.get('task_id')}")
    typer.echo(f"获取报告: GET {api_url}/api/v1/review/reports/{data.get('task_id')}")


if __name__ == "__main__":
    app()
