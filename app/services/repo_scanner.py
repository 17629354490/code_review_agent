"""远程仓库扫描：从 GitHub 拉取代码并生成可供审查的 diff 风格内容。支持全量、最新提交增量、指定文件/目录。"""
import re
from typing import Any

import httpx

# 参与扫描的扩展名（可配置）
DEFAULT_EXTENSIONS = {".py", ".yaml", ".yml", ".md", ".txt", ".json", ".toml", ".cfg", ".ini"}
# 忽略的路径片段
SKIP_PATH_PARTS = {"__pycache__", ".git", "node_modules", ".venv", "venv", ".env", "dist", "build"}

# 扫描模式
ScanMode = str  # "full" | "latest_commit" | "paths"


def _parse_repo_url(repo_url: str) -> tuple[str, str]:
    """从 URL 解析 owner/repo。支持 https://github.com/owner/repo 或 owner/repo。"""
    repo_url = repo_url.strip().rstrip("/")
    if not repo_url:
        raise ValueError("repo_url 为空")
    # owner/repo 形式
    if re.match(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$", repo_url):
        return tuple(repo_url.split("/", 1))  # type: ignore
    # https://github.com/owner/repo 或 .git
    m = re.search(r"github\.com[/:]([^/]+)/([^/]+?)(?:\.git)?$", repo_url)
    if m:
        return m.group(1), m.group(2)
    raise ValueError(f"无法解析仓库地址: {repo_url}")


def _should_include(path: str, extensions: set[str] | None = None) -> bool:
    ext = extensions or DEFAULT_EXTENSIONS
    if any(part in path for part in SKIP_PATH_PARTS):
        return False
    from pathlib import Path
    return Path(path).suffix.lower() in ext


def fetch_tree(owner: str, repo: str, branch: str = "main", client: httpx.Client | None = None) -> list[dict[str, Any]]:
    """获取 GitHub 仓库的递归文件树。返回 tree 中 type=blob 的项。"""
    close = False
    if client is None:
        client = httpx.Client(timeout=30.0)
        close = True
    try:
        # 获取 branch 的 commit sha
        r = client.get(f"https://api.github.com/repos/{owner}/{repo}/branches/{branch}")
        if r.status_code == 404:
            # 可能是 default branch 叫 main 或 master
            r2 = client.get(f"https://api.github.com/repos/{owner}/{repo}")
            if r2.status_code != 200:
                r.raise_for_status()
            default_branch = r2.json().get("default_branch", "main")
            if default_branch != branch:
                return fetch_tree(owner, repo, default_branch, client)
            r.raise_for_status()
        r.raise_for_status()
        commit_sha = r.json()["commit"]["sha"]
        # 递归 tree
        r2 = client.get(f"https://api.github.com/repos/{owner}/{repo}/git/trees/{commit_sha}?recursive=1")
        r2.raise_for_status()
        tree = r2.json().get("tree") or []
        return [t for t in tree if t.get("type") == "blob"]
    finally:
        if close:
            client.close()


def fetch_file_content(owner: str, repo: str, branch: str, path: str, client: httpx.Client | None = None) -> str:
    """从 raw.githubusercontent.com 拉取单文件内容。"""
    close = False
    if client is None:
        client = httpx.Client(timeout=15.0)
        close = True
    try:
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
        r = client.get(url)
        r.raise_for_status()
        return r.text
    finally:
        if close:
            client.close()


def fetch_commit_info(
    owner: str, repo: str, ref: str = "HEAD", client: httpx.Client | None = None
) -> dict[str, str]:
    """
    获取指定 ref（分支名或 commit SHA）的 commit 信息。
    返回 {"sha": "...", "parent_sha": "..."}，若为首次提交则 parent_sha 为空。
    """
    close = False
    if client is None:
        client = httpx.Client(timeout=30.0)
        close = True
    try:
        r = client.get(f"https://api.github.com/repos/{owner}/{repo}/commits/{ref}")
        r.raise_for_status()
        data = r.json()
        sha = data["sha"]
        parents = data.get("parents") or []
        parent_sha = parents[0]["sha"] if parents else ""
        return {"sha": sha, "parent_sha": parent_sha}
    finally:
        if close:
            client.close()


def fetch_compare_diff(
    owner: str, repo: str, base_sha: str, head_sha: str, client: httpx.Client | None = None
) -> str:
    """
    获取 base...head 的 diff（Compare API），返回拼接后的 unified diff 文本。
    仅包含可审查的文本文件（有 patch 且扩展名在 DEFAULT_EXTENSIONS 内）。
    """
    close = False
    if client is None:
        client = httpx.Client(timeout=60.0)
        close = True
    try:
        r = client.get(
            f"https://api.github.com/repos/{owner}/{repo}/compare/{base_sha}...{head_sha}"
        )
        r.raise_for_status()
        data = r.json()
        files = data.get("files") or []
        parts: list[str] = []
        for f in files:
            patch = f.get("patch")
            if not patch or not isinstance(patch, str):
                continue
            path = f.get("filename") or ""
            if not _should_include(path, DEFAULT_EXTENSIONS):
                continue
            # API 返回的 patch 已是 unified diff，可直接拼接
            parts.append(f"--- a/{path}\n+++ b/{path}\n{patch}")
        return "\n".join(parts)
    finally:
        if close:
            client.close()


def fetch_commit_diff(
    owner: str, repo: str, ref: str = "HEAD", client: httpx.Client | None = None
) -> str:
    """
    获取「单个提交」相对其父提交的增量 diff（仅该次提交变更的文件）。
    ref 可为分支名（如 main）或 commit SHA；分支时表示该分支最新一次提交。
    """
    info = fetch_commit_info(owner, repo, ref, client)
    sha = info["sha"]
    parent_sha = info["parent_sha"]
    if not parent_sha:
        return ""  # 首次提交无 parent，无增量
    return fetch_compare_diff(owner, repo, parent_sha, sha, client)


def _path_matches(file_path: str, paths: list[str]) -> bool:
    """
    判断 file_path 是否被 paths 命中。
    paths 中元素为文件路径或目录路径；目录以 / 结尾或作为前缀匹配（如 app 或 app/ 匹配 app/main.py）。
    """
    norm_path = file_path.replace("\\", "/")
    for p in paths:
        p = p.strip().replace("\\", "/").rstrip("/")
        if not p:
            continue
        if p == norm_path:
            return True
        if norm_path.startswith(p + "/"):
            return True
    return False


def build_diff_from_paths(
    owner: str,
    repo: str,
    branch: str,
    paths: list[str],
    extensions: set[str] | None = None,
    max_file_lines: int = 500,
    client: httpx.Client | None = None,
) -> str:
    """
    仅拉取 paths 指定文件/目录下的文件，组装成 unified diff 风格（每个文件以「新增」形式）。
    paths 示例：["app/", "cli/main.py", "config"]。
    """
    blob_list = fetch_tree(owner, repo, branch, client)
    ext = extensions or DEFAULT_EXTENSIONS
    to_fetch = [
        b["path"]
        for b in blob_list
        if _should_include(b["path"], ext) and _path_matches(b["path"], paths)
    ]
    if not to_fetch:
        return ""
    parts: list[str] = []
    close = client is None
    if client is None:
        client = httpx.Client(timeout=20.0)
    try:
        for path in to_fetch:
            try:
                content = fetch_file_content(owner, repo, branch, path, client)
            except Exception:
                continue
            lines = content.splitlines()
            if len(lines) > max_file_lines:
                lines = lines[:max_file_lines]
                lines.append("... (truncated)")
            line_count = len(lines)
            part = f"--- /dev/null\n+++ {path}\n@@ 0,0 +1,{line_count} @@\n"
            part += "\n".join("+" + line for line in lines)
            parts.append(part)
        return "\n".join(parts)
    finally:
        if close:
            client.close()


def build_diff_from_tree(
    owner: str,
    repo: str,
    branch: str = "main",
    extensions: set[str] | None = None,
    max_files: int = 80,
    max_file_lines: int = 500,
) -> str:
    """
    根据仓库树拉取文件内容，组装成 unified diff 风格文本（便于 LLM 审查）。
    每个文件以「新增」形式呈现：--- /dev/null, +++ path, @@ 0,0 +1,N @@，行前加 +。
    """
    blob_list = fetch_tree(owner, repo, branch)
    to_fetch = [b["path"] for b in blob_list if _should_include(b["path"], extensions)][:max_files]
    ext = extensions or DEFAULT_EXTENSIONS
    parts: list[str] = []
    with httpx.Client(timeout=20.0) as client:
        for path in to_fetch:
            try:
                content = fetch_file_content(owner, repo, branch, path, client)
            except Exception:
                continue
            lines = content.splitlines()
            if len(lines) > max_file_lines:
                lines = lines[:max_file_lines]
                lines.append("... (truncated)")
            line_count = len(lines)
            part = f"--- /dev/null\n+++ {path}\n@@ 0,0 +1,{line_count} @@\n"
            part += "\n".join("+" + line for line in lines)
            parts.append(part)
    return "\n".join(parts)


def scan_repo_to_diff(
    repo_url: str,
    branch: str = "main",
    extensions: set[str] | None = None,
    max_files: int = 80,
    max_file_lines: int = 500,
    *,
    mode: ScanMode = "full",
    paths: list[str] | None = None,
    commit_ref: str | None = None,
) -> tuple[str, str]:
    """
    扫描远程仓库并返回 (diff_content, repo_slug)。

    - mode="full": 全量扫描（默认），拉取分支下所有符合扩展名的文件。
    - mode="latest_commit": 增量扫描，仅扫描「最新一次提交」或 commit_ref 指定提交的变更。
    - mode="paths": 仅扫描 paths 指定的文件/目录，如 ["app/", "cli/main.py"]。

    commit_ref: 仅在 mode="latest_commit" 时有效；为分支名（如 main）或 commit SHA，默认用 branch。
    """
    owner, repo = _parse_repo_url(repo_url)
    repo_slug = f"{owner}/{repo}"

    if mode == "latest_commit":
        ref = (commit_ref or branch).strip() or branch
        diff = fetch_commit_diff(owner, repo, ref=ref)
    elif mode == "paths":
        if not paths:
            diff = ""
        else:
            with httpx.Client(timeout=30.0) as client:
                diff = build_diff_from_paths(
                    owner=owner,
                    repo=repo,
                    branch=branch,
                    paths=paths,
                    extensions=extensions,
                    max_file_lines=max_file_lines,
                    client=client,
                )
    else:
        diff = build_diff_from_tree(
            owner=owner,
            repo=repo,
            branch=branch,
            extensions=extensions,
            max_files=max_files,
            max_file_lines=max_file_lines,
        )

    return diff, repo_slug
