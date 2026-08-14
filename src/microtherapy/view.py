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
  .play-btn {
    display: none; width: 100%; padding: 10px; border: none; border-radius: 8px;
    background: var(--mt-accent); color: white; font-size: 15px; cursor: pointer;
    margin-bottom: 8px;
  }
  .play-btn:hover { opacity: 0.9; }
  .play-btn.visible { display: block; }
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
  <div class="error" id="error"></div>
  <div class="debug" id="debug"></div>
</div>

<script type="importmap">
{
  "imports": {
    "@modelcontextprotocol/ext-apps": "https://esm.sh/@modelcontextprotocol/ext-apps@1.7.5"
  }
}
</script>
<script type="module">
const $ = id => document.getElementById(id);
const badge = $('badge'), textEl = $('text'), playBtn = $('playBtn');
const errorEl = $('error'), debugEl = $('debug');

const SERVER = 'http://localhost:3001';

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
  // Direct fetch fallback
  const resp = await fetch(SERVER + '/mcp', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name, arguments: args } })
  });
  const text = await resp.text();
  const match = text.match(/data:\s*(\{.*\})/);
  if (!match) throw new Error('No SSE data');
  const r = JSON.parse(match[1]);
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
  badge.textContent = 'Loading...';
  
  // Poll for the complete WAV
  for (let i = 0; i < 300; i++) {
    try {
      const data = await callTool('get_full_audio', { audio_id: queueId });
      
      if (data.status === 'complete') {
        log('Got full WAV, ' + data.duration_ms + 'ms');
        
        // Decode base64 WAV and play via Web Audio API
        const wavBytes = Uint8Array.from(atob(data.audio_b64), c => c.charCodeAt(0));
        
        const ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
        if (ctx.state === 'suspended') await ctx.resume();
        
        try {
          const audioBuffer = await ctx.decodeAudioData(wavBytes.buffer.slice(0));
          const source = ctx.createBufferSource();
          source.buffer = audioBuffer;
          source.connect(ctx.destination);
          
          badge.textContent = 'Playing...';
          source.onended = () => { badge.textContent = 'Done ✓'; ctx.close(); };
          source.start(0);
          return;
        } catch(e) {
          log('decodeAudioData failed: ' + e);
          badge.textContent = '⚠ Decode error';
          return;
        }
      } else if (data.status === 'waiting') {
        await new Promise(r => setTimeout(r, 100));
      } else {
        log('Status: ' + data.status);
        await new Promise(r => setTimeout(r, 100));
      }
    } catch(e) {
      log('Poll err: ' + e);
      await new Promise(r => setTimeout(r, 200));
    }
  }
  
  log('Timed out waiting for audio');
  badge.textContent = '⚠ Timeout';
}

function handleSpeakResult(result) {
  log('Result received');
  try {
    const data = JSON.parse(result?.content?.[0]?.text || '{}');
    if (data.queue_id) {
      textEl.textContent = data.text || '';
      errorEl.style.display = 'none';
      collectAndPlay(data.queue_id);
    }
  } catch(e) { log('Parse err: ' + e); }
}

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
