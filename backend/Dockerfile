FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN --mount=type=secret,id=build_ca,required=false \
    if [ -s /run/secrets/build_ca ]; then \
      SSL_CERT_FILE=/run/secrets/build_ca uv sync --frozen --no-dev; \
    else \
      uv sync --frozen --no-dev; \
    fi
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

