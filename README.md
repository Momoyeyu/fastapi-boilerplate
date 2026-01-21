# FastAPI Boilerplate

[![CI](https://github.com/yourusername/fastapi-boilerplate/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/fastapi-boilerplate/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.112+-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

[中文文档](README_zh.md) | [English](README.md)

A modern, production-ready FastAPI boilerplate and demo project designed to kickstart your backend development. This project integrates best practices for project structure, database management, authentication, and DevOps pipelines.

## ✨ Features

-   **Modern Stack**: Built with **FastAPI** (Python 3.12+) for high performance.
-   **ORM & Database**: Uses **SQLModel** (SQLAlchemy + Pydantic) with **PostgreSQL**.
-   **Auto-Migrations**: Integrated **Alembic** for automatic database schema synchronization on startup.
-   **Authentication**: JWT-based authentication middleware with secure password hashing.
-   **Package Management**: Powered by **uv** for extremely fast dependency management.
-   **Docker Ready**: Full **Docker Compose** support for local development and deployment.
-   **CI/CD Pipeline**: GitHub Actions workflow with lint checks and automated testing.
-   **Code Quality**: Static analysis with **ruff** (linting + formatting) and **mypy** (type checking).
-   **Clean Architecture**: Modular `src/` structure separating concerns (Handler, Service, Model, DTO).

## 📂 Project Structure

```text
fastapi-boilerplate/
├── .github/
│   └── workflows/
│       └── ci.yml          # GitHub Actions CI workflow
├── pipeline/               # CI/CD pipelines
│   ├── ci.sh               # CI entry script (local/Jenkins)
│   └── ci.yml              # Coverage configuration
├── scripts/
│   └── lint.sh             # Local linting script
├── src/                    # Source code
│   ├── common/             # Shared utilities & error handling
│   ├── conf/               # Configuration & Database setup
│   │   ├── alembic/        # Migration scripts & env
│   │   └── ...
│   ├── middleware/         # Custom middlewares (Auth, etc.)
│   ├── user/               # User module (Domain logic)
│   └── main.py             # App entry point
├── tests/                  # Unit & Integration tests
│   ├── unit/               # Unit tests (mocked dependencies)
│   └── integration/        # Integration tests (SQLite in-memory)
├── docker-compose.yml      # Docker services (App + DB)
├── pyproject.toml          # Project dependencies & tool configs
├── run.sh                  # Local startup script
└── README.md               # Documentation
```

## 🚀 Getting Started

### Prerequisites

-   **Python 3.12+**
-   **uv** (Recommended package manager): `pip install uv`
-   **Docker** & **Docker Compose** (Optional, for containerized run)

### Installation

1.  **Clone the repository**
    ```bash
    git clone https://github.com/yourusername/fastapi-boilerplate.git
    cd fastapi-boilerplate
    ```

2.  **Install dependencies**
    ```bash
    uv sync
    ```

### Running Locally

1.  **Start the Database**
    You can use Docker to start a PostgreSQL instance:
    ```bash
    docker-compose up -d db
    ```

2.  **Run the Application**
    Use the provided script to start the dev server:
    ```bash
    bash run.sh
    # OR manually:
    # uv run uvicorn main:app --app-dir src --reload
    ```
    The API will be available at `http://localhost:8000`.
    Interactive docs (Swagger UI): `http://localhost:8000/docs`

### Running with Docker

Build and run the entire stack (App + DB + Migration):

```bash
docker-compose up --build
```

## 🛠 Development

### Database Migrations

This project uses **Alembic** for schema migrations.
*   **Automatic**: The app automatically runs `upgrade head` on startup via `src/conf/alembic_runner.py`.
*   **Manual**: To create a new migration after modifying models:
    ```bash
    # Generate migration script
    uv run alembic revision --autogenerate -m "description_of_changes"
    
    # Apply migration manually (if needed)
    uv run alembic upgrade head
    ```

### Code Quality

This project uses **ruff** for linting/formatting and **mypy** for type checking.

Install dev dependencies:

```bash
uv sync --all-extras
```

Run all lint checks:

```bash
bash scripts/lint.sh
```

Or run individually:

```bash
# Linting
uv run ruff check src tests

# Format check
uv run ruff format --check src tests

# Type checking
uv run mypy src
```

Auto-fix linting issues:

```bash
uv run ruff check --fix src tests
uv run ruff format src tests
```

### Testing

This project includes both **unit tests** and **integration tests**.

#### Run all tests (with CI pipeline):

```bash
bash pipeline/ci.sh
```

#### Run tests separately:

```bash
# Unit tests only
uv run pytest tests/unit -v

# Integration tests only (uses SQLite in-memory)
DATABASE_URL="sqlite:///:memory:" uv run pytest tests/integration -v

# All tests
uv run pytest tests -v
```

#### Test Coverage

Coverage reports are generated in the `output/` directory:
- `coverage.xml` - XML format for CI tools
- `junit-unit.xml` - JUnit format for unit tests
- `junit-integration.xml` - JUnit format for integration tests

### CI/CD

This project includes GitHub Actions workflow (`.github/workflows/ci.yml`) that runs:

1. **Lint Job**: ruff check, ruff format, mypy
2. **Test Job**: Unit tests + Integration tests with coverage threshold (80%)

The workflow triggers on push/PR to `main`, `master`, and `develop` branches.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
