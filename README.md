# FastAPI Boilerplate

[![CI](https://github.com/Momoyeyu/fastapi-boilerplate/actions/workflows/ci.yml/badge.svg)](https://github.com/Momoyeyu/fastapi-boilerplate/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.112+-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

[中文文档](README_zh.md) | [English](README.md)

A production-ready FastAPI boilerplate with 4-layer module architecture, JWT auth, auto-migration, structured logging, Docker support, and CI/CD. Designed for AI coding agents to scaffold backend projects quickly and consistently.

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

Verify: `http://localhost:8000/docs` (Swagger UI, requires `DEBUG=true` for unauthenticated access)

Full-stack Docker: `docker-compose up --build`

## Project Structure

```
src/
├── main.py                 # app factory, router & middleware registration
├── conf/                   # configuration (pydantic-settings, SQLAlchemy, Loguru, Redis)
├── common/                 # response envelope (resp.py), error factory (erri.py), exception handlers (trap.py)
├── middleware/              # JWT auth middleware + request/response logging
├── auth/                   # auth module (login, register, token, password, verification)
├── user/                   # user module (profile)
└── invitation/             # invitation code module

migration/                  # Alembic migrations (auto-run on `make run`)
tests/
├── unit/                   # isolated service logic tests (monkeypatch mocks)
├── integration/            # full request/response cycle (SQLite + FakeRedis)
└── cfg.yml                 # coverage config
```

## Module Architecture

Every feature module follows a **4-layer pattern** under `src/{module}/`:

| Layer | File | Responsibility |
|-------|------|----------------|
| Model | `model.py` | SQLAlchemy ORM models + async DB query functions |
| DTO | `dto.py` | Pydantic request/response schemas (no DB dependency) |
| Service | `{domain}.py` | Business logic, validation, raises `BusinessError` |
| Handler | `handler.py` | FastAPI `APIRouter`, calls service, returns `Response` |

**Data flow**: Handler -> Service -> Model

Service files are named by business domain (e.g., `token.py`, `password.py`), not a generic `service.py`. Reference: `src/user/` (minimal module), `src/auth/` (multi-service module).

### Adding a New Module

1. Create `src/{module}/` with `__init__.py`, `model.py`, `dto.py`, `{domain}.py`, `handler.py`
2. `model.py` — define SQLAlchemy ORM model + async query functions (use `async with AsyncSessionLocal()` with try/commit/rollback pattern)
3. `dto.py` — define Pydantic request/response schemas
4. `{domain}.py` — implement async business logic, call model functions, raise `erri.*` on errors
5. `handler.py` — define `APIRouter` routes, `await` service calls, return `ok(data=...)`
6. Register router in `src/main.py` `init_routers()`
7. Import model in `migration/alembic/env.py` for auto-migration
8. Add tests following `test_{module}_{domain}.py` naming convention

## Key Patterns

### Response Envelope

All endpoints return a standardized `Response` via `common.resp`:

```python
from common.resp import ok
return ok(data={...})           # success

from common import erri
raise erri.bad_request("...")   # 40000
raise erri.unauthorized("...")  # 40100
raise erri.forbidden("...")     # 40300
raise erri.not_found("...")     # 40400
raise erri.internal("...")      # 50000
```

### Authentication

- JWT middleware (`src/middleware/auth.py`) validates tokens on all routes by default
- `@auth.exempt` — skip auth for a handler
- `auth.get_username(request)` — extract current user
- Endpoints: `POST /api/v1/auth/login`, `POST /api/v1/auth/token/refresh`, `POST /api/v1/auth/logout`

### Configuration

Defined in `src/conf/config.py` via `pydantic-settings`, loaded from `.env`. See [`.env.example`](.env.example) for all available variables. Usage: `from conf.config import settings`

### Logging

Loguru-based (`src/conf/logging.py`). Console output + daily-rotated file logs (`logs/`). Request logging middleware auto-logs method, path, status, duration with sensitive field masking.

## Development

```bash
make run       # migrate DB + start dev server (uvicorn with reload)
make test      # run unit + integration tests
make lint      # ruff check + format
make migrate   # run Alembic migrations manually
make deploy    # deploy application
```

Generate migration after model changes:
```bash
PYTHONPATH="src:." uv run alembic -c migration/alembic.ini revision --autogenerate -m "description"
```

### Testing

Tests follow `test_{module}_{domain}.py` naming, mirroring `src/{module}/{domain}.py`.

| Layer | Purpose | Dependencies |
|-------|---------|--------------|
| Unit (`tests/unit/`) | Isolated service function tests | All external calls mocked via `monkeypatch` |
| Integration (`tests/integration/`) | Full API endpoint tests | SQLite + FakeRedis + mocked email |
| Workflow (`tests/integration/test_workflow.py`) | Cross-module user journeys | Same as integration |

Key fixtures in `integration/conftest.py`: `client`, `register_and_verify`, `auth_header`, `mock_email`, `session`.

### CI/CD

- **CI** (`.github/workflows/ci.yml`): lint -> test -> coverage check (PR only). Triggers on push/PR to `master`.
- **CD** (`.github/workflows/cd.yml.example`): Docker build + SSH deploy template. Copy to `cd.yml` and configure secrets.

## Tech Stack

FastAPI 0.112+ | Python 3.12+ | SQLAlchemy 2.0 (async) | PostgreSQL 16 | Redis 7 | PyJWT | Alembic | pydantic-settings | Loguru | uv | Ruff | pytest | Docker Compose | GitHub Actions

## License

MIT License — see [LICENSE](LICENSE).
