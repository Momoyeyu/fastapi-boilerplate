# FastAPI Boilerplate

[![CI](https://github.com/Momoyeyu/fastapi-boilerplate/actions/workflows/ci.yml/badge.svg)](https://github.com/Momoyeyu/fastapi-boilerplate/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.112+-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

[中文文档](README_zh.md) | [English](README.md)

生产就绪的 FastAPI 脚手架，专为 AI 编程代理快速、规范地搭建后端项目而设计。提供标准的 4 层模块架构、JWT 认证、自动迁移、结构化日志、Docker 支持和 CI/CD 流水线，让代理（和人类）专注于业务逻辑。

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

**验证**: `http://localhost:8000/docs`（Swagger UI，设置 `DEBUG=true` 可免认证访问）

**Docker 运行**（完整栈）：
```bash
docker-compose up --build
```

## 项目结构

```
fastapi-boilerplate/
├── src/                        # 应用源码
│   ├── main.py                 # 应用工厂，路由和中间件注册
│   ├── conf/
│   │   ├── config.py           # pydantic-settings 配置（加载 .env）
│   │   ├── db.py               # SQLAlchemy 引擎
│   │   └── logging.py          # Loguru 配置
│   ├── common/
│   │   ├── resp.py             # 响应信封和状态码
│   │   ├── erri.py             # BusinessError 工厂（bad_request、not_found 等）
│   │   └── trap.py             # 全局异常处理器
│   ├── middleware/
│   │   ├── auth.py             # JWT 认证中间件 + @auth.exempt 装饰器
│   │   └── logging.py          # 请求/响应日志中间件
│   ├── auth/                   # 认证模块（登录、刷新、登出）
│   ├── user/                   # 用户模块（个人信息、注册）
│   └── invitation/             # 邀请码模块
├── migration/
│   ├── runner.py               # 迁移执行接口
│   └── alembic/                # Alembic 环境和版本脚本
├── tests/
│   ├── unit/                   # 单元测试（mock 依赖）
│   ├── integration/            # 集成测试（SQLite 内存数据库）
│   │   └── conftest.py         # 测试 fixtures（TestClient、FakeRedis、测试 DB）
│   └── cfg.yml                 # 测试覆盖率配置
├── scripts/                    # 开发任务脚本
├── .env.example                # 环境变量模板
├── docker-compose.yml          # App + PostgreSQL + Redis
├── Makefile                    # 开发命令
├── pyproject.toml              # 依赖和工具配置
└── CLAUDE.md                   # 代理工作流指南
```

## 模块架构

每个功能模块遵循 4 层模式，位于 `src/{module}/`：

| 层级 | 文件 | 职责 |
|------|------|------|
| **Model** | `model.py` | SQLModel 表类 + 数据库查询函数 |
| **DTO** | `dto.py` | Pydantic 请求/响应模型（无数据库依赖） |
| **Service** | `service.py` | 业务逻辑、校验、抛出 `BusinessError` |
| **Handler** | `handler.py` | FastAPI `APIRouter`，调用 service，返回 `Response` |

**数据流**: Handler（解析请求） -> Service（校验 + 编排） -> Model（数据库操作）

**参考实现**: `src/user/` 是一个完整的示例模块。

### 添加新模块

1. 创建 `src/{module}/` 目录，包含 `__init__.py`、`model.py`、`dto.py`、`service.py`、`handler.py`

2. **model.py** — 定义表和查询：
```python
from datetime import UTC, datetime
from sqlmodel import Field, Session, SQLModel, select
from conf.db import engine

class Product(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    price: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

def create_product(name: str, price: float) -> Product | None:
    product = Product(name=name, price=price)
    with Session(engine) as session:
        try:
            session.add(product)
            session.commit()
            session.refresh(product)
        except Exception:
            session.rollback()
            return None
    return product

def get_product(product_id: int) -> Product | None:
    with Session(engine) as session:
        return session.get(Product, product_id)
```

3. **dto.py** — 请求/响应模型：
```python
from pydantic import BaseModel

class ProductCreateRequest(BaseModel):
    name: str
    price: float

class ProductResponse(BaseModel):
    id: int
    name: str
    price: float
```

4. **service.py** — 业务逻辑和错误处理：
```python
from common import erri
from product import model

def create_product(name: str, price: float) -> model.Product:
    product = model.create_product(name, price)
    if not product:
        raise erri.internal("Create product failed")
    return product

def get_product(product_id: int) -> model.Product:
    product = model.get_product(product_id)
    if not product:
        raise erri.not_found("Product not found")
    return product
```

5. **handler.py** — 路由：
```python
from fastapi import APIRouter
from common.resp import Response, ok
from product import dto, service

router = APIRouter(prefix="/product", tags=["product"])

@router.post("")
async def create_product(body: dto.ProductCreateRequest) -> Response:
    product = service.create_product(body.name, body.price)
    return ok(data=dto.ProductResponse(**product.__dict__).model_dump())

@router.get("/{product_id}")
async def get_product(product_id: int) -> Response:
    product = service.get_product(product_id)
    return ok(data=dto.ProductResponse(**product.__dict__).model_dump())
```

6. **注册路由**，在 `src/main.py` 的 `init_routers()` 中：
```python
from product.handler import router as product_router
_app.include_router(product_router)
```

7. **导入模型**，在 `migration/alembic/env.py` 中（用于自动迁移）：
```python
from product.model import Product  # noqa: F401
```

8. **添加测试**：`tests/unit/test_{module}_service.py` 和 `tests/integration/test_{module}_api.py`

## 核心模式

### 响应信封

所有接口返回标准化 `Response`：
```python
from common.resp import Response, ok

# 成功
return ok(data={"key": "value"})
return ok(message="Operation completed")

# 错误 — 抛出 BusinessError，trap.py 自动转换
from common import erri
raise erri.bad_request("Invalid input")     # code 40000
raise erri.unauthorized("Login required")   # code 40100
raise erri.forbidden("No permission")       # code 40300
raise erri.not_found("Resource not found")  # code 40400
raise erri.internal("Server error")         # code 50000
```

### 认证

- JWT 中间件位于 `src/middleware/auth.py`，默认对所有路由进行 token 校验
- 使用 `@auth.exempt` 装饰器跳过认证
- 获取当前用户：`username = auth.get_username(request)`
- 认证接口：`POST /auth/login`、`POST /auth/token/refresh`、`POST /auth/logout`

### 数据库事务

```python
# model.py 中的标准模式
with Session(engine) as session:
    try:
        session.add(obj)
        session.commit()
        session.refresh(obj)
    except Exception:
        session.rollback()
        return None  # service 层将 None 转换为 BusinessError
```

### 配置管理

在 `src/conf/config.py` 中通过 `pydantic-settings` 定义，从 `.env` 加载：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEBUG` | `false` | 启用调试模式（免认证访问文档） |
| `DB_HOST` | `localhost` | PostgreSQL 主机 |
| `DB_PORT` | `5432` | PostgreSQL 端口 |
| `DB_USER` | `postgres` | PostgreSQL 用户 |
| `DB_PASSWORD` | `postgres` | PostgreSQL 密码 |
| `DB_NAME` | `fastapi-boilerplate` | PostgreSQL 数据库 |
| `REDIS_HOST` | `localhost` | Redis 主机 |
| `REDIS_PORT` | `6379` | Redis 端口 |
| `REDIS_DB` | `0` | Redis 数据库编号 |
| `PASSWORD_SALT` | `Momoyeyu` | 密码哈希盐值（生产环境必须修改） |
| `JWT_SECRET` | `Momoyeyu` | JWT 签名密钥（生产环境必须修改） |
| `JWT_ALGORITHM` | `HS256` | JWT 算法 |
| `JWT_EXPIRE_SECONDS` | `3600` | Access Token 过期时间 |
| `REFRESH_TOKEN_EXPIRE_SECONDS` | `604800` | Refresh Token 过期时间（7 天） |
| `VERIFICATION_CODE_EXPIRE_SECONDS` | `300` | 验证码过期时间 |
| `REQUIRE_INVITATION_CODE` | `false` | 注册时是否需要邀请码 |

使用方式：`from conf.config import settings`

### 日志

在 `src/conf/logging.py` 中通过 Loguru 配置。输出到控制台（彩色）和 `logs/backend_{date}.log`（每日轮转、保留 7 天、zip 压缩）。

```python
from loguru import logger
logger.info("User logged in", user_id=123)
```

请求日志中间件（`src/middleware/logging.py`）自动记录方法、路径、状态码、耗时，并对敏感字段（`password`、`authorization`、`access_token` 等）脱敏。

## 开发命令

```bash
make run       # 迁移数据库 + 启动开发服务器（uvicorn 热重载）
make test      # 运行单元测试 + 集成测试
make lint      # ruff check + format
make migrate   # 手动运行 Alembic 迁移
make deploy    # 部署应用
```

### 数据库迁移

- **自动**：`make run` 启动前自动运行迁移
- **手动**：`make migrate`
- **生成新迁移**（修改模型后）：
  ```bash
  PYTHONPATH="src:." uv run alembic -c migration/alembic.ini revision --autogenerate -m "description"
  ```

### 测试

```bash
make test                          # 所有测试
uv run pytest tests/unit -v        # 仅单元测试
uv run pytest tests/integration -v # 仅集成测试
```

- 单元测试通过 `monkeypatch` mock 依赖
- 集成测试使用 SQLite 内存数据库 + FakeRedis（见 `tests/integration/conftest.py`）
- CI 在 PR 中检查增量覆盖率（阈值 80%，配置于 `tests/cfg.yml`）

### CI/CD

**CI**（`.github/workflows/ci.yml`）：lint -> test -> 覆盖率检查（仅 PR）。在 `master` 分支 push/PR 时触发。

**CD**（`.github/workflows/cd.yml.example`）：Docker 构建 + SSH 部署模板。复制为 `cd.yml` 并配置 secrets 即可启用。

## 技术栈

| 组件 | 技术 |
|------|------|
| 框架 | FastAPI 0.112+ |
| Python | 3.12+ |
| ORM | SQLModel（SQLAlchemy + Pydantic） |
| 数据库 | PostgreSQL 16 |
| 缓存 | Redis 7 |
| 认证 | PyJWT（Access + Refresh Token） |
| 迁移 | Alembic |
| 配置 | pydantic-settings |
| 日志 | Loguru |
| 包管理 | uv |
| 代码检查 | Ruff |
| 测试 | pytest |
| 容器 | Docker Compose |
| CI/CD | GitHub Actions |

## 许可证

MIT License — 详见 [LICENSE](LICENSE)。
