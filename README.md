# nxcat

![CI](https://github.com/ShubhamX57/nxcat/actions/workflows/ci.yml/badge.svg)

A small, open-source metadata catalogue for neutron (NeXus/HDF5) data.

> **Personal portfolio project, not production software. Work in progress.**

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

## AI evaluation

<!-- The real numbers from the 30-question evaluation set, whatever they are. -->

## Limitations

<!-- Synthetic data only, no facility login, not performance-tested. -->

## AI assistance

- Project set-up and configuration files (pyproject.toml, pre-commit, CI workflow,
  this README outline) were drafted with help from Claude (Anthropic) and reviewed by me.
- <!-- Keep this list up to date as the project grows. I write the core code myself:
  ingest, API endpoints, FilterSpec and validation, and the main front-end pages. -->

## Licence

MIT. See [LICENSE](LICENSE).
