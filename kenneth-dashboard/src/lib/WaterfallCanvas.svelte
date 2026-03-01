<script lang="ts">
  import { onMount } from 'svelte';

  export let wsUrl = 'ws://localhost:8766';
  export let centerHz = 156_800_000;
  export let bandwidthHz = 2_000_000;
  export let plotHeight = 260;

  let canvasEl: HTMLCanvasElement;
  let socket: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let reconnectAttempts = 0;
  let connected = false;
  let sourceMode = 'disconnected';
  let frameRateHz = 20;
  let leftHz = centerHz - bandwidthHz / 2;
  let rightHz = centerHz + bandwidthHz / 2;
  let visibleSeconds = Math.max(1, Math.round(plotHeight / frameRateHz));

  function formatMHz(hz: number): string {
    return `${(hz / 1_000_000).toFixed(3)} MHz`;
  }

  function setCanvasSize() {
    if (!canvasEl) return;
    const dpr = window.devicePixelRatio || 1;
    const width = canvasEl.clientWidth;
    const height = plotHeight;

    canvasEl.width = Math.max(1, Math.floor(width * dpr));
    canvasEl.height = Math.max(1, Math.floor(height * dpr));

    const ctx = canvasEl.getContext('2d');
    if (!ctx) return;

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(dpr, dpr);
    ctx.fillStyle = '#071126';
    ctx.fillRect(0, 0, width, height);
  }

  // Inferno colormap LUT — perceptually uniform: black→purple→red→orange→yellow→white
  // Best-in-class for SDR waterfalls. Shows weak signals near noise floor beautifully.
  const INFERNO_LUT = new Uint8Array([
    0,0,4, 1,0,5, 1,1,6, 1,1,8, 2,1,9, 2,2,11, 2,2,13, 3,3,15,
    3,3,18, 4,4,20, 5,4,22, 6,5,24, 6,5,26, 7,6,28, 8,7,30, 9,7,32,
    10,8,34, 11,9,36, 12,9,38, 13,10,41, 14,11,43, 16,11,45, 17,12,47, 18,13,49,
    19,13,52, 20,14,54, 21,14,56, 22,15,59, 24,15,61, 25,16,63, 26,16,66, 28,16,68,
    29,17,71, 30,17,73, 32,17,75, 33,17,78, 34,17,80, 36,18,83, 37,18,85, 39,18,88,
    41,17,90, 42,17,92, 44,17,95, 45,17,97, 47,17,99, 49,17,101, 51,16,103, 52,16,105,
    54,16,107, 56,15,109, 57,15,111, 59,15,113, 61,15,114, 63,15,116, 64,15,117, 66,15,119,
    68,15,120, 69,14,122, 71,14,123, 73,14,124, 74,14,126, 76,14,127, 77,14,128, 79,13,129,
    81,13,130, 82,13,131, 84,13,132, 85,13,133, 87,13,134, 89,13,135, 90,13,136, 92,13,137,
    93,13,138, 95,13,139, 97,13,139, 98,13,140, 100,13,141, 101,13,141, 103,13,142, 105,13,142,
    106,13,143, 108,14,143, 109,14,144, 111,14,144, 113,14,144, 114,14,145, 116,15,145, 117,15,145,
    119,15,145, 120,16,145, 122,16,146, 124,16,146, 125,17,146, 127,17,146, 128,17,146, 130,18,146,
    132,18,146, 133,18,146, 135,19,146, 136,19,146, 138,20,146, 140,20,146, 141,21,146, 143,21,146,
    144,22,146, 146,22,145, 148,23,145, 149,23,145, 151,24,145, 152,24,144, 154,25,144, 156,25,144,
    157,26,143, 159,27,143, 160,27,142, 162,28,142, 163,29,141, 165,29,141, 167,30,140, 168,31,140,
    170,31,139, 171,32,139, 173,33,138, 175,33,137, 176,34,137, 178,35,136, 179,36,135, 181,36,135,
    183,37,134, 184,38,133, 186,39,133, 187,40,132, 189,41,131, 190,42,130, 192,43,129, 194,43,129,
    195,44,128, 197,45,127, 198,46,126, 200,47,125, 201,48,124, 203,49,123, 205,50,122, 206,51,121,
    208,52,120, 209,53,119, 211,54,118, 212,55,117, 214,56,116, 215,57,115, 217,58,114, 218,60,113,
    220,61,112, 221,62,111, 223,63,110, 224,65,109, 226,66,108, 227,67,107, 229,68,106, 230,70,105,
    231,71,104, 233,72,103, 234,74,101, 236,75,100, 237,77,99, 238,78,98, 240,80,97, 241,81,96,
    242,83,95, 244,84,94, 245,86,92, 246,87,91, 247,89,90, 249,91,89, 250,92,88, 251,94,87,
    252,96,85, 253,97,84, 254,99,83, 254,101,82, 255,103,80, 255,105,79, 255,107,78, 255,109,77,
    255,111,75, 255,113,74, 255,115,72, 255,117,71, 255,119,70, 255,121,68, 255,123,67, 255,125,65,
    255,127,64, 255,129,62, 255,131,61, 255,133,59, 255,135,58, 255,137,56, 255,139,55, 255,141,53,
    255,143,52, 254,145,50, 254,148,49, 254,150,47, 254,152,46, 254,154,44, 253,156,43, 253,158,41,
    253,161,40, 253,163,38, 252,165,37, 252,167,35, 252,169,34, 251,172,33, 251,174,31, 250,176,30,
    250,178,28, 249,181,27, 249,183,26, 248,185,24, 248,187,23, 247,190,22, 247,192,20, 246,194,19,
    246,197,18, 245,199,16, 244,201,15, 244,204,14, 243,206,13, 243,208,12, 242,211,10, 242,213,9,
    241,215,9, 240,218,8, 240,220,7, 239,223,6, 238,225,6, 238,227,5, 237,230,5, 236,232,4,
    236,235,4, 235,237,3, 234,240,3, 234,242,3, 233,245,3, 232,247,3, 232,250,3, 231,252,4
  ]);
  const MIN_DBFS = -120;
  const MAX_DBFS = -20;
  function dbfsToLutIdx(v: number): number {
    return Math.round(Math.max(0, Math.min(1, (v - MIN_DBFS) / (MAX_DBFS - MIN_DBFS))) * 255);
  }

  function sendConfig() {
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(
      JSON.stringify({
        type: 'set_config',
        center_hz: centerHz,
        bandwidth_hz: Math.max(2_000_000, bandwidthHz),
      })
    );
  }

  function drawRow(dbfs: number[]) {
    const ctx = canvasEl?.getContext('2d');
    if (!ctx) return;
    const w = canvasEl.width;
    const h = plotHeight;
    // Scroll down 1px (fast GPU blit)
    ctx.drawImage(canvasEl, 0, 0, w, h - 1, 0, 1, w, h - 1);
    // Paint new top row with Inferno LUT via putImageData — no fillRect loop
    const rowData = new Uint8ClampedArray(w * 4);
    for (let x = 0; x < w; x++) {
      const binIdx = Math.floor((x / w) * dbfs.length);
      const val = dbfs[Math.min(dbfs.length - 1, binIdx)] ?? MIN_DBFS;
      const lut = dbfsToLutIdx(val) * 3;
      rowData[x * 4]     = INFERNO_LUT[lut];
      rowData[x * 4 + 1] = INFERNO_LUT[lut + 1];
      rowData[x * 4 + 2] = INFERNO_LUT[lut + 2];
      rowData[x * 4 + 3] = 255;
    }
    ctx.putImageData(new ImageData(rowData, w, 1), 0, 0);
  }

  function connect() {
    if (socket) socket.close();

    socket = new WebSocket(wsUrl);

    socket.addEventListener('open', () => {
      connected = true;
      reconnectAttempts = 0;
      sendConfig();
    });

    socket.addEventListener('message', (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type !== 'spectrum' || !Array.isArray(payload.dbfs)) return;

        frameRateHz = payload.frame_rate_hz ?? frameRateHz;
        sourceMode = payload.source ?? sourceMode;
        drawRow(payload.dbfs as number[]);
      } catch {
        // Ignore malformed websocket messages to keep stream rendering.
      }
    });

    socket.addEventListener('close', () => {
      connected = false;
      sourceMode = 'reconnecting';
      reconnectAttempts += 1;

      const delay = Math.min(5_000, 500 + reconnectAttempts * 400);
      reconnectTimer = setTimeout(connect, delay);
    });

    socket.addEventListener('error', () => {
      connected = false;
      sourceMode = 'error';
    });
  }

  $: if (connected) {
    sendConfig();
  }

  $: leftHz = centerHz - bandwidthHz / 2;
  $: rightHz = centerHz + bandwidthHz / 2;
  $: visibleSeconds = Math.max(1, Math.round(plotHeight / frameRateHz));

  onMount(() => {
    setCanvasSize();
    connect();

    const resizeObserver = new ResizeObserver(() => setCanvasSize());
    resizeObserver.observe(canvasEl);

    return () => {
      resizeObserver.disconnect();
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (socket) socket.close();
    };
  });
</script>

<div class="waterfall-panel">
  <div class="meta-row">
    <span class:up={connected} class:down={!connected}>{connected ? 'WS LIVE' : 'WS OFFLINE'}</span>
    <span>{sourceMode.toUpperCase()}</span>
    <span>{formatMHz(centerHz)} center</span>
    <span>{(bandwidthHz / 1_000_000).toFixed(1)} MHz span</span>
  </div>

  <div class="axis-row">
    <span>{formatMHz(leftHz)}</span>
    <span>{formatMHz(centerHz)}</span>
    <span>{formatMHz(rightHz)}</span>
  </div>

  <div class="plot-wrap">
    <div class="time-axis">
      <span>Now</span>
      <span>{visibleSeconds}s ago</span>
    </div>
    <canvas bind:this={canvasEl} class="waterfall-canvas" style={`height:${plotHeight}px`}></canvas>
  </div>
</div>

<style>
  .waterfall-panel {
    background: #0b1527;
    border: 1px solid #1e293b;
    border-radius: 6px;
    overflow: hidden;
  }

  .meta-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.45rem 0.75rem;
    border-bottom: 1px solid #1e293b;
    font-family: 'Fira Code', monospace;
    font-size: 0.62rem;
    color: #94a3b8;
  }

  .meta-row .up { color: #4ade80; }
  .meta-row .down { color: #ef4444; }

  .axis-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    padding: 0.35rem 0.75rem;
    border-bottom: 1px solid #1e293b;
    font-size: 0.62rem;
    color: #64748b;
    font-family: 'Fira Code', monospace;
  }

  .axis-row span:nth-child(2) {
    text-align: center;
    color: #f8fafc;
  }

  .axis-row span:last-child {
    text-align: right;
  }

  .plot-wrap {
    display: grid;
    grid-template-columns: 54px 1fr;
  }

  .time-axis {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: 0.5rem 0.4rem;
    font-family: 'Fira Code', monospace;
    font-size: 0.6rem;
    color: #64748b;
    border-right: 1px solid #1e293b;
    background: #081224;
  }

  .waterfall-canvas {
    width: 100%;
    display: block;
    background: #071126;
    image-rendering: pixelated;
  }

  @media (max-width: 900px) {
    .plot-wrap {
      grid-template-columns: 44px 1fr;
    }

    .meta-row {
      flex-wrap: wrap;
      gap: 0.4rem 0.7rem;
    }
  }
</style>
