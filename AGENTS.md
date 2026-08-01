# AGENTS.md — Coding Agent Instructions

## Contacting the User

When you need to ask the user a question (clarification, decision, approval), **do not** ask inline in the chat. Instead, send them a message via **Telegram** using the `better-telegram-mcp` MCP server. The user prefers async communication and may not see chat messages promptly.

### Telegram MCP Setup

The user has the [better-telegram-mcp](https://github.com/n24q02m/better-telegram-mcp) server configured in their MCP client. This server provides a `message` tool with a `send` action.

**Server:** `better-telegram-mcp` (Python, `uvx better-telegram-mcp`)
**Transport:** stdio (bot mode) with `TELEGRAM_BOT_TOKEN` env var, or HTTP mode for user accounts.

### How to Send a Message

Use the `message` tool with action `send`:

```
Tool: message
Action: send
Parameters:
  - chat_id: "<USER'S_TELEGRAM_CHAT_ID>"    ← REPLACE WITH ACTUAL CHAT ID
  - text: "<your question or message>"
```

**Example call:**

```json
{
  "name": "message",
  "arguments": {
    "action": "send",
    "chat_id": "123456789",
    "text": "Should I use PostgreSQL or SQLite for the auth module? SQLite is simpler but Postgres scales better."
  }
}
```

### When to Contact the User

- **Ambiguous requirements** — When the PRD/spec is unclear and you need a decision
- **Architecture tradeoffs** — When there's a meaningful choice (e.g., database, library, pattern)
- **Blockers** — When you cannot proceed without user input
- **Completion notice** — When a major milestone is done and you want the user to know

### When NOT to Contact

- **Trivial choices** — e.g., variable naming, file organization, minor style
- **Obvious fixes** — Bugs with a single clear fix
- **Routine progress** — The user wants results, not play-by-play updates

### Message Format

Keep Telegram messages concise. Use this structure:

```
[Context: what you're working on]
[Question/Decision needed]
[Options if applicable, with brief pros/cons]
[What you'll do if no response in N hours — default action]
```

**Example:**

> Working on MicroTherapy PRD-03 (MCP server impl). Should the `speak` tool use SSE streaming for audio chunks, or return the full WAV as one blob? SSE is better UX (audio starts faster) but adds complexity. I'll go with SSE streaming unless you say otherwise within 4 hours.

### User's Telegram Info

| Field | Value |
|-------|-------|
| Chat ID | **`<REPLACE_WITH_YOUR_TELEGRAM_CHAT_ID>`** |
| Username | **`<REPLACE_WITH_YOUR_TELEGRAM_USERNAME>`** |

> **⚠️ The user must fill in their actual Telegram chat ID or username above.** To find your chat ID, message [@userinfobot](https://t.me/userinfobot) on Telegram.

---

## Project: MicroTherapy

This is a TTS (Text-to-Speech) MCP application that lets coding agents speak their answers aloud using **Kokoro-82M** for TTS and **MCP 2.0 Apps** for the interactive audio player UI. See `/docs/prd/` for detailed requirements.

### Key Principles

- **Speak, don't just write** — When returning results, use the TTS `speak` tool to read answers aloud
- **Streaming first** — Prefer SSE streaming over batch responses for audio
- **Single-file where possible** — Follow the say-server pattern (embedded HTML view in Python)
- **Protocol version**: `2026-07-28` (stateless MCP 2.0, per-request `_meta`)

### How It Works

```
Copilot → speak(text) → MCP tool → returns JSON {text, voice, autoPlay}
                                      ↓
                               MCP App view opens (HTML player)
                                      ↓
                               creates queue → generates TTS → polls audio → plays
```

The `speak` tool has `meta.ui.resourceUri` which tells the MCP client to open the embedded HTML audio player. The player uses the `@modelcontextprotocol/ext-apps` SDK to create TTS queues, add text, and poll for audio chunks.

### Running the Server

**The server runs as a Docker container** — do NOT try to run it directly with `uv run` on the host.

```bash
# Start (first time builds the image, ~5-10 min for model download)
docker compose up -d microtherapy

# View logs
docker compose logs -f microtherapy

# Stop
docker compose stop microtherapy

# Restart after code changes
docker compose up -d --build microtherapy
```

The server listens on port 3001 via HTTP (streamable MCP). The `.vscode/mcp.json` connects to it at `http://localhost:3001/mcp`.

### Port Map

| Port | Service | Purpose |
|------|---------|---------|
| 3001 | microtherapy | MCP HTTP endpoint |
| 6274 | inspector | MCP Inspector web UI |
| 16006 | phoenix | Phoenix web UI + MCP endpoint |

### Debug Flags

- `MICROTHERAPY_DEBUG_SAVE_AUDIO=1` — Saves generated WAV files to `assets/audio/debug_*.wav`
- Debug files are accessible on the host via the docker volume mount `./assets/audio:/app/assets/audio`

### Dependency Notes

- `pyproject.toml` pins `mcp>=2.0.0` (stable, upgraded from `2.0.0b2`)
- `pyproject.toml` pins `kokoro>=0.9.4`
- `onnxruntime` pinned to `<1.24` for cp310 wheel compatibility
- `requires-python` capped at `<3.14` to avoid resolver failures on unreleased Python
- Always use `--prerelease=allow` with uv commands (mcp is pre-release)
- **view.py** uses `@modelcontextprotocol/ext-apps@1.7.5` (SDK) via esm.sh importmap

### Common Issues

- **Port 3001 "address already in use"**: VS Code MCP tunnel holds the port. Use Docker, not direct `uv run`.
- **"Waiting for text..." in player**: The view fallback in `ontoolresult` handles AI-invoked tools. If it persists, check server logs for CUDA errors.
- **CUDA device-side assert / garbled audio**: Force CPU mode with `CUDA_VISIBLE_DEVICES=""` env var if GPU issues occur. CPU generation is slower but produces clean audio.
- **Permission denied on /media/microshak/Data/huggingface**: External drive unmounted. Set `HF_HOME=$HOME/.cache/huggingface`.
