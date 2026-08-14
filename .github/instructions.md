# MicroTherapy — Project Instructions

You are working in the **MicroTherapy** project workspace.

## Quick Reference

| Purpose | Resource |
|---------|----------|
| **Therapy / counseling conversations** | Use the **Therapy agent** (`.github/agents/therapy.agent.md`) |
| **Coding / development work** | These instructions + `AGENTS.md` |

## Project Overview

MicroTherapy is a TTS-enabled AI therapy system that runs inside VS Code.
It uses Kokoro-82M for text-to-speech, MCP 2.0 Apps for the audio player UI,
and OKF (Open Knowledge Format) bundles for persistent client memory.

## For Therapy Sessions

When the user wants to talk about mental health, emotions, personal issues,
or anything therapeutic, **switch to or suggest the Therapy agent**. The
Therapy agent manages session lifecycle, client history, modality routing,
and OKF data.

Do NOT apply therapy techniques outside the Therapy agent context.

---

## For Development Work

When working on the MicroTherapy codebase:

- Python code lives in `src/microtherapy/`
- MCP server entry point: `src/microtherapy/server.py`
- TTS queue: `src/microtherapy/tts_queue.py`
- HTML player view: `src/microtherapy/view.py`
- Tests: `tests/`
- Run the server via Docker: `docker compose up -d microtherapy`

See `AGENTS.md` for Telegram contact preferences and coding conventions.

## Agents & Skills

This workspace uses custom agents and skills:

- `.github/agents/` — Custom agents (Therapy, and future domain agents)
- `.github/skills/` — Domain skills tied to specific agents

Future agents (workout, career, etc.) can be added alongside the Therapy agent.
Each agent can be scoped to its own skills and knowledge namespace.
