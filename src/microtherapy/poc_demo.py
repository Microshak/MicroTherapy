#!/usr/bin/env python3
"""
POC Demo — Simplest possible MCP App that displays a greeting.
Shows the core pattern: tool + ui:// resource + embedded HTML view.

Usage:
    uv run python src/microtherapy/poc_demo.py
"""

from __future__ import annotations

import logging
import os
import sys

import uvicorn
from mcp.server import MCPServer
from mcp_types._types import CallToolResult, TextContent
from starlette.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("poc-demo")

VIEW_URI = "ui://poc-demo/view.html"
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "3003"))

server = MCPServer(name="POC Demo", version="1.0.0")

# ── Embedded HTML View ──────────────────────────────────────────────
VIEW_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>POC Demo</title>
<style>
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    padding: 20px;
    text-align: center;
  }
  .card {
    max-width: 320px; margin: 0 auto; padding: 24px;
    border-radius: 12px; border: 1px solid #e2e8f0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  }
  .greeting { font-size: 24px; font-weight: 700; margin: 16px 0; color: #7c3aed; }
  .status { font-size: 13px; color: #94a3b8; }
  button {
    padding: 10px 24px; border: none; border-radius: 8px;
    background: #7c3aed; color: white; font-size: 16px; cursor: pointer;
  }
  button:hover { background: #6d28d9; }
</style>
</head>
<body>
<div class="card">
  <p>👋</p>
  <div class="greeting" id="msg">Waiting...</div>
  <div class="status" id="status">Connecting...</div>
  <br>
  <button id="btn">Say Hello Again</button>
</div>

<script>
// ── Minimal MCP App bridge — works without external SDK ──────────
const msgEl = document.getElementById('msg');
const statusEl = document.getElementById('status');
const btn = document.getElementById('btn');

let msgId = 0;
const pending = {};

function postToHost(method, params) {
  const id = ++msgId;
  return new Promise((resolve, reject) => {
    pending[id] = { resolve, reject };
    window.parent.postMessage({ jsonrpc: '2.0', id, method, params }, '*');
    setTimeout(() => { delete pending[id]; reject(new Error('timeout')); }, 10000);
  });
}

window.addEventListener('message', (event) => {
  const data = event.data;
  if (!data || !data.jsonrpc) return;

  // Handle tool result pushed by host
  if (data.method === 'tools/result' && data.params) {
    const text = data.params?.content?.[0]?.text || 'No result';
    msgEl.textContent = text;
    statusEl.textContent = '✅ Connected';
    return;
  }

  // Handle pending promises
  if (data.id !== undefined && pending[data.id]) {
    if (data.error) pending[data.id].reject(data.error);
    else pending[data.id].resolve(data.result);
    delete pending[data.id];
  }
});

// ── MCP App initialization handshake ──────────────────────
(async function init() {
  try {
    const initResult = await postToHost('initialize', {
      protocolVersion: '2025-06-18',
      clientInfo: { name: 'POC Demo', version: '1.0.0' },
      capabilities: {}
    });
    console.log('MCP initialized:', initResult);

    window.parent.postMessage({
      jsonrpc: '2.0',
      method: 'notifications/initialized'
    }, '*');

    statusEl.textContent = '✅ Connected to host';
  } catch (err) {
    console.error('MCP init failed:', err);
    statusEl.textContent = '⚠️ Offline';
  }
})();

// Button: call tool directly
btn.addEventListener('click', async () => {
  statusEl.textContent = 'Calling...';
  try {
    const result = await postToHost('tools/call', {
      name: 'hello',
      arguments: { name: 'Tester' }
    });
    const text = result?.content?.[0]?.text || 'No result';
    msgEl.textContent = text;
    statusEl.textContent = '✅ Done';
  } catch (err) {
    statusEl.textContent = '❌ ' + (err?.message || 'Error');
  }
});
</script>
</body>
</html>"""


# ── Tools ───────────────────────────────────────────────────────────

@server.tool(
    name="hello",
    description="Say hello! Returns a friendly greeting.",
    meta={"ui": {"resourceUri": VIEW_URI}},
)
def hello(name: str = "World") -> CallToolResult:
    logger.info("hello tool called: name=%r", name)
    greeting = f"Hello, {name}! 👋"
    return CallToolResult(content=[TextContent(type="text", text=greeting)])


# ── UI Resource ─────────────────────────────────────────────────────

@server.resource(
    VIEW_URI,
    name="POC Demo View",
    mime_type="text/html;profile=mcp-app",
    meta={
        "ui": {
            "csp": {
                "resourceDomains": ["https://esm.sh", "https://unpkg.com"],
            }
        }
    },
)
def view() -> str:
    return VIEW_HTML


# ── Entry Point ─────────────────────────────────────────────────────

def create_app():
    app = server.streamable_http_app(stateless_http=True, host=HOST)
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )
    return app


def main() -> None:
    if "--stdio" in sys.argv:
        logger.info("POC Demo starting in stdio mode...")
        server.run(transport="stdio")
    else:
        app = create_app()
        logger.info("POC Demo listening on http://%s:%s/mcp", HOST, PORT)
        uvicorn.run(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
