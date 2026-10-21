FROM python:3.13-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency definitions
COPY pyproject.toml uv.lock ./

# Install dependencies into project virtual environment
RUN uv sync --frozen --no-cache

# Copy backend application files
COPY . .

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uv run uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
