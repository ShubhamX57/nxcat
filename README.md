# nxcat

![CI](https://github.com/ShubhamX57/nxcat/actions/workflows/ci.yml/badge.svg)

A small, open-source metadata catalogue for neutron (NeXus/HDF5) data.

> **Personal portfolio project, not production software. Work in progress.**

## Problem

<!-- Scientists need to find experiment files by their metadata (instrument,
sample, temperature, date) rather than by folder and file name. -->

## Features

- [x] Ingest NeXus/HDF5 files with metadata validation (bad files are logged and skipped)
- [x] REST API with search, filters, paging and facets (FastAPI, OpenAPI docs)
- [x] Web app (React + TypeScript): search with filters and paging (filters kept in the address, so searches can be shared); dataset page with full metadata and a quick-look plot
- [ ] Plain-English search: the language model only proposes a validated filter, and the user confirms it before it runs
- [ ] Integration: SciCat or qens (see the decision record in `docs/adr`)

## Architecture

<!-- Diagram, and a link to docs/architecture.md -->

## Quick start

Requirements: Docker. One command starts PostgreSQL, the API and the web app:

```bash
docker compose up -d --build --wait

# Load 200 synthetic datasets (plus 5 deliberately broken files)
docker compose exec api nxcat-generate --out /data/generated -n 200 --with-broken
docker compose exec api nxcat-ingest /data/generated
```

Then open the app at <http://localhost:8080>, and the API docs at <http://localhost:8000/api/v1/docs>.
Stop with `docker compose down` (add `-v` to delete the data too).

## Write actions (admin login)

Reading is open. Changing the catalogue, for now starting an ingest, needs a login
token. Without login settings nxcat is read-only, and write requests answer 503.

```bash
cp .env.example .env
KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
sed -i '' "s|^NXCAT_SECRET_KEY=.*|NXCAT_SECRET_KEY=$KEY|" .env
HASH=$(cd backend && uv run nxcat-hash-password)   # asks for a password (12+ characters)
sed -i '' "s|^NXCAT_ADMIN_PASSWORD_HASH=.*|NXCAT_ADMIN_PASSWORD_HASH='$HASH'|" .env
docker compose up -d --wait                         # restart so the API reads .env
```

These write the secrets straight into `.env` without showing them (on Linux, use
`sed -i` instead of `sed -i ''`). The hash must stay in single quotes, because it
contains `$` signs that Docker Compose would otherwise treat as variables.

Then, in the API docs at <http://localhost:8000/api/v1/docs>, press **Authorize**,
log in, and call `POST /api/v1/ingest` with `{"folder": "generated"}`. Only folders
inside the data root (`/data` in Docker) can be ingested.

## Development

Requirements: Python 3.12, [uv](https://docs.astral.sh/uv/), Docker.

```bash
docker compose up -d db          # PostgreSQL on localhost:5432 (dev credentials)
cd backend
uv sync
uv run pytest                    # database tests are skipped if the db is not running

# Try it with synthetic data
uv run nxcat-generate --out ../data/generated -n 200 --with-broken
uv run nxcat-ingest ../data/generated

# Run the API, then open http://localhost:8000/api/v1/docs
uv run uvicorn nxcat.api.app:app --reload
```

Web app (needs Node 22.12 or newer, and the API running on port 8000):

```bash
cd frontend
npm install
npm run dev                      # http://localhost:5173
npm test                         # Vitest + React Testing Library
```

Run `pre-commit install` once, from the repository root.

## Licence

MIT. See [LICENSE](LICENSE).
