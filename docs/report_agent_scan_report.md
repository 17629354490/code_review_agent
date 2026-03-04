# report_agent 仓库扫描报告

**仓库**: [17629354490/report_agent](https://github.com/17629354490/report_agent)  
**类型**: 报表智能体（Text2SQL）  
**扫描方式**: 代码审查智能体远程扫描 + 静态分析  
**日期**: 2025-03-04  

---

## 1. 仓库概览

| 项 | 说明 |
|----|------|
| 仓库地址 | https://github.com/17629354490/report_agent |
| 主要语言 | Python 100% |
| 环境要求 | Python 3.11+，SQLite/MySQL/PostgreSQL，OpenAI 兼容 API |
| 功能 | 自然语言 → SQL，安全执行 SELECT，结果表格 + Markdown，审计日志 |

---

## 2. 项目结构（静态扫描）

```
report_agent/
  app/
    main.py              # FastAPI 入口
    config.py             # Pydantic Settings（数据库、LLM、Text2SQL 限制）
    core/
      models.py           # QueryRequest / QueryResponse / QueryError
    api/v1/
      query.py            # POST /query 自然语言查询
    services/
      schema_service.py   # 拉取表结构
      llm_sql_engine.py   # NL → SQL
      executor.py         # 校验（仅 SELECT）+ 执行 + 限行
      report_formatter.py # 结果转 Markdown
      orchestrator.py     # 编排：Schema → LLM → 执行 → 格式化 → 审计
    storage/
      audit.py            # 审计 audit.jsonl
  cli/
    main.py               # Typer CLI：query
  scripts/
    init_sample_db.py     # 初始化示例 SQLite
  data/
    report.db             # 默认 SQLite
    audit.jsonl           # 审计日志
  config: .env, requirements.txt, run.py
```

---

## 3. 依赖与配置（requirements.txt）

- **Web**: fastapi, uvicorn, httpx, python-multipart  
- **LLM**: openai  
- **数据库**: pymysql, psycopg2-binary, sqlalchemy  
- **配置**: pydantic, pydantic-settings, pyyaml, typer, python-dotenv  

---

## 4. 安全与质量要点（静态分析）

| 维度 | 结论 |
|------|------|
| SQL 安全 | executor 仅允许 SELECT，黑名单危险关键字，可配置表白名单、限行、超时 |
| 配置 | 敏感信息通过 .env 管理，未发现硬编码密钥 |
| 错误处理 | 查询失败返回 QueryError，审计记录 status=error |
| 接口 | 可选 API Keys，CORS 已配置 |

---

## 5. 使用代码审查智能体进行完整扫描

本报告由「代码审查智能体」的**远程仓库扫描**能力生成结构概览。支持三种扫描模式：

| 模式 | 说明 |
|------|------|
| **full** | 全量：拉取分支下所有符合扩展名的文件（.py/.yaml 等） |
| **latest_commit** | 增量：仅扫描「最新一次提交」或指定 commit 的变更 diff |
| **paths** | 指定范围：仅扫描传入的文件/目录，如 `app/`、`cli/main.py` |

### 5.1 CLI 本地扫描（拉取仓库 + 本地 LLM 审查）

需配置 `.env` 中的 `OPENAI_API_KEY` 或 `LLM_BASE_URL`/`LLM_MODEL`：

```bash
cd code_review_agent
# 全量
python -m cli.main scan-repo https://github.com/17629354490/report_agent -o report.md

# 仅最新一次提交的增量
python -m cli.main scan-repo https://github.com/17629354490/report_agent --mode latest_commit -o report.md

# 仅指定目录/文件
python -m cli.main scan-repo https://github.com/17629354490/report_agent --mode paths --paths "app/,cli/main.py" -o report.md
```

指定分支与语言提示：

```bash
python -m cli.main scan-repo https://github.com/17629354490/report_agent --branch main --language python -o report.md
```

### 5.2 通过 API 扫描（服务已启动时）

```bash
# 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 全量
curl -X POST "http://127.0.0.1:8000/api/v1/review/scan-repo" \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/17629354490/report_agent", "branch": "main"}'

# 仅最新一次提交
curl -X POST "http://127.0.0.1:8000/api/v1/review/scan-repo" \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/17629354490/report_agent", "branch": "main", "mode": "latest_commit"}'

# 仅 app/ 与 cli/
curl -X POST "http://127.0.0.1:8000/api/v1/review/scan-repo" \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/17629354490/report_agent", "branch": "main", "mode": "paths", "paths": ["app/", "cli/"]}'

# 返回 task_id 后轮询状态与报告
curl "http://127.0.0.1:8000/api/v1/review/tasks/{task_id}"
curl "http://127.0.0.1:8000/api/v1/review/reports/{task_id}?format=markdown"
```

或使用 CLI 调用 API（不占用本地 LLM）：

```bash
python -m cli.main scan-repo https://github.com/17629354490/report_agent --api-url http://127.0.0.1:8000
python -m cli.main scan-repo https://github.com/17629354490/report_agent -m latest_commit --api-url http://127.0.0.1:8000
python -m cli.main scan-repo https://github.com/17629354490/report_agent -m paths -p "app/,cli/" --api-url http://127.0.0.1:8000
```

---

## 6. 测试示例

### 6.1 代码审查智能体（本仓库）测试

见项目根目录 `tests/`：

- **报告服务**: `pytest tests/test_report_service.py -v`
- **审查 API**: `pytest tests/test_review_api.py -v`
- **LLM 解析**: `pytest tests/test_llm_engine.py -v`
- **仓库扫描**: `pytest tests/test_repo_scanner.py -v`

### 6.2 report_agent 接口测试示例

**健康检查**

```bash
curl -s http://127.0.0.1:8000/health
# 期望: {"status":"ok","app":"report-agent"}
```

**自然语言查询（需先初始化 DB 与配置 LLM）**

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{"question": "订单表有多少条记录"}'
```

**CLI 查询**

```bash
cd report_agent
python -m cli.main query "查询订单表前10条"
python -m cli.main query "订单金额汇总" -o result.md
```

---

## 7. 总结

- **report_agent** 结构清晰，Text2SQL 流程完整，SQL 执行有校验与限行，适合作为报表类智能体参考实现。  
- 使用 **代码审查智能体** 的 `scan-repo`（CLI 或 API）可对任意 GitHub 仓库做一次“拉取 + 审查”，并生成 Markdown/JSON 报告。  
- 上述测试示例覆盖健康检查、审查 API、报告服务、LLM 解析与仓库扫描，可按需扩展。
