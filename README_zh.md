# FastAPI Boilerplate

[![CI](https://github.com/Momoyeyu/fastapi-boilerplate/actions/workflows/ci.yml/badge.svg)](https://github.com/Momoyeyu/fastapi-boilerplate/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.112+-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

[中文文档](README_zh.md) | [English](README.md)

生产就绪的 FastAPI 脚手架，提供 4 层模块架构、JWT 认证、自动迁移、结构化日志、Docker 支持和 CI/CD。专为 AI 编程代理快速、规范地搭建后端项目而设计。

> **AI 编程代理**：请参阅 [CLAUDE.md](CLAUDE.md) 获取代理工作流指南。

## 快速开始

**前置要求**: Python 3.12+、[uv](https://github.com/astral-sh/uv)、Docker（可选）

```bash
git clone https://github.com/Momoyeyu/fastapi-boilerplate.git
cd fastapi-boilerplate
cp .env.example .env          # 配置环境变量
uv sync                       # 安装依赖
docker-compose up -d db redis # 启动 PostgreSQL + Redis
make run                      # 迁移数据库 + 启动开发服务器 localhost:8000
```

验证：`http://localhost:8000/docs`（Swagger UI，设置 `DEBUG=true` 可免认证访问）

完整 Docker 部署：`docker-compose up --build`

## 项目结构

```
src/
├── main.py                 # 应用工厂，路由和中间件注册
├── conf/                   # 配置（pydantic-settings、SQLAlchemy、Loguru、Redis）
├── common/                 # 响应信封 (resp.py)、错误工厂 (erri.py)、异常处理器 (trap.py)
├── middleware/              # JWT 认证中间件 + 请求/响应日志
├── auth/                   # 认证模块（登录、注册、Token、密码、验证码）
├── user/                   # 用户模块（个人信息）
└── invitation/             # 邀请码模块

migration/                  # Alembic 迁移（`make run` 时自动执行）
tests/
├── unit/                   # 隔离的 service 逻辑测试（monkeypatch mock）
├── integration/            # 完整请求/响应链路测试（SQLite + FakeRedis）
└── cfg.yml                 # 覆盖率配置
```

## 模块架构

每个功能模块遵循 **4 层模式**，位于 `src/{module}/`：

| 层级 | 文件 | 职责 |
|------|------|------|
| Model | `model.py` | SQLAlchemy ORM 模型 + 异步数据库查询函数 |
| DTO | `dto.py` | Pydantic 请求/响应模型（无数据库依赖） |
| Service | `{domain}.py` | 业务逻辑、校验、抛出 `BusinessError` |
| Handler | `handler.py` | FastAPI `APIRouter`，调用 service，返回 `Response` |

**数据流**: Handler -> Service -> Model

Service 文件按业务领域命名（如 `token.py`、`password.py`），而非统一的 `service.py`。参考实现：`src/user/`（最小化模块）、`src/auth/`（多 service 模块）。

### 添加新模块

1. 创建 `src/{module}/` 目录，包含 `__init__.py`、`model.py`、`dto.py`、`{domain}.py`、`handler.py`
2. `model.py` — 定义 SQLAlchemy ORM 模型 + 异步查询函数（使用 `async with AsyncSessionLocal()` 的 try/commit/rollback 模式）
3. `dto.py` — 定义 Pydantic 请求/响应模型
4. `{domain}.py` — 实现异步业务逻辑，调用 model 函数，出错时抛出 `erri.*`
5. `handler.py` — 定义 `APIRouter` 路由，`await` service 调用，返回 `ok(data=...)`
6. 在 `src/main.py` 的 `init_routers()` 中注册路由
7. 在 `migration/alembic/env.py` 中导入 model（用于自动迁移）
8. 按 `test_{module}_{domain}.py` 命名规范添加测试

## 核心模式

### 响应信封

所有接口通过 `common.resp` 返回标准化 `Response`：

```python
from common.resp import ok
return ok(data={...})           # 成功

from common import erri
raise erri.bad_request("...")   # 40000
raise erri.unauthorized("...")  # 40100
raise erri.forbidden("...")     # 40300
raise erri.not_found("...")     # 40400
raise erri.internal("...")      # 50000
```

### 认证

- JWT 中间件（`src/middleware/auth.py`）默认对所有路由进行 Token 校验
- `@auth.exempt` — 跳过认证
- `auth.get_username(request)` — 获取当前用户
- 认证接口：`POST /api/v1/auth/login`、`POST /api/v1/auth/token/refresh`、`POST /api/v1/auth/logout`

### 配置管理

在 `src/conf/config.py` 中通过 `pydantic-settings` 定义，从 `.env` 加载。所有可用变量参见 [`.env.example`](.env.example)。使用方式：`from conf.config import settings`

### 日志

基于 Loguru（`src/conf/logging.py`）。控制台输出 + 每日轮转文件日志（`logs/`）。请求日志中间件自动记录方法、路径、状态码、耗时，并对敏感字段脱敏。

## 开发

```bash
make run       # 迁移数据库 + 启动开发服务器（uvicorn 热重载）
make test      # 运行单元测试 + 集成测试
make lint      # ruff check + format
make migrate   # 手动运行 Alembic 迁移
make deploy    # 部署应用
```

修改模型后生成新迁移：
```bash
PYTHONPATH="src:." uv run alembic -c migration/alembic.ini revision --autogenerate -m "description"
```

### 测试

测试遵循 `test_{module}_{domain}.py` 命名规范，与 `src/{module}/{domain}.py` 一一对应。

| 层级 | 目的 | 依赖方式 |
|------|------|----------|
| Unit (`tests/unit/`) | 隔离测试单个 service 函数 | 所有外部调用通过 `monkeypatch` mock |
| Integration (`tests/integration/`) | 完整 API 端点测试 | SQLite + FakeRedis + mock 邮件 |
| Workflow (`tests/integration/test_workflow.py`) | 跨模块用户旅程测试 | 与 Integration 相同 |

核心 fixtures（`integration/conftest.py`）：`client`、`register_and_verify`、`auth_header`、`mock_email`、`session`。

### CI/CD

- **CI**（`.github/workflows/ci.yml`）：lint -> test -> 覆盖率检查（仅 PR）。在 `master` 分支 push/PR 时触发。
- **CD**（`.github/workflows/cd.yml.example`）：Docker 构建 + SSH 部署模板。复制为 `cd.yml` 并配置 secrets 即可启用。

## 技术栈

FastAPI 0.112+ | Python 3.12+ | SQLAlchemy 2.0（异步） | PostgreSQL 16 | Redis 7 | PyJWT | Alembic | pydantic-settings | Loguru | uv | Ruff | pytest | Docker Compose | GitHub Actions

## 许可证

MIT License — 详见 [LICENSE](LICENSE)。
