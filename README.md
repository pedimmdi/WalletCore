# WalletCore

![CI](https://github.com/pedimmdi/WalletCore/actions/workflows/ci.yml/badge.svg)

A digital wallet backend built with **double-entry ledger accounting**, **concurrency-safe** transactions, and full **idempotency** support. Built with Django and Django REST Framework.

## Why this project

Real financial systems can't afford mistakes: two simultaneous requests shouldn't allow a double withdrawal, a retried request (e.g. after a network timeout) shouldn't execute twice, and every unit of currency must be traceable. This project is built to solve exactly those three problems:

- **Double-entry ledger** — every transaction writes exactly two entries (debit/credit), with a dedicated system account representing money entering or leaving the platform.
- **Row-level locking** (`select_for_update`) to prevent race conditions, with a fixed locking order to avoid deadlocks.
- **Idempotency keys** on every money-moving operation — reusing a key with different request data returns a clear error instead of silently succeeding.
- **Automated daily reconciliation** via Celery Beat, which detects any mismatch between the cached wallet balance and the ledger's computed balance.

## Features

- JWT authentication (register, login, token refresh)
- Deposit, withdraw, and transfer between users
- Transaction history with filtering and pagination
- Admin endpoints to list and freeze wallets
- Redis-backed balance caching
- Background jobs with Celery (transaction notifications + daily reconciliation)
- Full API documentation via Swagger/Redoc
- Strong test coverage: unit, idempotency, and concurrency tests
- Automated CI with GitHub Actions

## Tech stack

Django 5.2 · Django REST Framework · PostgreSQL · Redis · Celery · JWT · drf-spectacular · pytest

## Running locally

```bash
git clone https://github.com/pedimmdi/WalletCore.git
cd WalletCore
cp .env.example .env   # fill in the values
docker compose up -d --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

The server runs at `http://localhost:8000`. API documentation:
- Swagger UI: `http://localhost:8000/api/docs/`
- Redoc: `http://localhost:8000/api/redoc/`

## Running tests

```bash
docker compose exec web pytest -q
```

## API usage examples

Register and log in:
```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"username": "ali", "email": "ali@example.com", "password": "strongpass123"}'

curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "ali", "password": "strongpass123"}'
```

Deposit (requires an `Idempotency-Key` header):
```bash
curl -X POST http://localhost:8000/api/wallet/deposit/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Idempotency-Key: unique-key-123" \
  -H "Content-Type: application/json" \
  -d '{"amount": "100.00"}'
```

Transfer funds:
```bash
curl -X POST http://localhost:8000/api/wallet/transfer/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Idempotency-Key: unique-key-456" \
  -H "Content-Type: application/json" \
  -d '{"to_user_id": 2, "amount": "40.00"}'
```

## Project structure

```
core/       Project settings, URLs, Celery configuration
wallet/     Models, financial services, views, tests
tests/      Unit, idempotency, and concurrency tests
```

## License

MIT