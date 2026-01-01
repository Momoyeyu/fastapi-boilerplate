# FastAPI Demo & Boilerplate (脚手架)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.112+-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)

[中文文档](README_zh.md) | [English](README.md)

这是一个现代化的、生产就绪的 FastAPI 脚手架和演示项目，旨在帮助你快速启动后端开发。本项目集成了项目结构、数据库管理、身份验证和 DevOps 流水线的最佳实践。

## ✨ 特性 (Features)

-   **现代技术栈**: 基于 **FastAPI** (Python 3.12+) 构建，提供高性能 API 服务。
-   **ORM 与数据库**: 使用 **SQLModel** (SQLAlchemy + Pydantic) 配合 **PostgreSQL**。
-   **自动迁移**: 集成 **Alembic**，支持服务启动时自动同步数据库表结构。
-   **身份验证**: 基于 JWT 的身份验证中间件，包含安全的密码哈希处理。
-   **依赖管理**: 使用 **uv** 进行极速的 Python 包管理。
-   **Docker 支持**: 提供完整的 **Docker Compose** 配置，支持本地开发和容器化部署。
-   **CI/CD 流水线**: 包含 Shell 编写的 CI 脚本 (`pipeline/ci.sh`)，用于自动化测试和覆盖率检查。
-   **清晰架构**: 模块化的 `src/` 目录结构，分离关注点 (Handler, Service, Model, DTO)。

## 📂 项目结构

```text
fastapi-demo/
├── pipeline/               # CI/CD 流水线脚本
│   ├── ci.sh               # CI 入口脚本
│   └── ci.yml              # GitHub Actions 工作流示例
├── src/                    # 源代码目录
│   ├── common/             # 通用工具与错误处理
│   ├── conf/               # 配置与数据库设置
│   │   ├── alembic/        # 迁移脚本与环境配置
│   │   └── ...
│   ├── middleware/         # 自定义中间件 (Auth 等)
│   ├── user/               # 用户模块 (领域逻辑)
│   ├── main.py             # 应用入口文件
│   └── tests/              # 单元测试与集成测试
├── docker-compose.yml      # Docker 服务编排 (App + DB)
├── pyproject.toml          # 项目依赖配置
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
    git clone https://github.com/yourusername/fastapi-demo.git
    cd fastapi-demo
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

### 测试

运行测试套件并查看覆盖率报告：

```bash
bash pipeline/ci.sh
```

或者直接运行 pytest：

```bash
uv run pytest src/tests
```

## 📄 许可证

本项目基于 MIT 许可证开源 - 详见 [LICENSE](LICENSE) 文件。
