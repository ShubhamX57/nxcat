# nxcat API image. Two stages: build the virtual environment, then copy only
# that into a small runtime image (no uv, no build tools, no tests).

FROM python:3.12-slim AS build
# git is needed only here, to fetch qens from its GitHub repository (pinned commit).
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app
# Dependencies first: this layer is cached until uv.lock changes.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.12-slim
RUN useradd --create-home --uid 10001 nxcat && mkdir /data && chown nxcat /data
COPY --from=build /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 MPLBACKEND=Agg
USER nxcat
WORKDIR /home/nxcat
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --retries=10 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')"]
CMD ["uvicorn", "nxcat.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
