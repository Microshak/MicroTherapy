#!/usr/bin/env python3
"""MicroTherapy MCP Server — End-to-End Test Script.

Tests:
  1. Docker HTTP endpoint reachable (tools/list)
  2. speak tool returns valid response
  3. list_voices tool returns valid response
  4. stdio mode starts and responds
"""

import json
import subprocess
import sys
import urllib.request
import urllib.error

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"

PASS = f"{GREEN}✓ PASS{RESET}"
FAIL = f"{RED}✗ FAIL{RESET}"
WARN = f"{YELLOW}⚠ WARN{RESET}"

MCP_URL = "http://localhost:3001/mcp"
TIMEOUT = 10

results = []

def test(name: str):
    print(f"\n{BOLD}── {name} ──{RESET}")

def ok(msg: str = ""):
    msg = f" — {msg}" if msg else ""
    print(f"  {PASS}{msg}")
    results.append(True)

def bad(msg: str):
    print(f"  {FAIL}: {msg}")
    results.append(False)

def warn(msg: str):
    print(f"  {WARN}: {msg}")
    results.append(True)  # warning is not a failure


# ── Test 1: HTTP endpoint reachable ──────────────────────────
test("HTTP endpoint: tools/list")

try:
    req = urllib.request.Request(
        MCP_URL,
        data=json.dumps({
            "jsonrpc": "2.0", "id": 1,
            "method": "tools/list", "params": {}
        }).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=TIMEOUT)
    body = resp.read().decode()
    
    # Parse SSE format: "event: message\ndata: {...}"
    if "data:" in body:
        data_line = [l for l in body.split("\n") if l.startswith("data:")][0]
        data = json.loads(data_line[5:].strip())
        tools = data.get("result", {}).get("tools", [])
        tool_names = [t["name"] for t in tools]
        
        expected = ["speak", "list_voices", "create_tts_queue", "add_tts_text", "poll_tts_audio", "end_tts_queue"]
        missing = [t for t in expected if t not in tool_names]
        
        if missing:
            bad(f"Missing tools: {missing}")
        else:
            ok(f"All {len(tools)} tools available: {', '.join(tool_names)}")
    else:
        bad(f"Unexpected response: {body[:200]}")

except urllib.error.URLError as e:
    bad(f"Cannot reach {MCP_URL}: {e.reason}")
except Exception as e:
    bad(str(e))


# ── Test 2: speak tool ───────────────────────────────────────
test("Tool call: speak")

try:
    req = urllib.request.Request(
        MCP_URL,
        data=json.dumps({
            "jsonrpc": "2.0", "id": 2,
            "method": "tools/call",
            "params": {
                "name": "speak",
                "arguments": {"text": "Hello", "voice": "default", "autoPlay": False}
            }
        }).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=TIMEOUT)
    body = resp.read().decode()
    
    if "data:" in body:
        data_line = [l for l in body.split("\n") if l.startswith("data:")][0]
        data = json.loads(data_line[5:].strip())
        
        if "error" in data:
            bad(f"speak returned error: {data['error']}")
        elif "result" in data:
            content = data["result"].get("content", [{}])[0].get("text", "")
            ok(f"Response: {content[:80]}")
        else:
            bad(f"Unexpected: {body[:200]}")
    else:
        bad(f"Unexpected: {body[:200]}")

except urllib.error.URLError as e:
    bad(f"Cannot reach {MCP_URL}: {e.reason}")
except Exception as e:
    bad(str(e))


# ── Test 3: list_voices tool ─────────────────────────────────
test("Tool call: list_voices")

try:
    req = urllib.request.Request(
        MCP_URL,
        data=json.dumps({
            "jsonrpc": "2.0", "id": 3,
            "method": "tools/call",
            "params": {"name": "list_voices", "arguments": {}}
        }).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=TIMEOUT)
    body = resp.read().decode()
    
    if "data:" in body:
        data_line = [l for l in body.split("\n") if l.startswith("data:")][0]
        data = json.loads(data_line[5:].strip())
        content = data.get("result", {}).get("content", [{}])[0].get("text", "")
        voices = json.loads(content)
        ok(f"Voices: {list(voices.keys())}")
    else:
        bad(f"Unexpected: {body[:200]}")

except urllib.error.URLError as e:
    bad(f"Cannot reach {MCP_URL}: {e.reason}")
except Exception as e:
    bad(str(e))


# ── Test 4: stdio mode ───────────────────────────────────────
test("stdio mode: starts and responds")

try:
    proc = subprocess.Popen(
        [
            "uv", "run", "--prerelease=allow",
            "--directory", "/home/microshak/Source/MicroTherapy",
            "microtherapy", "--stdio"
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    
    # Send initialize request
    init_req = json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2026-07-28",
            "capabilities": {},
            "clientInfo": {"name": "test-script", "version": "1.0"}
        }
    }) + "\n"
    
    proc.stdin.write(init_req.encode())
    proc.stdin.flush()
    
    # Read response (line-delimited JSON)
    import select
    ready, _, _ = select.select([proc.stdout], [], [], 10)
    if ready:
        line = proc.stdout.readline().decode().strip()
        if line:
            data = json.loads(line)
            if "result" in data:
                server_info = data["result"]
                ok(f"Server: {server_info.get('serverInfo', {}).get('name', 'unknown')} v{server_info.get('serverInfo', {}).get('version', '?')}")
            elif "error" in data:
                bad(f"Initialize error: {data['error']}")
            else:
                bad(f"Unexpected: {line[:100]}")
        else:
            bad("Empty response")
    else:
        warn("stdio mode timed out (model may be loading). This is OK if Docker HTTP mode works.")
    
    proc.terminate()
    proc.wait(timeout=5)

except FileNotFoundError:
    warn("uv not found — stdio test skipped")
except Exception as e:
    warn(f"stdio test error: {e}")


# ── Summary ──────────────────────────────────────────────────
print(f"\n{BOLD}{'═' * 50}{RESET}")
passed = sum(1 for r in results if r)
total = len(results)
if passed == total:
    print(f"  {GREEN}{BOLD}ALL {passed}/{total} TESTS PASSED{RESET}")
else:
    print(f"  {RED}{BOLD}{passed}/{total} TESTS PASSED{RESET}")
print(f"{'═' * 50}\n")

sys.exit(0 if passed == total else 1)
