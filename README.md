# FastAPI Boilerplate

[![CI](https://github.com/Momoyeyu/fastapi-boilerplate/actions/workflows/ci.yml/badge.svg)](https://github.com/Momoyeyu/fastapi-boilerplate/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.112+-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

[中文文档](README_zh.md) | [English](README.md)

A production-ready FastAPI boilerplate designed for coding agents to scaffold backend projects quickly and consistently. Provides a standard 4-layer module architecture, JWT auth, auto-migration, structured logging, Docker support, and CI/CD — so agents (and humans) can focus on business logic.

> **For AI coding agents**: see [CLAUDE.md](CLAUDE.md) for agent-specific workflow instructions.

## Quick Start

**Prerequisites**: Python 3.12+, [uv](https://github.com/astral-sh/uv), Docker (optional)

```bash
git clone https://github.com/Momoyeyu/fastapi-boilerplate.git
cd fastapi-boilerplate
cp .env.example .env          # configure environment
uv sync                       # install dependencies
docker-compose up -d db redis # start PostgreSQL + Redis
make run                      # migrate DB + start dev server at localhost:8000
```

**Verify**: `http://localhost:8000/docs` (Swagger UI, requires `DEBUG=true` for unauthenticated access)

**Run with Docker** (full stack):
```bash
docker-compose up --build
```

## Project Structure

```
fastapi-boilerplate/
├── src/                        # application source
│   ├── main.py                 # app factory, router & middleware registration
│   ├── conf/
│   │   ├── config.py           # pydantic-settings configuration (loads .env)
│   │   ├── db.py               # SQLAlchemy engine
│   │   └── logging.py          # Loguru setup
│   ├── common/
│   │   ├── resp.py             # Response envelope & status codes
│   │   ├── erri.py             # BusinessError factory (bad_request, not_found, etc.)
│   │   └── trap.py             # global exception handlers
│   ├── middleware/
│   │   ├── auth.py             # JWT auth middleware + @auth.exempt decorator
│   │   └── logging.py          # request/response logging middleware
│   ├── auth/                   # auth module
│   │   ├── token.py            # login, token creation/refresh/revocation
│   │   ├── password.py         # password hashing and reset
│   │   ├── register.py         # registration with email verification
│   │   └── verification.py     # verification code management (Redis)
│   ├── user/                   # user module
│   │   └── profile.py          # profile queries and updates
│   └── invitation/             # invitation code module
├── migration/
│   ├── runner.py               # migration execution interface
│   └── alembic/                # Alembic env & version scripts
├── tests/
│   ├── unit/                   # unit tests (mocked dependencies)
│   ├── integration/            # integration tests (SQLite + FakeRedis)
│   │   ├── conftest.py         # fixtures (TestClient, FakeRedis, email mock)
│   │   └── test_workflow.py    # end-to-end user journey tests
│   └── cfg.yml                 # test coverage config
├── scripts/                    # shell scripts for dev tasks
├── .env.example                # environment variable template
├── docker-compose.yml          # App + PostgreSQL + Redis
├── Makefile                    # dev commands
├── pyproject.toml              # dependencies & tool config
└── CLAUDE.md                   # agent workflow instructions
```

## Module Architecture

Every feature module follows a 4-layer pattern under `src/{module}/`:

| Layer | File | Responsibility |
|-------|------|----------------|
| **Model** | `model.py` | SQLModel table classes + DB query functions |
| **DTO** | `dto.py` | Pydantic request/response schemas (no DB dependency) |
| **Service** | `{domain}.py` | Business logic, validation, raises `BusinessError` |
| **Handler** | `handler.py` | FastAPI `APIRouter`, calls service, returns `Response` |

**Data flow**: Handler (parse request) -> Service (validate + orchestrate) -> Model (DB operations)

Service files are named by business domain (e.g., `token.py`, `password.py`, `register.py`) rather than a generic `service.py`. Simple modules may use a single service file; larger modules split into multiple domain files.

**Reference implementation**: `src/user/` is a minimal module; `src/auth/` shows a multi-service module.

### Adding a New Module

1. Create `src/{module}/` with `__init__.py`, `model.py`, `dto.py`, `{domain}.py` (service), `handler.py`

2. **model.py** — define table + queries:
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

3. **dto.py** — request/response schemas:
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

4. **service.py** — business logic + error handling:
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

5. **handler.py** — routes:
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

6. **Register** in `src/main.py` `init_routers()`:
```python
from product.handler import router as product_router
_app.include_router(product_router)
```

7. **Import model** in `migration/alembic/env.py` for auto-migration:
```python
from product.model import Product  # noqa: F401
```

8. **Add tests** following the naming convention `test_{module}_{domain}.py` (see [Testing](#testing))

## Key Patterns

### Response Envelope

All endpoints return a standardized `Response`:
```python
from common.resp import Response, ok

# Success
return ok(data={"key": "value"})
return ok(message="Operation completed")

# Errors — raise BusinessError, trap.py handles conversion
from common import erri
raise erri.bad_request("Invalid input")     # code 40000
raise erri.unauthorized("Login required")   # code 40100
raise erri.forbidden("No permission")       # code 40300
raise erri.not_found("Resource not found")  # code 40400
raise erri.internal("Server error")         # code 50000
```

### Authentication

- JWT middleware in `src/middleware/auth.py` validates tokens on all routes by default
- Use `@auth.exempt` decorator on handler functions to skip auth
- Extract current user: `username = auth.get_username(request)`
- Auth endpoints: `POST /auth/login`, `POST /auth/token/refresh`, `POST /auth/logout`

### Database Transactions

```python
# Standard pattern in model.py
with Session(engine) as session:
    try:
        session.add(obj)
        session.commit()
        session.refresh(obj)
    except Exception:
        session.rollback()
        return None  # service layer converts None -> BusinessError
```

### Configuration

Defined in `src/conf/config.py` via `pydantic-settings`, loaded from `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `false` | Enable debug mode (exposes docs without auth) |
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_USER` | `postgres` | PostgreSQL user |
| `DB_PASSWORD` | `postgres` | PostgreSQL password |
| `DB_NAME` | `fastapi-boilerplate` | PostgreSQL database |
| `REDIS_HOST` | `localhost` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_DB` | `0` | Redis database number |
| `PASSWORD_SALT` | `Momoyeyu` | Salt for password hashing (change in production) |
| `JWT_SECRET` | `Momoyeyu` | JWT signing secret (change in production) |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `JWT_EXPIRE_SECONDS` | `3600` | Access token TTL |
| `REFRESH_TOKEN_EXPIRE_SECONDS` | `604800` | Refresh token TTL (7 days) |
| `VERIFICATION_CODE_EXPIRE_SECONDS` | `300` | Verification code TTL |
| `REQUIRE_INVITATION_CODE` | `false` | Require invitation code for registration |

Usage: `from conf.config import settings`

### Logging

Configured in `src/conf/logging.py` via Loguru. Logs to console (colored) and `logs/backend_{date}.log` (daily rotation, 7-day retention, zip compression).

```python
from loguru import logger
logger.info("User logged in", user_id=123)
```

Request logging middleware (`src/middleware/logging.py`) auto-logs method, path, status, duration. Masks sensitive fields (`password`, `authorization`, `access_token`, etc.).

## Development Commands

```bash
make run       # migrate DB + start dev server (uvicorn with reload)
make test      # run unit + integration tests
make lint      # ruff check + format
make migrate   # run Alembic migrations manually
make deploy    # deploy application
```

### Database Migrations

- **Automatic**: `make run` runs migrations before starting the server
- **Manual**: `make migrate`
- **Generate new migration** (after model changes):
  ```bash
  PYTHONPATH="src:." uv run alembic -c migration/alembic.ini revision --autogenerate -m "description"
  ```

### Testing

```bash
make test                          # all tests
uv run pytest tests/unit -v        # unit only
uv run pytest tests/integration -v # integration only
```

#### Test Architecture

Tests are organized into three layers, all following the naming convention `test_{module}_{domain}.py` to mirror source files in `src/{module}/{domain}.py`:

```
tests/
├── unit/                          # isolated service logic (monkeypatch mocks)
│   ├── test_auth_token.py         ← src/auth/token.py
│   ├── test_auth_password.py      ← src/auth/password.py
│   ├── test_auth_register.py      ← src/auth/register.py
│   ├── test_user_profile.py       ← src/user/profile.py
│   ├── test_auth_middleware.py     ← src/middleware/auth.py
│   └── ...
├── integration/                   # full request/response cycle (SQLite + FakeRedis)
│   ├── conftest.py                # shared fixtures
│   ├── test_auth_register.py      # registration + invitation code endpoints
│   ├── test_auth_token.py         # login, token refresh, logout endpoints
│   ├── test_auth_password.py      # password forgot/reset endpoints
│   ├── test_user_profile.py       # profile + password change endpoints
│   ├── test_common_resp.py        # response envelope format consistency
│   └── test_workflow.py           # cross-module end-to-end user journeys
└── cfg.yml                        # coverage config (threshold, include/exclude)
```

| Layer | Purpose | Dependencies |
|-------|---------|--------------|
| **Unit** | Test individual service functions in isolation | All external calls mocked via `monkeypatch` |
| **Integration** | Test API endpoints through the full stack | Temporary SQLite DB + FakeRedis + mocked email |
| **Workflow** | Test multi-step user journeys across modules | Same as integration (lives in `integration/`) |

#### Key Conventions

- **Naming**: `test_{module}_{domain}.py` mirrors `src/{module}/{domain}.py`. When adding a new module, create corresponding test files in both `unit/` and `integration/`.
- **Fixtures** (`integration/conftest.py`): `client` (TestClient), `register_and_verify` (two-step registration helper), `auth_header` (get Bearer token), `mock_email` (captures sent emails), `session` (direct DB access).
- **Email mocking**: `mock_email` fixture (autouse) intercepts all email sending. Tests can inspect `mock_email` to verify email parameters.
- **Coverage**: CI checks incremental coverage on PRs (threshold: 80%, configured in `tests/cfg.yml`).

#### Workflow Tests

`test_workflow.py` tests complete user journeys that span multiple API modules:

| Test Class | Journey |
|------------|---------|
| `TestNewUserOnboarding` | Register → verify email → view/update profile → logout |
| `TestTokenLifecycle` | Access API → refresh token → access again → logout → verify revoked |
| `TestMultiSession` | Login twice → logout one session → other session unaffected |
| `TestPasswordLifecycle` | Change password → logout → login → forgot → reset → login |
| `TestProfilePersistence` | Update profile → logout → login → verify data persisted |

### CI/CD

**CI** (`.github/workflows/ci.yml`): lint -> test -> coverage check (PR only). Triggers on push/PR to `master`.

**CD** (`.github/workflows/cd.yml.example`): template for Docker build + SSH deploy. Copy to `cd.yml` and configure secrets to enable.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Framework | FastAPI 0.112+ |
| Python | 3.12+ |
| ORM | SQLModel (SQLAlchemy + Pydantic) |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| Auth | PyJWT (Access + Refresh tokens) |
| Migrations | Alembic |
| Config | pydantic-settings |
| Logging | Loguru |
| Package manager | uv |
| Linter/Formatter | Ruff |
| Testing | pytest |
| Container | Docker Compose |
| CI/CD | GitHub Actions |

## License

MIT License — see [LICENSE](LICENSE).
