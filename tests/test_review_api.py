"""审查 API 端到端测试（TestClient，不启动真实 Worker）。"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "app" in data


def test_trigger_review_requires_diff(client: TestClient):
    # 无 API Key 时若未配置 api_keys 可通过；若配置了则 401
    r = client.post("/api/v1/review/trigger", json={"repo": "owner/repo"})
    # 400 缺少 diff_content
    assert r.status_code in (400, 401)
    if r.status_code == 400:
        assert "diff_content" in r.json().get("detail", "")


def test_trigger_review_with_diff(client: TestClient):
    r = client.post(
        "/api/v1/review/trigger",
        json={
            "repo": "owner/repo",
            "diff_content": "--- a/app.py\n+++ b/app.py\n@@ -0,0 +1,2 @@\n+def foo():\n+    pass\n",
        },
    )
    if r.status_code == 401:
        pytest.skip("API key required")
    assert r.status_code == 200
    data = r.json()
    assert "task_id" in data
    assert data["status"] == "pending"


def test_get_task_not_found(client: TestClient):
    r = client.get("/api/v1/review/tasks/nonexistent-task-id")
    if r.status_code == 401:
        pytest.skip("API key required")
    assert r.status_code == 404


def test_get_report_before_complete(client: TestClient):
    # 先触发一个任务
    r0 = client.post(
        "/api/v1/review/trigger",
        json={"repo": "x/y", "diff_content": "--- /dev/null\n+++ a.py\n@@ 0,0 +1,1 @@\n+x = 1\n"},
    )
    if r0.status_code == 401:
        pytest.skip("API key required")
    assert r0.status_code == 200
    task_id = r0.json()["task_id"]
    # 任务可能尚未完成，报告接口应返回 400 或 404
    r = client.get(f"/api/v1/review/reports/{task_id}")
    if r.status_code == 401:
        pytest.skip("API key required")
    assert r.status_code in (400, 404)
