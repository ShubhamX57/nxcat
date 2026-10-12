# nxcat

![CI](https://github.com/ShubhamX57/nxcat/actions/workflows/ci.yml/badge.svg)

A small, open-source metadata catalogue for neutron (NeXus/HDF5) data.

## Problem

<!-- Scientists need to find experiment files by their metadata (instrument,
sample, temperature, date) rather than by folder and file name. -->

## Features

- [ ] Ingest NeXus/HDF5 files with metadata validation
- [ ] REST API with search, filters and facets (FastAPI, OpenAPI docs)
- [ ] Web app: search page and dataset page with a quick-look plot (React + TypeScript)
- [ ] Plain-English search: the language model only proposes a validated filter, and the user confirms it before it runs
- [ ] Integration: SciCat or qens (see the decision record in `docs/adr`)

## Architecture

<!-- Diagram, and a link to docs/architecture.md -->

## Quick start

<!-- docker compose up -->

## Development

```bash
cd backend
uv sync
uv run pytest
pre-commit install   # run once, from the repository root
```

## Licence

MIT. See [LICENSE](LICENSE).
