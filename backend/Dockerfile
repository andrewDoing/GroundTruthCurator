# Multi-stage image that builds the frontend and packages the FastAPI backend.

# --- Stage 1: build frontend (Vite/React assumed) ---
FROM --platform=linux/amd64 node:20-alpine AS fe-build
WORKDIR /work

# Use repo root as build context; copy only manifests first for caching
COPY frontend/package*.json frontend/
RUN cd frontend && npm ci --no-audit --no-fund

# Copy rest of frontend and build
COPY frontend frontend
RUN cd frontend && npm run build


# --- Stage 2: backend runtime ---
FROM --platform=linux/amd64 python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PORT=8080

WORKDIR /app

# System dependencies (minimal)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv (Astral) for fast, reproducible installs
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Copy only backend dependency manifests (context is repo root)
COPY backend/pyproject.toml backend/uv.lock ./

# Create and sync virtual environment with locked deps (no dev deps in image)
RUN uv sync --frozen --no-dev

# Ensure venv is on PATH at runtime
ENV PATH="/app/.venv/bin:${PATH}"

# Copy backend application code
COPY backend/app ./app

# Copy built frontend artifacts into a known directory and enable SPA serving by default
COPY --from=fe-build /work/frontend/dist /app/frontend_dist
ENV GTC_FRONTEND_DIR=/app/frontend_dist

EXPOSE 8080

# Start uvicorn. Use --proxy-headers for Azure ingress.
# Use shell form so $PORT is expanded at runtime (JSON-form doesn't expand env vars).
CMD sh -c 'uv run uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}" --proxy-headers'
