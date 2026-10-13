# Contributing to nxcat

Thank you for your interest. nxcat is a small personal project, but issues and pull
requests are welcome.

## Set up

You need Python 3.12, [uv](https://docs.astral.sh/uv/), Node 22.12 or newer, and Docker.

```bash
git clone https://github.com/ShubhamX57/nxcat.git
cd nxcat
docker compose up -d db              # PostgreSQL for the tests
cd backend && uv sync && cd ..
cd frontend && npm install && cd ..
pre-commit install                   # runs the linters before every commit
```

## Make a change

1. Create a branch from `main`: `git switch -c short-description`.
2. Make the change **with a test**. Every feature and every bug fix needs one.
3. Run the checks:

   ```bash
   cd backend
   uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
   cd ../frontend
   npm run lint && npm run typecheck && npm test
   ```

4. Commit with a short message in the imperative ("Add temperature filter"), push,
   and open a pull request into `main`.
5. A pull request is merged only when all three CI jobs (backend, frontend, docker)
   are green.

## Standards

- **Python:** ruff for style and lint, mypy in strict mode, type hints everywhere.
  Backend test coverage must stay at or above 80% (CI fails below that).
- **TypeScript:** strict mode, oxlint with no warnings.
- **Validation:** data coming in (files, query strings, request bodies, model output)
  goes through a pydantic model before it is used.
- **Secrets:** never commit `.env` or any key, password or token.
- **Data:** only synthetic data, or public files whose licence allows it. Record the
  source and licence in `data/SOURCES.md`.
- **Design decisions:** for a choice others will ask "why?" about, add a short record in
  `docs/adr/`.

## Reporting a problem

Open an issue with what you did, what you expected, and what happened instead
(including any error message).
