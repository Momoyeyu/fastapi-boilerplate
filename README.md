# FastAPI Demo & Boilerplate

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.112+-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)

[中文文档](README_zh.md) | [English](README.md)

A modern, production-ready FastAPI boilerplate and demo project designed to kickstart your backend development. This project integrates best practices for project structure, database management, authentication, and DevOps pipelines.

## ✨ Features

-   **Modern Stack**: Built with **FastAPI** (Python 3.12+) for high performance.
-   **ORM & Database**: Uses **SQLModel** (SQLAlchemy + Pydantic) with **PostgreSQL**.
-   **Auto-Migrations**: Integrated **Alembic** for automatic database schema synchronization on startup.
-   **Authentication**: JWT-based authentication middleware with secure password hashing.
-   **Package Management**: Powered by **uv** for extremely fast dependency management.
-   **Docker Ready**: Full **Docker Compose** support for local development and deployment.
-   **CI/CD Pipeline**: Includes shell-based CI scripts (`pipeline/ci.sh`) for testing and coverage.
-   **Clean Architecture**: Modular `src/` structure separating concerns (Handler, Service, Model, DTO).

## 📂 Project Structure

```text
fastapi-demo/
├── pipeline/               # CI/CD pipelines
│   ├── ci.sh               # CI entry script
│   └── ci.yml              # GitHub Actions workflow (example)
├── src/                    # Source code
│   ├── common/             # Shared utilities & error handling
│   ├── conf/               # Configuration & Database setup
│   │   ├── alembic/        # Migration scripts & env
│   │   └── ...
│   ├── middleware/         # Custom middlewares (Auth, etc.)
│   ├── user/               # User module (Domain logic)
│   ├── main.py             # App entry point
│   └── tests/              # Unit & Integration tests
├── docker-compose.yml      # Docker services (App + DB)
├── pyproject.toml          # Project dependencies
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
    git clone https://github.com/yourusername/fastapi-demo.git
    cd fastapi-demo
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

### Testing

Run the test suite with coverage reports:

```bash
bash pipeline/ci.sh
```

Or run pytest directly:

```bash
uv run pytest src/tests
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
