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


@app.command()
def scan_repo(
    repo_url: str = typer.Argument(..., help="仓库地址，如 https://github.com/owner/repo"),
    branch: str = typer.Option("main", "--branch", "-b", help="分支名"),
    mode: str = typer.Option(
        "full",
        "--mode", "-m",
        help="扫描模式：full 全量 | latest_commit 仅最新一次提交 | paths 仅指定文件/目录",
    ),
    paths: str | None = typer.Option(
        None,
        "--paths", "-p",
        help="mode=paths 时必填，逗号分隔，如 app/,cli/main.py,config",
    ),
    commit_ref: str | None = typer.Option(
        None,
        "--commit", "-c",
        help="mode=latest_commit 时可选，指定分支或 commit SHA，默认用 branch",
    ),
    output: str | None = typer.Option(None, "--output", "-o", help="报告输出路径（默认打印到 stdout）"),
    api_url: str | None = typer.Option(None, "--api-url", help="若指定则通过 API 触发，否则本地拉取+审查"),
    language: str = typer.Option("", "--language", "-l", help="语言提示，如 python"),
):
    """扫描远程 GitHub 仓库并生成代码审查报告（支持全量、最新提交增量、指定文件/目录）。"""
    from app.services.repo_scanner import scan_repo_to_diff
    from app.services.llm_engine import get_llm_engine
    from app.services.report_service import get_report_service

    path_list: list[str] | None = None
    if mode == "paths":
        if not paths or not paths.strip():
            typer.echo("mode=paths 时请指定 --paths，如 -p app/,cli/main.py", err=True)
            raise typer.Exit(1)
        path_list = [x.strip() for x in paths.split(",") if x.strip()]

    kwargs = dict(repo_url=repo_url, branch=branch, mode=mode, paths=path_list, commit_ref=commit_ref)

    if api_url:
        import httpx
        typer.echo("正在拉取仓库并提交到 API...", err=True)
        try:
            diff_content, repo_slug = scan_repo_to_diff(**kwargs)
        except Exception as e:
            typer.echo(f"拉取仓库失败: {e}", err=True)
            raise typer.Exit(1)
        payload = {"repo_url": repo_url, "branch": branch, "mode": mode}
        if path_list is not None:
            payload["paths"] = path_list
        if commit_ref:
            payload["commit_ref"] = commit_ref
        with httpx.Client(timeout=60.0) as client:
            r = client.post(
                f"{api_url.rstrip('/')}/api/v1/review/scan-repo",
                json=payload,
            )
        r.raise_for_status()
        data = r.json()
        typer.echo(f"任务已创建: task_id={data.get('task_id')}")
        typer.echo(f"查询状态: GET {api_url}/api/v1/review/tasks/{data.get('task_id')}")
        typer.echo(f"获取报告: GET {api_url}/api/v1/review/reports/{data.get('task_id')}")
        return
    typer.echo("正在拉取仓库...", err=True)
    try:
        diff_content, repo_slug = scan_repo_to_diff(**kwargs)
    except Exception as e:
        typer.echo(f"拉取仓库失败: {e}", err=True)
        raise typer.Exit(1)
    if not diff_content.strip():
        typer.echo("未获取到可审查内容（该模式/路径下无匹配文件）。", err=True)
        raise typer.Exit(1)
    typer.echo("正在审查...", err=True)
    engine = get_llm_engine()
    report_svc = get_report_service()
    issues = engine.review_sync(diff_content, language_hint=language or "python")
    report = report_svc.build_report(task_id="scan-repo", repo=repo_slug, issues=issues)
    md = report.raw_markdown or "未发现需要报告的问题。"
    if output:
        Path(output).write_text(md, encoding="utf-8")
        typer.echo(f"报告已写入: {output}", err=True)
    else:
        print(md)


if __name__ == "__main__":
    app()
