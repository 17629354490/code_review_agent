"""仓库扫描器单元测试。"""
import pytest

from app.services.repo_scanner import (
    _parse_repo_url,
    _path_matches,
    _should_include,
    fetch_tree,
    build_diff_from_tree,
    scan_repo_to_diff,
)


def test_parse_repo_url():
    assert _parse_repo_url("https://github.com/17629354490/report_agent") == ("17629354490", "report_agent")
    assert _parse_repo_url("https://github.com/owner/repo.git") == ("owner", "repo")
    assert _parse_repo_url("owner/repo") == ("owner", "repo")


def test_parse_repo_url_invalid():
    with pytest.raises(ValueError, match="无法解析"):
        _parse_repo_url("https://gitlab.com/other/repo")
    with pytest.raises(ValueError, match="为空"):
        _parse_repo_url("")


def test_should_include():
    assert _should_include("app/main.py") is True
    assert _should_include("config/rules.yaml") is True
    assert _should_include("app/__pycache__/x.py") is False
    assert _should_include(".git/config") is False
    assert _should_include("readme.MD") is True
    assert _should_include("foo.go") is False  # 默认不包含 .go


def test_path_matches():
    assert _path_matches("app/main.py", ["app/"]) is True
    assert _path_matches("app/main.py", ["app"]) is True
    assert _path_matches("app/services/foo.py", ["app/"]) is True
    assert _path_matches("cli/main.py", ["cli/main.py"]) is True
    assert _path_matches("config/rules.yaml", ["config"]) is True
    assert _path_matches("app/main.py", ["cli/"]) is False
    assert _path_matches("app/main.py", []) is False
    assert _path_matches("app/main.py", ["app/", "cli/main.py"]) is True


@pytest.mark.skipif(True, reason="需要网络，CI 可设为 False")
def test_fetch_tree_live():
    tree = fetch_tree("17629354490", "report_agent", "main")
    assert isinstance(tree, list)
    paths = [t["path"] for t in tree]
    assert any("app/main.py" in p or p == "app/main.py" for p in paths)


def test_scan_repo_to_diff_integration():
    """需要网络；仅在有网时跑。"""
    pytest.importorskip("httpx")
    try:
        diff, slug = scan_repo_to_diff(
            "https://github.com/17629354490/report_agent",
            branch="main",
            max_files=3,
            max_file_lines=20,
        )
    except Exception as e:
        pytest.skip(f"网络或 GitHub 不可用: {e}")
    assert slug == "17629354490/report_agent"
    assert "+++" in diff
    assert "report_agent" in diff or "app/" in diff or "README" in diff


def test_scan_repo_to_diff_mode_paths_integration():
    """mode=paths 时仅拉取指定目录/文件；需要网络。"""
    pytest.importorskip("httpx")
    try:
        diff, slug = scan_repo_to_diff(
            "https://github.com/17629354490/report_agent",
            branch="main",
            mode="paths",
            paths=["app/"],
            max_file_lines=15,
        )
    except Exception as e:
        pytest.skip(f"网络或 GitHub 不可用: {e}")
    assert slug == "17629354490/report_agent"
    assert "app/" in diff
    assert "+++" in diff


def test_scan_repo_to_diff_mode_latest_commit_integration():
    """mode=latest_commit 时仅拉取最新一次提交的 diff；需要网络。"""
    pytest.importorskip("httpx")
    try:
        diff, slug = scan_repo_to_diff(
            "https://github.com/17629354490/report_agent",
            branch="main",
            mode="latest_commit",
        )
    except Exception as e:
        pytest.skip(f"网络或 GitHub 不可用: {e}")
    assert slug == "17629354490/report_agent"
    # 可能为空（该提交无变更或无可审查文件）或包含 diff
    assert isinstance(diff, str)
