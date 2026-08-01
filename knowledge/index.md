---
okf_version: "1.0"
title: "MicroTherapy — Knowledge Base"
description: "OKF knowledge bundle for the MicroTherapy AI therapist."
created: "2026-07-25"
---

# MicroTherapy Knowledge Base

This is the persistent knowledge store for MicroTherapy. Every client profile,
session record, treatment plan, topic reference, and modality guide lives here
as OKF-formatted markdown files.

## Structure

| Directory | Purpose |
|-----------|---------|
| `clients/` | One subdirectory per client — profile, history, plan |
| `topics/` | Reusable therapy topic knowledge (anxiety, grief, etc.) |
| `approaches/` | Modality reference (when and how to use each) |
| `_templates/` | Templates for creating new client bundles |

## Using This Knowledge

- **At session start:** Read the client's `profile.md`, `history.md` (last entry), and `plan.md`
- **During session:** Reference `topics/` and `approaches/` for guidance
- **At session end:** Write updated `history.md`, `plan.md`, and `profile.md`
- **Changes:** Log all writes to `log.md`
