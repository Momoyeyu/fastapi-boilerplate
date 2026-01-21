# FastAPI Boilerplate (脚手架)

[![CI](https://github.com/yourusername/fastapi-boilerplate/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/fastapi-boilerplate/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.112+-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

[中文文档](README_zh.md) | [English](README.md)

这是一个现代化的、生产就绪的 FastAPI 脚手架，旨在帮助你快速启动后端开发。本项目提供了坚实的基础架构，集成了项目结构、数据库管理、身份验证、测试和 CI/CD 流水线的最佳实践——让你可以专注于业务逻辑的开发。

## ✨ 特性 (Features)

-   **现代技术栈**: 基于 **FastAPI** (Python 3.12+) 构建，提供高性能 API 服务。
-   **ORM 与数据库**: 使用 **SQLModel** (SQLAlchemy + Pydantic) 配合 **PostgreSQL**。
-   **自动迁移**: 集成 **Alembic**，支持服务启动时自动同步数据库表结构。
-   **身份验证**: 基于 JWT 的身份验证中间件，包含安全的密码哈希处理。
-   **依赖管理**: 使用 **uv** 进行极速的 Python 包管理。
-   **Docker 支持**: 提供完整的 **Docker Compose** 配置，支持本地开发和容器化部署。
-   **CI/CD 流水线**: GitHub Actions 工作流，包含静态检查和自动化测试。
-   **代码质量**: 使用 **ruff** 进行代码检查与格式化，**mypy** 进行类型检查。
-   **清晰架构**: 模块化的 `src/` 目录结构，分离关注点 (Handler, Service, Model, DTO)。

## 📂 项目结构

```text
fastapi-boilerplate/
├── .github/
│   └── workflows/
│       └── ci.yml          # GitHub Actions CI 工作流
├── scripts/
│   ├── lint.sh             # 本地代码检查脚本
│   └── test.sh             # 运行测试并统计覆盖率
├── src/                    # 源代码目录
│   ├── common/             # 通用工具与错误处理
│   ├── conf/               # 配置与数据库设置
│   │   ├── alembic/        # 迁移脚本与环境配置
│   │   └── ...
│   ├── middleware/         # 自定义中间件 (Auth 等)
│   ├── user/               # 用户模块 (领域逻辑)
│   └── main.py             # 应用入口文件
├── tests/                  # 单元测试与集成测试
│   ├── unit/               # 单元测试 (mock 依赖)
│   ├── integration/        # 集成测试 (SQLite 内存数据库)
│   └── test.yml            # 测试配置（覆盖率阈值、路径）
├── .env.example            # 环境变量模板
├── docker-compose.yml      # Docker 服务编排 (App + DB)
├── pyproject.toml          # 项目依赖与工具配置
├── run.sh                  # 本地启动脚本
└── README.md               # 项目文档
```

## 🚀 快速开始 (Getting Started)

### 前置要求

-   **Python 3.12+**
-   **uv** (推荐的包管理器): `pip install uv`
-   **Docker** & **Docker Compose** (可选，用于容器化运行)

### 安装

1.  **克隆仓库**
    ```bash
    git clone https://github.com/yourusername/fastapi-boilerplate.git
    cd fastapi-boilerplate
    ```

2.  **安装依赖**
    ```bash
    uv sync
    ```

### 本地运行

1.  **启动数据库**
    你可以使用 Docker 快速启动一个 PostgreSQL 实例：
    ```bash
    docker-compose up -d db
    ```

2.  **运行应用**
    使用提供的脚本启动开发服务器：
    ```bash
    bash run.sh
    # 或者手动运行:
    # uv run uvicorn main:app --app-dir src --reload
    ```
    API 服务将在 `http://localhost:8000` 启动。
    交互式文档 (Swagger UI): `http://localhost:8000/docs`

### 使用 Docker 运行

构建并启动整个技术栈 (应用 + 数据库 + 迁移)：

```bash
docker-compose up --build
```

## 🛠 开发指南

### 数据库迁移

本项目使用 **Alembic** 进行数据库模式迁移。
*   **自动模式**: 应用会在启动时通过 `src/conf/alembic_runner.py` 自动执行 `upgrade head`。
*   **手动模式**: 当修改了模型 (Model) 需要创建新迁移时：
    ```bash
    # 生成迁移脚本
    uv run alembic revision --autogenerate -m "description_of_changes"
    
    # 手动应用迁移 (如果需要)
    uv run alembic upgrade head
    ```

### 代码质量

本项目使用 **ruff** 进行代码检查与格式化，**mypy** 进行类型检查。

安装开发依赖：

```bash
uv sync --all-extras
```

运行所有检查：

```bash
bash scripts/lint.sh
```

或者单独运行：

```bash
# 代码检查
uv run ruff check src tests

# 格式检查
uv run ruff format --check src tests

# 类型检查
uv run mypy src
```

自动修复问题：

```bash
uv run ruff check --fix src tests
uv run ruff format src tests
```

### 测试

本项目包含**单元测试**和**集成测试**。

#### 运行测试并查看统计：

```bash
bash scripts/test.sh
```

输出内容包括：
- 单元测试成功率
- 单元测试覆盖率
- 集成测试成功率
- 覆盖率阈值检查（默认 80%）

#### 单独运行测试：

```bash
# 仅单元测试
uv run pytest tests/unit -v

# 仅集成测试
uv run pytest tests/integration -v

# 所有测试
uv run pytest tests -v
```

#### 测试覆盖率

覆盖率报告生成在 `output/` 目录：
- `coverage.xml` - XML 格式，供 CI 工具使用
- `junit-unit.xml` - 单元测试 JUnit 报告
- `junit-integration.xml` - 集成测试 JUnit 报告

### CI/CD

本项目包含 GitHub Actions 工作流 (`.github/workflows/ci.yml`)，执行以下步骤：

1. **Lint Job**: ruff check、ruff format、mypy 类型检查
2. **Test Job**: 单元测试 + 集成测试，覆盖率阈值 80%

工作流在 `master` 分支的 push/PR 时触发。

## 📄 许可证

本项目基于 MIT 许可证开源 - 详见 [LICENSE](LICENSE) 文件。
