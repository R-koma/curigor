FROM ghcr.io/astral-sh/uv:0.9.30 AS uv

FROM python:3.13-slim-bookworm AS builder

COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY . .
RUN uv sync --frozen --no-dev


FROM python:3.13-slim-bookworm

COPY --from=uv /uv /usr/local/bin/uv

WORKDIR /app

RUN useradd --create-home appuser
COPY --from=builder --chown=appuser:appuser /app /app

EXPOSE 8000
USER appuser
ENV UV_CACHE_DIR=/tmp/uv-cache
# --no-sync: 起動時に uv が .venv を作り直さない（appuser はルート所有の /app に書けず権限エラーになるため）。
# ビルド時に同期済みの .venv をそのまま使う。
CMD ["sh", "-c", "uv run --no-sync fastapi run main.py --host 0.0.0.0 --port ${PORT:-8000}"]