# PRD-04: Build, Package & Deploy

**Status:** Draft  
**Date:** 2026-07-25  
**Depends on:** PRD-00, PRD-01, PRD-02, PRD-03  
**Produces:** `pyproject.toml`, `README.md`, Docker support, test suite

---

## 1. Objective

Package MicroTherapy as a distributable MCP server that works with:
- **VS Code GitHub Copilot** (stdio or HTTP transport)
- **Claude Desktop** (stdio transport)
- **Any MCP 2.0-compatible host** (Streamable HTTP)

---

## 2. Project Configuration

### 2.1 `pyproject.toml`

```toml
[project]
name = "microtherapy"
version = "0.1.0"
description = "Streaming TTS MCP App — let your coding agent speak to you"
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
authors = [
    { name = "MicroShak" }
]
keywords = ["mcp", "tts", "text-to-speech", "kokoro", "ai-agent"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
]

dependencies = [
    "mcp[cli]>=2.0.0b1",
    "kokoro>=0.9.4",
    "uvicorn>=0.34.0",
    "starlette>=0.46.0",
    "pydantic>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "ruff>=0.8.0",
]

[project.scripts]
microtherapy = "microtherapy.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/microtherapy"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]
```

### 2.2 Package Structure

```
src/
└── microtherapy/
    ├── __init__.py          # Empty or version
    ├── server.py            # MCP server entry point
    ├── tts.py               # Kokoro-82M TTS wrapper
    ├── queue.py             # TTS queue manager
    └── view.py              # Embedded HTML view

assets/
└── audio/
    └── prompt.wav           # Default voice prompt audio

tests/
├── __init__.py
├── test_tts.py
├── test_queue.py
└── test_server.py

pyproject.toml
README.md
LICENSE
AGENTS.md
```

---

## 3. Installation & Usage

### 3.1 Quick Start (uv)

```bash
# Run directly from the repo
uv run python -m microtherapy.server

# Or via the script entry point
uv run microtherapy
```

### 3.2 stdio Mode (Desktop Clients)

```json
{
  "mcpServers": {
    "microtherapy": {
      "command": "uv",
      "args": [
        "run",
        "--directory", "/path/to/MicroTherapy",
        "microtherapy",
        "--stdio"
      ]
    }
  }
}
```

### 3.3 HTTP Mode (Remote / Browser Clients)

```bash
# Start HTTP server
uv run microtherapy
# → Server listening on http://0.0.0.0:3001/mcp
```

Configure client to connect to `http://localhost:3001/mcp`.

### 3.4 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | HTTP bind address |
| `PORT` | `3001` | HTTP port |
| `MICROTHERAPY_DEBUG_SAVE_AUDIO` | `0` | Set to `1` to save generated WAV files to `assets/audio/` |

---

## 4. Docker Support

### 4.1 Dockerfile

```dockerfile
FROM python:3.12-slim-bookworm

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy source
COPY src/ src/
COPY assets/ assets/

# Pre-download Kokoro model (optional, speeds first run)
RUN python -c "from microtherapy.tts import TTSModel; TTSModel.load_model()" || true

ENV HOST=0.0.0.0
ENV PORT=3001

EXPOSE 3001

CMD ["uvicorn", "microtherapy.server:create_app", "--host", "0.0.0.0", "--port", "3001"]
```

### 4.2 Docker Compose

```yaml
# docker-compose.yml
services:
  microtherapy:
    build: .
    ports:
      - "3001:3001"
    environment:
      - HOST=0.0.0.0
      - PORT=3001
      # GPU is optional — Kokoro runs well on CPU
    volumes:
      - ./assets:/app/assets  # For custom prompt audio
      - huggingface_cache:/root/.cache/huggingface  # Cache model weights

volumes:
  huggingface_cache:
```

### 4.3 Run with Docker

```bash
docker compose up -d
# Server at http://localhost:3001/mcp
```

---

## 5. Testing

### 5.1 Test Suite

```python
# tests/test_queue.py
import pytest
from microtherapy.queue import TTSQueueManager

def test_create_queue():
    mgr = TTSQueueManager()
    qid = mgr.create_queue("default")
    assert len(qid) == 12
    assert qid in mgr._queues

def test_add_text():
    mgr = TTSQueueManager()
    qid = mgr.create_queue("default")
    added = mgr.add_text(qid, "Hello world")
    assert added == 11
    assert mgr._queues[qid].full_text == "Hello world"

def test_add_text_incremental():
    mgr = TTSQueueManager()
    qid = mgr.create_queue("default")
    mgr.add_text(qid, "Hello")
    added = mgr.add_text(qid, "Hello world")  # Replaces with fuller version
    assert added == 6  # " world" added
    assert mgr._queues[qid].full_text == "Hello world"

def test_get_new_chunks():
    mgr = TTSQueueManager()
    qid = mgr.create_queue("default")
    # Add fake audio chunk
    mgr._queues[qid].audio_chunks = [b"fake_audio_data"]
    chunks = mgr.get_new_chunks(qid)
    assert len(chunks) == 1
    # Second call returns empty (already consumed)
    chunks = mgr.get_new_chunks(qid)
    assert len(chunks) == 0

def test_end_queue():
    mgr = TTSQueueManager()
    qid = mgr.create_queue("default")
    assert not mgr.is_done(qid)
    mgr.end_queue(qid)
    assert mgr.is_done(qid)
```

### 5.2 Server Integration Tests

```python
# tests/test_server.py
import pytest
from microtherapy.server import mcp

def test_server_name():
    assert mcp.name == "MicroTherapy"

def test_list_voices():
    """Test that list_voices returns valid data."""
    # This is a structural test — actual MCP tool invocation
    # requires a running server transport
    pass
```

### 5.3 Running Tests

```bash
# Install dev deps
uv pip install -e ".[dev]"

# Run tests
uv run pytest -v

# With coverage
uv run pytest --cov=microtherapy --cov-report=html
```

---

## 6. Prompt Audio

### 6.1 Default Voice

The project needs a default voice prompt audio file. Options:

**Option A: Generate with another TTS model**
Use a high-quality TTS model (e.g., Kokoro, XTTS, ElevenLabs) to generate a clean 5-10 second clip.

**Option B: Record yourself**
Record 5-10 seconds of clear, neutral speech.

**Option C: Use an open-source voice sample**
Kokoro-82M includes 28 built-in voices (American and British English, male and female). No prompt audio needed.

### 6.2 Requirements

- **Format:** 16-bit mono WAV
- **Duration:** 3-10 seconds
- **Content:** Clear, neutral English speech
- **Location:** `assets/audio/prompt.wav`
- **Voices:** 28 built-in Kokoro voices; select via the `voice` parameter

---

## 7. CI/CD (Optional)

### 7.1 GitHub Actions

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
      - name: Lint
        run: ruff check src/ tests/
      - name: Test
        run: pytest -v
```

---

## 8. Distribution

### 8.1 PyPI (Future)

```bash
# Build
uv build

# Publish
uv publish
```

Users would install via:
```bash
pip install microtherapy
microtherapy --stdio
```

### 8.2 GitHub Release

Tag and release on GitHub. Users can:
```bash
uv run https://raw.githubusercontent.com/microshak/MicroTherapy/main/src/microtherapy/server.py --stdio
```

---

## 9. Troubleshooting Guide

Include in `README.md`:

| Problem | Solution |
|---------|----------|
| "kokoro not found" | `pip install kokoro>=0.9.4` |
| "model download failed" | Check internet; first run downloads ~800MB model weights |
| "CUDA out of memory" | Set `CUDA_VISIBLE_DEVICES=""` to force CPU |
| "No audio output" | Check browser autoplay policy; click the play button |
| "Audio sounds robotic" | Try a different prompt audio file |
| "Server not starting on port 3001" | Check if port is in use: `lsof -i :3001` |
| "CORS errors in browser" | Ensure CORS middleware is configured |

---

## 10. Deliverables Checklist

- [x] `pyproject.toml` with correct dependencies and build config
- [x] `src/microtherapy/__init__.py`
- [x] `src/microtherapy/server.py` — main entry point
- [x] `src/microtherapy/tts.py` — Kokoro-82M wrapper
- [x] `src/microtherapy/queue.py` — TTS queue manager
- [x] `src/microtherapy/view.py` — embedded HTML view
- [x] `assets/audio/prompt.wav` — default voice prompt
- [x] `tests/test_tts.py` — TTS tests
- [x] `tests/test_queue.py` — queue tests
- [x] `tests/test_server.py` — server tests
- [x] `README.md` — installation and usage docs
- [x] `Dockerfile` and `docker-compose.yml`
- [x] CI workflow (`.github/workflows/ci.yml`)
- [x] Works with `uv run microtherapy --stdio` (desktop clients)
- [x] Works with `uv run microtherapy` (HTTP mode)
