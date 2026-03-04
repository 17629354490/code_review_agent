# 代码审查智能体 (Code Review Agent)

基于技术方案实现的代码审查智能体：支持通过 API / Webhook / CLI 触发审查，使用 LLM 对 diff 进行分析并生成结构化报告。

## 功能概览

- **API**：`POST /api/v1/review/trigger` 提交 diff 触发审查，`GET /api/v1/review/tasks/{id}` 查状态，`GET /api/v1/review/reports/{id}` 取报告
- **远程仓库扫描**：`POST /api/v1/review/scan-repo` 传入 `repo_url`（如 `https://github.com/owner/repo`）自动拉取代码并入队审查；CLI `scan-repo <repo_url>` 支持本地审查或调用 API
- **Webhook**：`POST /api/v1/webhook/github`、`/api/v1/webhook/gitlab` 接收 PR/MR 事件（MVP 仅创建任务，不拉取 diff）
- **CLI**：本地直接调用 LLM 审查 diff，或向已启动的服务发起触发请求
- **规则**：`config/rules.yaml` 配置审查维度，供 LLM Prompt 使用
- **报告**：Markdown + JSON 落盘到 `data/reports/{task_id}/`

## 环境要求

- Python 3.11+
- 使用 OpenAI 兼容 API（OpenAI / Azure / Ollama 等），需配置 API Key 或 Base URL

## 安装与配置

```bash
cd code_review_agent
pip install -r requirements.txt
```

复制环境变量并编辑：

```bash
cp .env.example .env
```

`.env` 示例：

```env
# LLM（必填其一）
OPENAI_API_KEY=sk-xxx
# 或使用 Ollama 等兼容端点
LLM_BASE_URL=http://127.0.0.1:11434/v1
LLM_MODEL=llama3
LLM_API_KEY=ollama

# 可选：API 鉴权（多个 key 逗号分隔）
API_KEYS=your-secret-key

# 可选：Webhook 签名
WEBHOOK_GITHUB_SECRET=your-github-webhook-secret
WEBHOOK_GITLAB_SECRET=your-gitlab-token
```

## 运行

### 启动 API 服务（含后台 Worker）

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- 健康检查：`GET http://127.0.0.1:8000/health`
- 文档：`http://127.0.0.1:8000/docs`

### CLI 本地审查（不启动服务）

```bash
# 对文件中的 diff 审查，结果打印到 stdout
python -m cli.main review --diff path/to/file.diff --repo my/repo

# 从 stdin 读 diff
git diff main -- myfile.py | python -m cli.main review --stdin --repo my/repo

# 指定输出文件
python -m cli.main review --diff change.diff -o report.md
```

### CLI 触发远程审查

```bash
# 先启动 API 服务，再执行
python -m cli.main trigger --diff change.diff --repo owner/repo --pr 42
```

### CLI 扫描远程仓库（如 report_agent）

支持三种模式：`full` 全量、`latest_commit` 仅最新一次提交增量、`paths` 仅指定文件/目录。

```bash
# 全量扫描
python -m cli.main scan-repo https://github.com/17629354490/report_agent -o report.md

# 仅扫描最新一次提交的变更（增量）
python -m cli.main scan-repo https://github.com/17629354490/report_agent --mode latest_commit -o report.md

# 仅扫描指定目录/文件
python -m cli.main scan-repo https://github.com/17629354490/report_agent --mode paths --paths "app/,cli/main.py" -o report.md

# 通过已启动的 API 服务扫描（不占用本地 LLM）
python -m cli.main scan-repo https://github.com/17629354490/report_agent --api-url http://127.0.0.1:8000
```

## 测试

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

详见 `tests/`：报告服务、审查 API、LLM 解析、仓库扫描器。对 [report_agent](https://github.com/17629354490/report_agent) 的扫描报告与更多测试示例见 `docs/report_agent_scan_report.md`。

## 项目结构

```
code_review_agent/
  app/
    main.py           # FastAPI 入口
    config.py        # 配置
    worker.py        # 后台任务 Worker
    api/             # 路由与鉴权
    core/            # 数据模型
    services/        # 规则、LLM、报告、编排
    storage/        # 任务存储（内存）
  cli/
    main.py          # Typer CLI
  config/
    rules.yaml       # 规则配置
  data/
    reports/         # 报告输出目录（自动创建）
  requirements.txt
  README.md
  .env.example
```

## 开发说明

- 规则与 Prompt 在 `app/services/rule_service.py` 与 `app/services/llm_engine.py` 中，可按需扩展。
- 任务存储当前为内存，重启后丢失；可后续改为 SQLite/Redis。
- Webhook 当前不拉取远程 diff，需在 `app/api/v1/webhook.py` 中接入 GitHub/GitLab API 实现。

## 许可证

MIT，详见 [LICENSE](LICENSE)。
