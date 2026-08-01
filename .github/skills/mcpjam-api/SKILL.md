---
name: mcpjam-api
description: |
  Use this skill when the user wants to test, debug, validate, or run evals
  against an MCP server using the MCPJam public API. Covers the full MCPJam
  REST API surface: catalog discovery, server diagnostics (validate, doctor,
  check-oauth), primitives (tools, prompts, resources), tool execution,
  OAuth token import, eval suites and runs, and project management.
  Use when the user mentions "MCPJam API", "test with MCPJam", "run evals
  in MCPJam", "CI eval", "server diagnostics via MCPJam", or similar.
---

# MCPJam API

Programmatic access to MCP servers saved in your MCPJam projects — diagnostics,
tool calls, prompt rendering, eval suites, and more.

**Base URL:** `https://app.mcpjam.com/api/v1`

## ⚠️ Prerequisites

Before using the API, you need:

1. **An MCPJam account** — sign in at [app.mcpjam.com](https://app.mcpjam.com)
2. **An API key** — create at [Settings → API keys](https://app.mcpjam.com/settings/api-keys)
3. **A project with servers** — create a project in the hosted inspector, add your MCP servers

Store the API key in `.env`:

```bash
MCPJAM_API_KEY=sk_...
```

## Authentication

Every request needs the API key in the `Authorization` header:

```bash
curl -H "Authorization: Bearer $MCPJAM_API_KEY" \
     -H "Content-Type: application/json" \
     "https://app.mcpjam.com/api/v1/me"
```

API keys are scoped to one organization and act as the user who created them.
Guest sessions cannot use the API.

## Conventions

- **Reads** are `GET` with query params for filters/pagination
- **Writes/operations** are `POST` with JSON body (most accept `{}`)
- **Collections** return `{"items": [...], "nextCursor": "..."}` — cursor-based pagination
- **Errors** return `{"code": "...", "message": "..."}` with matching HTTP status
- **Rate limit:** 60 req/min sustained, bursts up to 10. Honor `Retry-After` header

### Error Codes

| Code | HTTP | Meaning |
|------|------|---------|
| `UNAUTHORIZED` | 401 | Bad/missing/revoked key |
| `OAUTH_REQUIRED` | 401 | Target MCP server needs OAuth |
| `FORBIDDEN` | 403 | Valid key, not allowed |
| `VALIDATION_ERROR` | 400 | Malformed body/params |
| `NOT_FOUND` | 404 | Unknown project/server/resource |
| `CONFLICT` | 409 | Stale revision, dup name |
| `FEATURE_NOT_SUPPORTED` | 422 | Server lacks capability |
| `RATE_LIMITED` | 429 | Too many requests |
| `SERVER_UNREACHABLE` | 502 | Can't connect to MCP server |
| `TIMEOUT` | 504 | MCP server didn't respond |
| `INTERNAL_ERROR` | 500 | MCPJam-side failure |

## Catalog (Discovery)

Find the IDs everything else needs.

### Who am I?

```bash
curl -s -H "Authorization: Bearer $MCPJAM_API_KEY" \
  "https://app.mcpjam.com/api/v1/me" | jq
```

### List projects

```bash
curl -s -H "Authorization: Bearer $MCPJAM_API_KEY" \
  "https://app.mcpjam.com/api/v1/projects" | jq '.items[] | {id, name}'
```

### List servers in a project

```bash
PROJECT_ID="proj_..."
curl -s -H "Authorization: Bearer $MCPJAM_API_KEY" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/servers" | jq '.items[] | {id, name, url, transportType, useOAuth}'
```

### List eval suites in a project

```bash
curl -s -H "Authorization: Bearer $MCPJAM_API_KEY" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/eval-suites" | jq
```

## Server Diagnostics

### Validate (connect + initialize)

Quick check: connect, initialize MCP session, return capability snapshot.

```bash
curl -s -X POST \
  -H "Authorization: Bearer $MCPJAM_API_KEY" \
  -H "Content-Type: application/json" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/servers/$SERVER_ID/validate" \
  -d '{}' | jq
```

Returns: `{ success: true, status: "connected", initInfo: {...} }`

### Doctor (full health check)

Probe → connect → initialize → capabilities → primitives. Richest diagnostic.

```bash
curl -s -X POST \
  -H "Authorization: Bearer $MCPJAM_API_KEY" \
  -H "Content-Type: application/json" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/servers/$SERVER_ID/doctor" \
  -d '{}' | jq
```

Returns: `{ status: "ready"|"partial"|"error", checks: {...}, tools: [...], ... }`

### Check OAuth

Does this server require OAuth?

```bash
curl -s -X POST \
  -H "Authorization: Bearer $MCPJAM_API_KEY" \
  -H "Content-Type: application/json" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/servers/$SERVER_ID/check-oauth" \
  -d '{}' | jq
```

Returns: `{ useOAuth: true|false, serverUrl: "..." }`

## Primitives

### List tools

```bash
curl -s -X POST \
  -H "Authorization: Bearer $MCPJAM_API_KEY" \
  -H "Content-Type: application/json" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/servers/$SERVER_ID/tools" \
  -d '{}' | jq '.items[] | {name, description}'
```

### List prompts

```bash
curl -s -X POST \
  -H "Authorization: Bearer $MCPJAM_API_KEY" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/servers/$SERVER_ID/prompts" \
  -d '{}' | jq
```

### List resources

```bash
curl -s -X POST \
  -H "Authorization: Bearer $MCPJAM_API_KEY" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/servers/$SERVER_ID/resources" \
  -d '{}' | jq
```

### Read a resource

```bash
curl -s -X POST \
  -H "Authorization: Bearer $MCPJAM_API_KEY" \
  -H "Content-Type: application/json" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/servers/$SERVER_ID/resources/read" \
  -d '{"uri": "file:///readme.md"}' | jq
```

## Execution

### Call a tool

Execute a tool and get the MCP `CallToolResult` back verbatim.

```bash
curl -s -X POST \
  -H "Authorization: Bearer $MCPJAM_API_KEY" \
  -H "Content-Type: application/json" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/servers/$SERVER_ID/tools/call" \
  -d '{
    "toolName": "hello",
    "parameters": {"name": "World"}
  }' | jq
```

Tool-level failures (`isError: true`) are successful HTTP calls — the server answered.

### Render a prompt

```bash
curl -s -X POST \
  -H "Authorization: Bearer $MCPJAM_API_KEY" \
  -H "Content-Type: application/json" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/servers/$SERVER_ID/prompts/get" \
  -d '{
    "promptName": "summarize",
    "arguments": {"style": "bullet"}
  }' | jq
```

## Export (Snapshot)

Get tools, resources, and prompts in one JSON snapshot — useful for CI diffing.

```bash
curl -s -X POST \
  -H "Authorization: Bearer $MCPJAM_API_KEY" \
  -H "Content-Type: application/json" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/servers/$SERVER_ID/export" \
  -d '{}' | jq '{serverId, tools: .tools | length, resources: .resources | length, prompts: .prompts | length}'
```

## OAuth Token Import

If a server returns `OAUTH_REQUIRED`, complete OAuth yourself (using `@mcpjam/sdk`'s
`runOAuthLogin`) and push the tokens. Subsequent calls inject and refresh automatically.

```bash
curl -s -X POST \
  -H "Authorization: Bearer $MCPJAM_API_KEY" \
  -H "Content-Type: application/json" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/servers/$SERVER_ID/oauth/import-tokens" \
  -d '{
    "serverUrl": "https://mcp.example.com/mcp",
    "clientInformation": {"clientId": "client_123"},
    "tokens": {
      "access_token": "at_...",
      "refresh_token": "rt_...",
      "expires_in": 3600
    }
  }' | jq
```

## Eval Suites & Runs

### Create an eval suite (author only, does NOT run)

```bash
curl -s -X POST \
  -H "Authorization: Bearer $MCPJAM_API_KEY" \
  -H "Content-Type: application/json" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/eval-suites" \
  -d '{
    "name": "smoke-tests",
    "serverIds": ["srv_..."],
    "model": "anthropic/claude-haiku-4.5",
    "tests": [
      {
        "title": "hello tool works",
        "steps": [
          {"id": "s1", "kind": "prompt", "prompt": "Use the hello tool to greet World"},
          {"id": "s2", "kind": "assert", "assertion": {
            "type": "toolCalledWith",
            "toolName": "hello",
            "args": {"args": {"name": "World"}}
          }}
        ]
      }
    ]
  }' | jq
```

### Create an eval run (async — responds 202 immediately)

```bash
# From an existing suite
RUN_ID=$(curl -s -X POST \
  -H "Authorization: Bearer $MCPJAM_API_KEY" \
  -H "Content-Type: application/json" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/eval-runs" \
  -d '{"suiteId": "suite_..."}' | jq -r '.runId')

# Or inline (new suite + run)
RUN_ID=$(curl -s -X POST \
  -H "Authorization: Bearer $MCPJAM_API_KEY" \
  -H "Content-Type: application/json" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/eval-runs" \
  -d '{
    "suiteName": "smoke",
    "serverIds": ["srv_..."],
    "tests": [...]
  }' | jq -r '.runId')
```

### Poll run status

```bash
curl -s -H "Authorization: Bearer $MCPJAM_API_KEY" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/eval-runs/$RUN_ID" | jq '{status, result, summary}'
```

Terminal statuses: `completed`, `failed`, `cancelled`.

### Get iteration results

```bash
curl -s -H "Authorization: Bearer $MCPJAM_API_KEY" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/eval-runs/$RUN_ID/iterations" | jq
```

### Cancel a run

```bash
curl -s -X POST \
  -H "Authorization: Bearer $MCPJAM_API_KEY" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/eval-runs/$RUN_ID/cancel" \
  -d '{}' | jq
```

## Hosts

### List hosts

```bash
curl -s -H "Authorization: Bearer $MCPJAM_API_KEY" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/hosts" | jq '.items[] | {id, name, modelId}'
```

### Create a host from template

```bash
curl -s -X POST \
  -H "Authorization: Bearer $MCPJAM_API_KEY" \
  -H "Content-Type: application/json" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/hosts" \
  -d '{"name": "My Claude", "template": "claude", "theme": "dark"}' | jq
```

Available templates: `claude`, `chatgpt`, `cursor`, `copilot`, `vscode`, `mistral`, `codex`, `perplexity`, `mcpjam`, `claude-code`, `agentcore`, `n8n`.

## Environments

Project environments are named execution bundles (host + optional server group +
pinned skills/plugins) that eval suites run against.

### List environments

```bash
curl -s -H "Authorization: Bearer $MCPJAM_API_KEY" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/environments" | jq '.items[] | {id, name, hostId}'
```

### Resolve an environment (preview what it connects to)

```bash
curl -s -H "Authorization: Bearer $MCPJAM_API_KEY" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/environments/$ENV_ID/resolve" | jq '.effectiveServerIds'
```

## Chatboxes

Read-only access to published chatboxes.

```bash
# List
curl -s -H "Authorization: Bearer $MCPJAM_API_KEY" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/chatboxes" | jq

# Detail (model, system prompt, tool approval policy, servers)
curl -s -H "Authorization: Bearer $MCPJAM_API_KEY" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/chatboxes/$CHATBOX_ID" | jq
```

## Tunnels

Expose a local MCP server through a public relay URL.

### Create a tunnel

```bash
curl -s -X POST \
  -H "Authorization: Bearer $MCPJAM_API_KEY" \
  -H "Content-Type: application/json" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/tunnels" \
  -d '{"name": "my-local-server"}' | jq
```

Returns: `{ serverId, url, connectToken, relayWsUrl, slug }`. The `url` is the public
endpoint; `connectToken` authenticates the WebSocket to `relayWsUrl`.

### Close a tunnel

```bash
curl -s -X POST \
  -H "Authorization: Bearer $MCPJAM_API_KEY" \
  -H "Content-Type: application/json" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/tunnels/$SERVER_ID/close" \
  -d '{}' | jq
```

## Common Workflows for This Project

### 1. Quick smoke test of MicroTherapy server

```bash
# Set up
PROJECT_ID="<your-project-id>"
SERVER_ID="<your-server-id>"

# List tools (should include "speak", "list_voices")
curl -s -X POST \
  -H "Authorization: Bearer $MCPJAM_API_KEY" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/servers/$SERVER_ID/tools" \
  -d '{}' | jq '.items[].name'

# Call speak tool
curl -s -X POST \
  -H "Authorization: Bearer $MCPJAM_API_KEY" \
  -H "Content-Type: application/json" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/servers/$SERVER_ID/tools/call" \
  -d '{"toolName": "speak", "parameters": {"text": "Hello from CI", "autoPlay": false}}' | jq
```

### 2. Server health check in CI

```bash
# Run doctor
RESULT=$(curl -s -X POST \
  -H "Authorization: Bearer $MCPJAM_API_KEY" \
  -H "Content-Type: application/json" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/servers/$SERVER_ID/doctor" \
  -d '{}')

STATUS=$(echo "$RESULT" | jq -r '.status')
if [ "$STATUS" != "ready" ]; then
  echo "Server health check failed: $STATUS"
  echo "$RESULT" | jq '.checks'
  exit 1
fi
echo "Server healthy"
```

### 3. Regression testing with eval suites

```bash
# Create a suite (one-time)
SUITE_ID=$(curl -s -X POST \
  -H "Authorization: Bearer $MCPJAM_API_KEY" \
  -H "Content-Type: application/json" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/eval-suites" \
  -d '{
    "name": "microtherapy-regression",
    "serverIds": ["'"$SERVER_ID"'"],
    "model": "anthropic/claude-haiku-4.5",
    "tests": [
      {
        "title": "speak tool returns audio",
        "steps": [
          {"id": "s1", "kind": "prompt", "prompt": "Say hello world"},
          {"id": "s2", "kind": "assert", "assertion": {
            "type": "toolCalledWith",
            "toolName": "speak",
            "args": {"args": {"text": "hello world"}}
          }}
        ]
      }
    ]
  }' | jq -r '.suiteId')

# Run it (every CI run)
RUN_ID=$(curl -s -X POST \
  -H "Authorization: Bearer $MCPJAM_API_KEY" \
  -H "Content-Type: application/json" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/eval-runs" \
  -d '{"suiteId": "'"$SUITE_ID"'"}' | jq -r '.runId')

# Poll
while true; do
  STATUS=$(curl -s -H "Authorization: Bearer $MCPJAM_API_KEY" \
    "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/eval-runs/$RUN_ID" | jq -r '.status')
  case "$STATUS" in
    completed|failed|cancelled) break ;;
    *) sleep 10 ;;
  esac
done

# Check result
PASSED=$(curl -s -H "Authorization: Bearer $MCPJAM_API_KEY" \
  "https://app.mcpjam.com/api/v1/projects/$PROJECT_ID/eval-runs/$RUN_ID" | jq -r '.summary.passed')
echo "Eval result: $PASSED tests passed"
```

## What's NOT in the API (yet)

- Creating or revoking API keys (UI-only)
- Chat and conformance suites
- Browser-based OAuth flows (use `oauth/import-tokens` instead)
