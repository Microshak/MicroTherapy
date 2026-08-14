"""Embedded HTML audio player view for MCP App."""

from pathlib import Path

VIEW_URI = "ui://microtherapy/view.html"

EMBEDDED_VIEW_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="color-scheme" content="light dark">
<title>MicroTherapy v2</title>
<style>
  :root {
    --mt-bg: #ffffff; --mt-fg: #1a1a2e; --mt-accent: #7c3aed;
    --mt-border: #e2e8f0; --mt-muted: #94a3b8;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --mt-bg: #1e1e2e; --mt-fg: #cdd6f4;
      --mt-border: #45475a; --mt-muted: #6c7086;
    }
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--mt-bg); color: var(--mt-fg); padding: 14px; max-width: 460px;
  }
  .player {
    border: 1px solid var(--mt-border); border-radius: 12px; padding: 16px;
    background: var(--mt-bg);
  }
  .player-header {
    display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;
  }
  .player-title { font-size: 14px; font-weight: 600; display: flex; align-items: center; gap: 6px; }
  .badge {
    font-size: 11px; padding: 2px 10px; border-radius: 10px;
    background: color-mix(in srgb, var(--mt-accent) 15%, transparent); color: var(--mt-accent);
  }
  .player-text {
    font-size: 15px; line-height: 1.5; margin-bottom: 8px; min-height: 44px;
    padding: 10px; border-radius: 8px;
    background: color-mix(in srgb, var(--mt-accent) 6%, transparent);
    white-space: pre-wrap; word-break: break-word;
  }
  .play-btn, .test-btn {
    width: 100%; padding: 10px; border: none; border-radius: 8px;
    font-size: 15px; cursor: pointer; margin-bottom: 8px;
  }
  .play-btn {
    display: none; background: var(--mt-accent); color: white;
  }
  .play-btn:hover { opacity: 0.9; }
  .play-btn.visible { display: block; }
  .test-btn {
    background: color-mix(in srgb, var(--mt-accent) 20%, transparent);
    color: var(--mt-accent); border: 1px solid var(--mt-accent);
  }
  .test-btn:hover { background: color-mix(in srgb, var(--mt-accent) 30%, transparent); }
  .error { color: #ef4444; font-size: 13px; margin-top: 8px; display: none; }
  .debug {
    font-size: 10px; color: var(--mt-muted); margin-top: 8px; max-height: 80px;
    overflow-y: auto; font-family: monospace; white-space: pre-wrap;
    word-break: break-all; border-top: 1px solid var(--mt-border); padding-top: 8px;
  }
</style>
</head>
<body>
<div class="player">
  <div class="player-header">
    <span class="player-title">🎤 MicroTherapy</span>
    <span class="badge" id="badge">Loading...</span>
  </div>
  <div class="player-text" id="text">Waiting for text...</div>
  <button class="play-btn" id="playBtn">▶ Play</button>
  <button class="test-btn" id="replayBtn">🔁 Replay Speech</button>
  <button class="test-btn" id="testBtn">🔊 Test Beep</button>
  <div class="error" id="error"></div>
  <div class="debug" id="debug"></div>
</div>

<script type="importmap">
{
  "imports": {
    "@modelcontextprotocol/ext-apps": "https://esm.sh/@modelcontextprotocol/ext-apps@1.7.5?deps=zod@3.25.1",
    "zod": "https://esm.sh/zod@3.25.1"
  }
}
</script>
<script type="module">
const $ = id => document.getElementById(id);
const badge = $('badge'), textEl = $('text'), playBtn = $('playBtn');
const errorEl = $('error'), debugEl = $('debug');

const SERVER = 'http://localhost:3001';

let lastQueueId = null;  // most recent speak queue, for replay

function log(msg) {
  console.log('[MT]', msg);
  debugEl.textContent += msg + '\n';
}

log('v3 WAV player');

let sdkApp = null;  // SDK app instance, used for proxied tool calls

async function callTool(name, args) {
  // Prefer SDK proxy (bypasses CORS) over direct fetch
  if (sdkApp) {
    try {
      const result = await sdkApp.callServerTool({ name, arguments: args });
      return JSON.parse(result?.content?.[0]?.text || '{}');
    } catch(e) {
      log('SDK call failed: ' + e + ', trying fetch...');
    }
  }
  return callToolDirect(name, args);
}

// Direct HTTP fetch, used for LARGE tool results (host cancels big SDK calls)
async function callToolDirect(name, args) {
  const resp = await fetch(SERVER + '/mcp', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream' },
    body: JSON.stringify({ jsonrpc: '2.0', id: Math.floor(Math.random() * 1e9), method: 'tools/call', params: { name, arguments: args } })
  });
  if (!resp.ok) throw new Error('HTTP ' + resp.status);
  const text = await resp.text();
  // Robust SSE parse: collect all data: lines
  const parts = [];
  for (const line of text.split('\n')) {
    if (line.startsWith('data:')) parts.push(line.slice(5).trim());
  }
  if (!parts.length) throw new Error('No SSE data');
  const r = JSON.parse(parts.join(''));
  if (r.error) throw new Error(r.error.message || 'Tool error');
  return JSON.parse(r.result.content[0].text);
}

function buildWav(pcmBytes, sampleRate) {
  const numChannels = 1;
  const bitsPerSample = 16;
  const byteRate = sampleRate * numChannels * bitsPerSample / 8;
  const blockAlign = numChannels * bitsPerSample / 8;
  const dataSize = pcmBytes.length;
  const headerSize = 44;
  const buf = new ArrayBuffer(headerSize + dataSize);
  const view = new DataView(buf);

  function writeStr(offset, str) {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
  }

  writeStr(0, 'RIFF');
  view.setUint32(4, 36 + dataSize, true);
  writeStr(8, 'WAVE');
  writeStr(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);  // PCM
  view.setUint16(22, numChannels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, byteRate, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, bitsPerSample, true);
  writeStr(36, 'data');
  view.setUint32(40, dataSize, true);

  const pcm = new Uint8Array(buf, 44);
  pcm.set(new Uint8Array(pcmBytes));
  return buf;
}

async function collectAndPlay(queueId) {
  log('Waiting for audio: ' + queueId);
  badge.textContent = 'Generating...';

  // Phase 1: poll lightweight status until the server finishes generating
  for (let i = 0; i < 720; i++) {   // up to ~6 min at 500ms
    let data;
    try {
      data = await callTool('get_speak_status', { audio_id: queueId });
    } catch(e) {
      log('Status poll err: ' + e);
      await new Promise(r => setTimeout(r, 1000));
      continue;
    }

    if (data.status === 'complete') {
      badge.textContent = 'Downloading...';
      return fetchAndPlay(queueId);
    } else if (data.status === 'error') {
      log('Server error: ' + (data.error || 'unknown'));
      badge.textContent = '⚠ ' + (data.error || 'Error');
      return;
    } else {
      const secs = Math.round((data.progress_ms || 0) / 1000);
      badge.textContent = secs > 0 ? ('Generating... ' + secs + 's') : 'Generating...';
      await new Promise(r => setTimeout(r, 500));
    }
  }

  log('Timed out waiting for audio');
  badge.textContent = '⚠ Timeout — click Replay';
}

// Phase 2: download the ONE complete WAV file, then play it
async function fetchAndPlay(queueId) {
  // Preferred: plain file endpoint (simple GET, no JSON/SSE/base64)
  const fileUrl = SERVER + '/audio/' + queueId + '.wav';
  for (let attempt = 0; attempt < 4; attempt++) {
    try {
      const resp = await fetch(fileUrl);
      if (resp.ok) {
        const buf = await resp.arrayBuffer();
        if (buf.byteLength > 44) {
          log('Downloaded WAV via /audio: ' + buf.byteLength + ' bytes');
          return playArrayBuffer(buf);
        }
      }
      log('File endpoint returned ' + resp.status + ' — trying MCP tool');
      // Fallback: full audio via MCP tool (JSON + base64)
      const data = await callToolDirect('get_full_audio', { audio_id: queueId });
      if (data.status === 'complete' && data.audio_b64) {
        log('Got full WAV via MCP tool, ' + data.duration_ms + 'ms');
        const wavBytes = Uint8Array.from(atob(data.audio_b64), c => c.charCodeAt(0));
        return playArrayBuffer(wavBytes.buffer.slice(0));
      }
      if (data.status === 'waiting') {
        // Rare race: status said complete but WAV not built yet — retry soon
        log('WAV not ready yet, retrying...');
        await new Promise(r => setTimeout(r, 500));
        continue;
      }
      log('Status: ' + data.status);
      await new Promise(r => setTimeout(r, 500));
    } catch(e) {
      log('Download attempt ' + (attempt + 1) + ' failed: ' + e);
      await new Promise(r => setTimeout(r, 1000));
    }
  }
  badge.textContent = '⚠ Download error — click Replay';
}

async function playArrayBuffer(arrayBuffer) {
  const ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
  if (ctx.state === 'suspended') {
    try { await ctx.resume(); } catch(e) { log('resume failed: ' + e); }
  }
  if (ctx.state === 'suspended') {
    // Autoplay blocked by the browser — user must click to hear audio
    log('Autoplay blocked — click 🔁 Replay Speech');
    badge.textContent = '🔊 Ready — click Replay';
    return;
  }

  try {
    const audioBuffer = await ctx.decodeAudioData(arrayBuffer);
    const source = ctx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(ctx.destination);
    badge.textContent = 'Playing...';
    source.onended = () => { badge.textContent = 'Done ✓'; ctx.close(); };
    source.start(0);
  } catch(e) {
    log('decodeAudioData failed: ' + e);
    badge.textContent = '⚠ Decode error';
  }
}

function handleSpeakResult(result) {
  log('Result received');
  try {
    const data = JSON.parse(result?.content?.[0]?.text || '{}');
    if (data.queue_id) {
      lastQueueId = data.queue_id;
      textEl.textContent = data.text || '';
      errorEl.style.display = 'none';
      collectAndPlay(data.queue_id);
    } else {
      // No speak queue in this result (e.g. test_play) — play latest speech if any
      checkLatestSpeak();
    }
  } catch(e) { log('Parse err: ' + e); }
}

async function checkLatestSpeak() {
  try {
    const data = await callTool('get_latest_speak', {});
    if (data.queue_id) {
      lastQueueId = data.queue_id;
      textEl.textContent = data.text || '';
      log('Found latest speak: ' + data.queue_id);
      collectAndPlay(data.queue_id);
      return true;
    }
  } catch(e) { log('No latest speak'); }
  return false;
}

async function replaySpeech() {
  const btn = $('replayBtn');
  btn.disabled = true;
  btn.textContent = 'Loading...';
  badge.textContent = 'Replaying...';
  try {
    let queueId = lastQueueId;
    if (!queueId) {
      // No result seen in this view yet — ask the server for the latest queue
      const data = await callTool('get_latest_speak', {});
      queueId = data.queue_id;
      if (queueId) {
        lastQueueId = queueId;
        textEl.textContent = data.text || '';
      }
    }
    if (!queueId) {
      badge.textContent = 'No speech yet';
      textEl.textContent = 'Nothing to replay — no speech has been generated in this session.';
    } else {
      log('Replaying queue: ' + queueId);
      await collectAndPlay(queueId);
    }
  } catch (e) {
    log('Replay failed: ' + e);
    badge.textContent = '⚠ Replay error';
    errorEl.textContent = e.message;
    errorEl.style.display = 'block';
  } finally {
    btn.disabled = false;
    btn.textContent = '🔁 Replay Speech';
  }
}

$('replayBtn').addEventListener('click', replaySpeech);

async function playTestBeep() {
  const btn = $('testBtn');
  btn.disabled = true;
  btn.textContent = 'Loading...';
  badge.textContent = 'Fetching...';
  try {
    const data = await callTool('test_play', {});
    if (data.status !== 'ready') throw new Error(data.error || 'Unknown error');
    const wavBytes = Uint8Array.from(atob(data.audio_b64), c => c.charCodeAt(0));
    const ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: data.sample_rate || 24000 });
    if (ctx.state === 'suspended') await ctx.resume();
    const audioBuffer = await ctx.decodeAudioData(wavBytes.buffer.slice(0));
    const source = ctx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(ctx.destination);
    badge.textContent = 'Playing...';
    source.onended = () => { badge.textContent = 'Done ✓'; ctx.close(); };
    source.start(0);
    textEl.textContent = 'Playing test beep (440 Hz, 1 sec)';
  } catch (e) {
    log('Test beep failed: ' + e);
    badge.textContent = '⚠ Error';
    errorEl.textContent = e.message;
    errorEl.style.display = 'block';
  } finally {
    btn.disabled = false;
    btn.textContent = '🔊 Test Beep';
  }
}

$('testBtn').addEventListener('click', playTestBeep);

// ── Listen for tool results via postMessage ────────────
let _gotResult = false;
window.addEventListener('message', (event) => {
  const data = event.data;
  if (!data || !data.jsonrpc) return;
  if (data.method === 'tools/result' && data.params) {
    log('postMessage received');
    _gotResult = true;
    handleSpeakResult(data.params);
  }
});

// ── SDK init (for fallback) ────────────────────────────
try {
  const { App } = await import('@modelcontextprotocol/ext-apps');
  log('SDK loaded');

  const app = new App({ name: 'MicroTherapy', version: '3.0.0' });
  app.ontoolresult = (result) => { log('SDK result'); handleSpeakResult(result); };
  app.onerror = (err) => { log('Err: ' + (err?.message || err)); };

  log('Connect...');
  await app.connect();
  sdkApp = app;  // enable SDK-proxied tool calls
  log('Connected ✓');
  badge.textContent = 'Ready';

  if (!_gotResult) {
    log('Checking for pending speak...');
    try {
      const data = await callTool('get_latest_speak', {});
      if (data.queue_id) {
        log('Found pending: ' + data.queue_id);
        lastQueueId = data.queue_id;
        textEl.textContent = data.text || '';
        collectAndPlay(data.queue_id);
      }
    } catch(e) { log('No pending speak'); }
  }
} catch(e) {
  log('SDK init failed: ' + (e?.message || e) + ', using direct fetch fallback');
  badge.textContent = 'Ready (direct)';
  
  if (!_gotResult) {
    // Poll for latest speak
    (async function poll() {
      try {
        const data = await callTool('get_latest_speak', {});
        if (data.queue_id) {
          log('Found pending (direct): ' + data.queue_id);
          lastQueueId = data.queue_id;
          textEl.textContent = data.text || '';
          collectAndPlay(data.queue_id);
          return;
        }
      } catch(e) {}
      setTimeout(poll, 1000);
    })();
  }
}
</script>
</body>
</html>"""


def get_view_html() -> str:
    """Get the View HTML, preferring built version from dist/."""
    dist_path = Path(__file__).parent.parent.parent / "dist" / "mcp-app.html"
    if dist_path.exists():
        return dist_path.read_text()
    return EMBEDDED_VIEW_HTML
