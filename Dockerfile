# syntax=docker/dockerfile:1
# MicroTherapy TTS MCP Server

FROM python:3.12-slim

WORKDIR /app

# Install uv for fast Python package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# System deps for audio processing, espeak phonemizer, and build tools
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    espeak-ng \
    espeak-ng-data \
    libsndfile1 \
    gcc \
    g++ \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# --- Dependency install (cached unless pyproject.toml changes) ---
COPY pyproject.toml README.md ./
COPY configs/ configs/
COPY assets/ assets/

# Create a dummy package so pip install succeeds without real src/
RUN mkdir -p src/microtherapy && echo '__version__ = "0.1.0"' > src/microtherapy/__init__.py

RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --prerelease=allow .

# Copy real source (fast — only this layer changes on code edits)
COPY src/ src/

# Reinstall in editable mode so source files are used directly
RUN uv pip install --system --prerelease=allow -e .

# Create a non-root user and pre-create the HF cache dir with correct ownership
RUN useradd --create-home --shell /bin/bash microtherapy && \
    mkdir -p /home/microtherapy/.cache/huggingface && \
    chown -R microtherapy:microtherapy /app /home/microtherapy/.cache

USER microtherapy

EXPOSE 3001
ENV MICROTHERAPY_DEBUG_SAVE_AUDIO=1
ENV HF_HOME=/home/microtherapy/.cache/huggingface

CMD ["python", "-m", "microtherapy.server"]

# Expose the MCP HTTP port
EXPOSE 3001

# Enable debug audio saving by default in the container
ENV MICROTHERAPY_DEBUG_SAVE_AUDIO=1
ENV HF_HOME=/home/microtherapy/.cache/huggingface

CMD ["python", "-m", "microtherapy.server"]
