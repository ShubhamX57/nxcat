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
- [ ] Web app: search page and dataset page with a quick-look plot (React + TypeScript)
- [ ] Plain-English search: the language model only proposes a validated filter, and the user confirms it before it runs
- [ ] Integration: SciCat or qens (see the decision record in `docs/adr`)

## Architecture

<!-- Diagram, and a link to docs/architecture.md -->

## Quick start

Requirements: Docker. One command starts PostgreSQL and the API:

```bash
docker compose up -d --build --wait

# Load 200 synthetic datasets (plus 5 deliberately broken files)
docker compose exec api nxcat-generate --out /data/generated -n 200 --with-broken
docker compose exec api nxcat-ingest /data/generated
```

Then open the API docs at <http://localhost:8000/api/v1/docs>.
Stop with `docker compose down` (add `-v` to delete the data too).

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

Run `pre-commit install` once, from the repository root.

## Licence

MIT. See [LICENSE](LICENSE).
