# FastAPI Boilerplate

[![CI](https://github.com/Momoyeyu/fastapi-boilerplate/actions/workflows/ci.yml/badge.svg)](https://github.com/Momoyeyu/fastapi-boilerplate/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.112+-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

[中文文档](README_zh.md) | [English](README.md)

A modern, production-ready FastAPI boilerplate designed to kickstart your backend development. This project provides a solid foundation with best practices for project structure, database management, authentication, testing, and CI/CD pipelines — so you can focus on building your business logic.

## ✨ Features

-   **Modern Stack**: Built with **FastAPI** (Python 3.12+) for high performance.
-   **ORM & Database**: Uses **SQLModel** (SQLAlchemy + Pydantic) with **PostgreSQL**.
-   **Auto-Migrations**: Integrated **Alembic** for automatic database schema synchronization on startup.
-   **Authentication**: JWT-based authentication with Access Token + Refresh Token, Token Rotation, and secure password hashing.
-   **Configuration**: Type-safe settings management with **pydantic-settings**, auto-loading from `.env` files.
-   **Structured Logging**: Powered by **Loguru** with console coloring, file rotation, retention, and compression.
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
│       ├── ci.yml          # GitHub Actions CI workflow
│       └── cd.yml.example  # GitHub Actions CD workflow template
├── scripts/
│   ├── deploy.sh           # Deployment script
│   ├── lint.sh             # Local linting script
│   ├── migrate.sh          # Database migration script
│   ├── run.sh              # Local startup script
│   └── test.sh             # Run tests with coverage stats
├── src/                    # Source code
│   ├── auth/               # Authentication module (JWT, Refresh Token)
│   ├── common/             # Shared utilities & error handling
│   ├── conf/               # Configuration & Database setup
│   ├── middleware/         # Custom middlewares (Auth, Logging)
│   ├── user/               # User module (Domain logic)
│   └── main.py             # App entry point
├── migration/              # Alembic migration scripts
│   ├── alembic/            # Migration versions & env
│   └── runner.py           # Migration runner
├── tests/                  # Unit & Integration tests
│   ├── unit/               # Unit tests (mocked dependencies)
│   ├── integration/        # Integration tests (SQLite in-memory)
│   └── cfg.yml             # Test configuration (coverage threshold, paths)
├── logs/                   # Application logs (auto-created)
│   └── backend_{date}.log  # Daily log files (auto-rotated)
├── .env.example            # Environment variables template
├── docker-compose.yml      # Docker services (App + DB)
├── Makefile                # Development commands
├── pyproject.toml          # Project dependencies & tool configs
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
    git clone https://github.com/Momoyeyu/fastapi-boilerplate.git
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
    Use Makefile to start the dev server:
    ```bash
    make run
    # OR manually:
    # ./scripts/run.sh
    ```
    The API will be available at `http://localhost:8000`.
    Interactive docs (Swagger UI): `http://localhost:8000/docs`

3.  **Debug Mode (Optional)**
    Set `DEBUG=true` in your `.env` file to enable development features:
    - Swagger UI (`/docs`), ReDoc (`/redoc`), and OpenAPI schema (`/openapi.json`) are accessible without authentication
    
    > ⚠️ **Note**: In production, keep `DEBUG=false` (default) to require authentication for API documentation.

4.  **Testing APIs with Swagger UI**
    The project supports OAuth2 Password Flow for Swagger UI authentication:
    1. Visit `http://localhost:8000/docs`
    2. Click the **"Authorize"** button in the top right
    3. Enter admin credentials (default: `admin` / `admin`)
    4. Click **"Authorize"** to login
    5. Now you can test all protected endpoints directly from Swagger UI
    
    > The admin account is automatically created on application startup based on `ADMIN_USERNAME` and `ADMIN_PASSWORD` settings.

### Running with Docker

Build and run the entire stack (App + DB + Migration):

```bash
docker-compose up --build
```

## 🛠 Development

### Database Migrations

This project uses **Alembic** for schema migrations. Migration code is located in `migration/` (project root).

*   **Automatic**: Migrations run automatically before the app starts (via `scripts/migrate.sh`).
*   **Manual**: To run migrations manually:
    ```bash
    make migrate
    ```
*   **Create new migration**: After modifying models:
    ```bash
    # Generate migration script
    PYTHONPATH="src:." uv run alembic -c migration/alembic.ini revision --autogenerate -m "description_of_changes"
    ```

### Configuration

This project uses **pydantic-settings** for type-safe configuration management, defined in `src/conf/config.py`.

**Features:**
-   **Auto-loading**: Automatically loads from `.env` file and environment variables
-   **Type-safe**: All settings are validated with Pydantic
-   **Singleton pattern**: Single `settings` instance shared across the application

**Available Settings:**

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| `debug` | `DEBUG` | `false` | Enable debug mode |
| `database_url` | `DATABASE_URL` | PostgreSQL local | Database connection string |
| `password_salt` | `PASSWORD_SALT` | `Momoyeyu` | Salt for password hashing |
| `jwt_secret` | `JWT_SECRET` | `Momoyeyu` | Secret key for JWT tokens |
| `jwt_algorithm` | `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `jwt_expire_seconds` | `JWT_EXPIRE_SECONDS` | `3600` | Access Token expiration time (seconds) |
| `refresh_token_expire_seconds` | `REFRESH_TOKEN_EXPIRE_SECONDS` | `604800` | Refresh Token expiration time (seconds, default 7 days) |
| `admin_username` | `ADMIN_USERNAME` | `admin` | Admin account username (auto-created on startup) |
| `admin_password` | `ADMIN_PASSWORD` | `admin` | Admin account password |

**Usage:**

```python
from conf.config import settings

if settings.debug:
    print("Debug mode enabled")

print(f"Database: {settings.database_url}")
```

### Logging

This project uses **Loguru** for structured logging, configured in `src/conf/logging.py`.

**Features:**
-   **Console Output**: Colored, human-readable logs to stderr
-   **File Output**: Logs written to `logs/backend_{date}.log` (e.g., `backend_2024-01-22.log`)
-   **Rotation**: Daily rotation at midnight
-   **Retention**: Old logs kept for 7 days
-   **Compression**: Rotated logs are compressed to `.zip`
-   **Log Level**: `DEBUG` when `DEBUG=true`, otherwise `INFO`

**Usage:**

```python
from loguru import logger

logger.info("User logged in", user_id=123)
logger.error("Failed to process request", exc_info=True)
```

Log files are stored in the `logs/` directory (auto-created on first run).

### Request Logging Middleware

This project includes a request/response logging middleware (`src/middleware/logging.py`) for debugging and monitoring.

**Features:**
-   **Automatic Logging**: Logs method, path, status code, and duration for each request
-   **Detailed Logs**: DEBUG level logs headers, query params, and body
-   **Sensitive Data Masking**: Automatically masks passwords, tokens, etc. (shown as `***`)
-   **Path Exclusion**: Skips `/docs`, `/redoc`, and other documentation paths

**Log Output Example:**

```
INFO  | Request 1769136075426 | POST /auth/login
DEBUG | Request headers: {"content-type": "application/json", "authorization": "***"}
DEBUG | Request body: {"username": "alice", "password": "***"}
INFO  | Response 1769136075426 | 200 | 5.23ms
DEBUG | Response body: {"access_token": "***", "token_type": "bearer"}
```

**Masked Fields:**
-   Headers: `authorization`, `cookie`, `x-api-key`
-   Body/Params: `password`, `access_token`, `refresh_token`, `api_key`

### Authentication System

This project implements a complete JWT authentication system with Access Token + Refresh Token, located in `src/auth/` module.

**Features:**
-   **Dual Token Mechanism**: Access Token (short-lived, default 1 hour) for API authentication, Refresh Token (long-lived, default 7 days) for refreshing Access Token
-   **Token Rotation**: Each refresh revokes the old Refresh Token and generates a new one for enhanced security
-   **Database Storage**: Refresh Tokens are stored in the database, enabling revocation and auditing
-   **Secure Design**: Refresh Tokens are generated using cryptographically secure random strings

**API Endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/login` | POST | User login, returns Access Token and Refresh Token |
| `/auth/refresh` | POST | Use Refresh Token to get a new token pair |
| `/auth/logout` | POST | Revoke Refresh Token |

**Authentication Flow:**

```
1. User login -> Get Access Token + Refresh Token
2. Use Access Token to access APIs
3. When Access Token expires, use Refresh Token to refresh
4. On refresh, old Refresh Token is revoked, new token pair is returned
5. On logout, Refresh Token is revoked
```

**Usage Example:**

```http
# Login
POST /auth/login
Content-Type: application/x-www-form-urlencoded
username=admin&password=admin

# Response
{
    "access_token": "eyJhbG...",
    "refresh_token": "abc123...",
    "token_type": "bearer"
}

# Refresh Token
POST /auth/refresh
Content-Type: application/json
{"refresh_token": "abc123..."}

# Logout
POST /auth/logout
Content-Type: application/json
{"refresh_token": "abc123..."}
```

### Code Quality

This project uses **ruff** for linting/formatting and **mypy** for type checking.

Install dev dependencies:

```bash
uv sync --all-extras
```

Run all lint checks:

```bash
make lint
```

The script will prompt you to auto-format if any formatting issues are detected (`[y/n]`).

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

#### Run all tests with statistics:

```bash
make test
```

This will output:
- Unit test success rate
- Unit test coverage percentage
- Integration test success rate
- Coverage threshold check (default: 80%)

#### Run tests separately:

```bash
# Unit tests only
uv run pytest tests/unit -v

# Integration tests only
uv run pytest tests/integration -v

# All tests
uv run pytest tests -v
```

#### Test Coverage

Coverage reports are generated in the `output/` directory:
- `coverage.xml` - XML format for CI tools
- `junit-unit.xml` - JUnit format for unit tests
- `junit-integration.xml` - JUnit format for integration tests

### CI/CD

This project includes GitHub Actions workflows:

**CI (`.github/workflows/ci.yml`)**:
1. **Lint Job**: ruff check, ruff format, mypy
2. **Test Job**: Unit tests + Integration tests with coverage threshold (80%)

Triggers on push/PR to `master` branch.

**CD (`.github/workflows/cd.yml.example`)**:

This is a template file for continuous deployment. To enable CD:
1. Copy `cd.yml.example` to `cd.yml`
2. Configure the required secrets in your GitHub repository settings

The workflow includes:
1. **Build Job**: Build and push Docker image to Docker Hub
2. **Deploy Job**: Deploy to server via SSH

Triggers on push to `master` branch or manual dispatch when enabled.

**Available Make Commands:**
```bash
make           # Show help
make run       # Start development server
make migrate   # Run database migrations
make lint      # Run linting checks
make test      # Run all tests
make deploy    # Deploy application
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
