<script lang="ts">
  // Kenneth RF Intelligence -- Dashboard
  // L'Avalanche design language: Tufte density, no emoji, pure typography
  import { onMount } from 'svelte';
  import WaterfallCanvas from '$lib/WaterfallCanvas.svelte';

  const SENTINEL_API = '';
  const AUDIO_API = 'http://localhost:8765';

  interface FreqTarget {
    id: string;
    name: string;
    freq: string;
    band: 'maritime' | 'aviation' | 'broadcast';
    priority: 'critical' | 'high' | 'medium' | 'low';
    desc: string;
  }

  interface PipelineStage {
    name: string;
    status: 'ready' | 'running' | 'offline' | 'pending';
    detail: string;
  }

  interface CaptureFile {
    name: string;
    freq: string;
    band: string;
    size: string;
    date: string;
    hasSpeech: boolean;
    stressLevel?: number;
  }

  interface WaterfallPreset {
    id: string;
    label: string;
    centerHz: number;
    bandwidthHz: number;
  }

  const FREQ_TARGETS: FreqTarget[] = [
    { id: 'CH16', name: 'Distress / Calling', freq: '156.800', band: 'maritime', priority: 'critical', desc: 'International emergency channel, monitored 24/7' },
    { id: 'CH13', name: 'Bridge-to-Bridge', freq: '156.650', band: 'maritime', priority: 'high', desc: 'Ship navigation safety' },
    { id: 'CH22A', name: 'Coast Guard', freq: '157.100', band: 'maritime', priority: 'high', desc: 'Official coast guard traffic' },
    { id: 'CH09', name: 'General Calling', freq: '156.450', band: 'maritime', priority: 'medium', desc: 'Commercial vessel comms' },
    { id: 'CH06', name: 'Ship Safety', freq: '156.300', band: 'maritime', priority: 'medium', desc: 'Inter-ship safety' },
    { id: 'EMER', name: 'Aviation Emergency', freq: '121.500', band: 'aviation', priority: 'critical', desc: 'International aviation distress' },
    { id: 'TWR', name: 'Malta Tower', freq: '119.100', band: 'aviation', priority: 'high', desc: 'Luqa approach/tower control' },
    { id: 'A2A', name: 'Air-to-Air', freq: '122.750', band: 'aviation', priority: 'low', desc: 'Pilot-to-pilot chat' },
  ];

  const WATERFALL_PRESETS: WaterfallPreset[] = [
    { id: 'CH16', label: 'Maritime Distress -- 156.800 MHz', centerHz: 156_800_000, bandwidthHz: 2_000_000 },
    { id: 'CH13', label: 'Bridge-to-Bridge -- 156.650 MHz', centerHz: 156_650_000, bandwidthHz: 2_000_000 },
    { id: 'CH22A', label: 'Coast Guard -- 157.100 MHz', centerHz: 157_100_000, bandwidthHz: 2_000_000 },
    { id: 'CH09', label: 'General Calling -- 156.450 MHz', centerHz: 156_450_000, bandwidthHz: 2_000_000 },
    { id: 'EMER', label: 'Aviation Emergency -- 121.500 MHz', centerHz: 121_500_000, bandwidthHz: 2_000_000 },
    { id: 'TWR', label: 'Malta Tower -- 119.100 MHz', centerHz: 119_100_000, bandwidthHz: 2_000_000 },
    { id: 'A2A', label: 'Air-to-Air -- 122.750 MHz', centerHz: 122_750_000, bandwidthHz: 2_000_000 },
  ];

  const PIPELINE: PipelineStage[] = [
    { name: 'SDR Capture', status: 'offline', detail: 'RSPdx / RTL-SDR / HackRF' },
    { name: 'FM Demod', status: 'ready', detail: 'IQ to audio pipeline' },
    { name: 'Silero VAD', status: 'ready', detail: 'Voice activity detection' },
    { name: 'Stress Classifier', status: 'ready', detail: 'RAVDESS-trained model' },
    { name: 'Speaker Profile', status: 'ready', detail: 'Gender / age estimation' },
    { name: 'Whisper STT', status: 'ready', detail: 'faster-whisper base' },
    { name: 'Translation', status: 'ready', detail: 'Maltese / Arabic / Italian' },
    { name: 'Telegram Alert', status: 'pending', detail: 'Embassy relay' },
  ];

  let sentinelOnline = $state(false);
  let workshopOnline = $state(false);
  let sdrConnected = $state(false);
  let captureFiles = $state<CaptureFile[]>([]);
  let loading = $state(true);
  let stressModels = $state({ vad: '', transcription: '', classifier: '' });
  let selectedWaterfall = $state('CH16');

  async function fetchWithTimeout(url: string, timeoutMs = 1600): Promise<Response> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    try {
      return await fetch(url, { signal: controller.signal });
    } finally {
      clearTimeout(timeout);
    }
  }

  async function init() {
    loading = true;

    // Check workshop audio server
    try {
      const res = await fetchWithTimeout(`${AUDIO_API}/health`);
      workshopOnline = res.ok;
    } catch { workshopOnline = false; }

    // Check sentinel API
    try {
      const res = await fetchWithTimeout(`${SENTINEL_API}/api/sentinel/status`);
      if (res.ok) {
        const data = await res.json();
        sentinelOnline = true;
        sdrConnected = data.sdr?.available ?? false;
        stressModels = {
          vad: data.models?.vad ?? '',
          transcription: data.models?.transcription ?? '',
          classifier: data.calibrated ? 'RF-Calibrated' : 'Uncalibrated',
        };
      }
    } catch { sentinelOnline = false; }

    // Scan capture files
    try {
      const res = await fetchWithTimeout(`${SENTINEL_API}/api/sentinel/recent-alerts`);
      if (res.ok) {
        const data = await res.json();
        captureFiles = (data.alerts || []).map((a: any) => ({
          name: a.file,
          freq: '',
          band: '',
          size: '',
          date: a.timestamp || '',
          hasSpeech: a.has_speech,
          stressLevel: a.max_stress,
        }));
      }
    } catch {}

    loading = false;
  }

  onMount(() => {
    init();
  });

  let totalCaptures = $derived(captureFiles.length);
  let speechDetections = $derived(captureFiles.filter(c => c.hasSpeech).length);
  let alertCount = $derived(captureFiles.filter(c => (c.stressLevel ?? 0) > 0.55).length);
  let maritimeTargets = $derived(FREQ_TARGETS.filter(f => f.band === 'maritime'));
  let aviationTargets = $derived(FREQ_TARGETS.filter(f => f.band === 'aviation'));
  let selectedWaterfallTarget = $derived(
    WATERFALL_PRESETS.find((preset) => preset.id === selectedWaterfall) ?? WATERFALL_PRESETS[0]
  );

  function priorityColor(p: string): string {
    if (p === 'critical') return '#ef4444';
    if (p === 'high') return '#f59e0b';
    if (p === 'medium') return '#6366f1';
    return '#475569';
  }

  function stressColor(v: number): string {
    if (v < 0.35) return '#4ade80';
    if (v < 0.55) return '#f59e0b';
    return '#ef4444';
  }

  function statusColor(s: string): string {
    if (s === 'ready' || s === 'running') return '#4ade80';
    if (s === 'pending') return '#f59e0b';
    return '#ef4444';
  }

  function timeAgo(ts: string): string {
    if (!ts) return '';
    const diff = Date.now() - new Date(ts).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  }
</script>

<svelte:head>
  <title>Kenneth -- RF Intelligence Dashboard</title>
</svelte:head>

<main>
  <header>
    <div class="header-left">
      <h1>RF Intelligence Dashboard</h1>
      <span class="subtitle">Kenneth SIGINT -- Gozo, Malta -- Mediterranean Coverage</span>
    </div>
    <div class="header-right">
      <span class="server-status" class:ok={workshopOnline} class:err={!workshopOnline}>
        {workshopOnline ? 'WORKSHOP ONLINE' : 'WORKSHOP OFFLINE'}
      </span>
      <span class="server-status" class:ok={sentinelOnline} class:err={!sentinelOnline}>
        {sentinelOnline ? 'SENTINEL ONLINE' : 'SENTINEL OFFLINE'}
      </span>
    </div>
  </header>

  {#if loading}
    <div class="loading">Connecting to Kenneth infrastructure...</div>
  {:else}

  <!-- Stats strip -->
  <div class="stats-strip">
    <div class="stat-card accent-amber">
      <div class="stat-value">{sdrConnected ? 'CONNECTED' : 'OFFLINE'}</div>
      <div class="stat-label">SDR Hardware</div>
    </div>
    <div class="stat-card accent-indigo">
      <div class="stat-value">{FREQ_TARGETS.length}</div>
      <div class="stat-label">Target Frequencies</div>
    </div>
    <div class="stat-card accent-green">
      <div class="stat-value">{totalCaptures}</div>
      <div class="stat-label">Total Captures</div>
    </div>
    <div class="stat-card accent-cyan">
      <div class="stat-value">{speechDetections}</div>
      <div class="stat-label">Speech Detected</div>
    </div>
    <div class="stat-card accent-red">
      <div class="stat-value">{alertCount}</div>
      <div class="stat-label">Stress Alerts</div>
    </div>
  </div>

  <!-- Pipeline status -->
  <section class="section">
    <h2>Pipeline Architecture</h2>
    <p class="section-desc">Eight-stage processing chain. SDR capture through Telegram alert delivery via the Embassy.</p>

    <div class="pipeline-matrix">
      {#each PIPELINE as stage, i}
        <div class="pipeline-row">
          <span class="pipe-num">{i + 1}</span>
          <span class="pipe-name">{stage.name}</span>
          <span class="pipe-detail">{stage.detail}</span>
          <span class="pipe-status" style="color: {statusColor(stage.status)}">
            {stage.status.toUpperCase()}
          </span>
        </div>
      {/each}
    </div>
  </section>

  <!-- Live waterfall -->
  <section class="section">
    <h2>Live Spectrum Waterfall</h2>
    <p class="section-desc">Realtime 2 MHz FFT span from SDRplay RSPdx-R2 websocket stream (simulated fallback if SDR unavailable).</p>

    <div class="waterfall-controls">
      <label for="waterfall-preset">Center Frequency</label>
      <select id="waterfall-preset" bind:value={selectedWaterfall}>
        {#each WATERFALL_PRESETS as preset}
          <option value={preset.id}>{preset.label}</option>
        {/each}
      </select>
    </div>

    <WaterfallCanvas centerHz={selectedWaterfallTarget.centerHz} bandwidthHz={selectedWaterfallTarget.bandwidthHz} />
  </section>

  <!-- Frequency targets -->
  <section class="section">
    <h2>Frequency Targets -- Maritime VHF</h2>
    <p class="section-desc">Mediterranean maritime band. Primary coverage: Malta Channel, Comino Strait, Gozo approaches.</p>

    <div class="freq-matrix">
      {#each maritimeTargets as f}
        <div class="freq-row" style="border-left-color: {priorityColor(f.priority)}">
          <span class="freq-badge" style="background: {priorityColor(f.priority)}">{f.id}</span>
          <div class="freq-info">
            <span class="freq-name">{f.name}</span>
            <span class="freq-desc">{f.desc}</span>
          </div>
          <span class="freq-value">{f.freq} MHz</span>
          <span class="freq-priority" style="color: {priorityColor(f.priority)}">{f.priority}</span>
        </div>
      {/each}
    </div>
  </section>

  <section class="section">
    <h2>Frequency Targets -- Aviation</h2>
    <p class="section-desc">Luqa International and overflights. Emergency, tower, and inter-pilot communications.</p>

    <div class="freq-matrix">
      {#each aviationTargets as f}
        <div class="freq-row" style="border-left-color: {priorityColor(f.priority)}">
          <span class="freq-badge" style="background: {priorityColor(f.priority)}">{f.id}</span>
          <div class="freq-info">
            <span class="freq-name">{f.name}</span>
            <span class="freq-desc">{f.desc}</span>
          </div>
          <span class="freq-value">{f.freq} MHz</span>
          <span class="freq-priority" style="color: {priorityColor(f.priority)}">{f.priority}</span>
        </div>
      {/each}
    </div>
  </section>

  <!-- Recent captures -->
  <section class="section">
    <h2>Recent Captures</h2>
    <p class="section-desc">Voice detections from sentinel scanning. Click to open full analysis in Sentinel view.</p>

    {#if captureFiles.length === 0}
      <div class="empty-state">
        No captures yet. Start the sentinel to begin scanning target frequencies.
      </div>
    {:else}
      <div class="capture-grid">
        {#each captureFiles as cap}
          <a href="/sentinel" class="capture-card" class:has-speech={cap.hasSpeech} class:alert={cap.stressLevel && cap.stressLevel > 0.55}>
            <div class="capture-header">
              <span class="capture-name">{cap.name}</span>
              <span class="capture-time">{timeAgo(cap.date)}</span>
            </div>
            {#if cap.hasSpeech}
              <div class="capture-speech">
                Speech detected
                {#if cap.stressLevel !== undefined}
                  <span class="stress-tag" style="background: {stressColor(cap.stressLevel)}20; color: {stressColor(cap.stressLevel)}">
                    stress {(cap.stressLevel * 100).toFixed(0)}%
                  </span>
                {/if}
              </div>
            {:else}
              <div class="capture-nospeech">No speech</div>
            {/if}
          </a>
        {/each}
      </div>
    {/if}
  </section>

  <!-- Model status -->
  <section class="section">
    <h2>Model Status</h2>
    <div class="model-strip">
      <div class="model-card">
        <span class="model-label">Voice Activity</span>
        <span class="model-value">{stressModels.vad || 'Silero VAD'}</span>
      </div>
      <div class="model-card">
        <span class="model-label">Transcription</span>
        <span class="model-value">{stressModels.transcription || 'faster-whisper'}</span>
      </div>
      <div class="model-card">
        <span class="model-label">Stress Classifier</span>
        <span class="model-value">{stressModels.classifier || 'RAVDESS'}</span>
      </div>
      <div class="model-card">
        <span class="model-label">Coverage</span>
        <span class="model-value">1 MHz -- 6 GHz</span>
      </div>
    </div>
  </section>

  {/if}

  <footer>
    <span>Kenneth RF Intelligence -- Gozo, Malta</span>
    <span>35.9N, 14.5E -- {new Date().toISOString().split('T')[0]}</span>
  </footer>
</main>

<style>
  main {
    max-width: 1100px;
    margin: 0 auto;
    padding: 1.25rem 1.5rem;
  }

  header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 1.25rem;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid #1e293b;
  }

  h1 { font-size: 1.1rem; font-weight: 600; color: #f1f5f9; margin: 0; letter-spacing: -0.02em; }
  .subtitle { font-size: 0.65rem; color: #475569; text-transform: uppercase; letter-spacing: 0.05em; }
  .header-right { display: flex; align-items: center; gap: 0.5rem; }

  .server-status {
    padding: 2px 8px; border-radius: 3px;
    font-family: 'Fira Code', monospace;
    font-size: 0.6rem; font-weight: 600; letter-spacing: 0.05em;
  }
  .server-status.ok { background: #22c55e18; color: #4ade80; }
  .server-status.err { background: #ef444418; color: #ef4444; }

  /* Stats */
  .stats-strip { display: flex; gap: 0.5rem; margin-bottom: 1.5rem; }
  .stat-card {
    flex: 1; padding: 0.6rem 0.75rem;
    background: #131c2e; border-radius: 4px; border-left: 2px solid #1e293b;
  }
  .accent-amber { border-left-color: #f59e0b; }
  .accent-indigo { border-left-color: #6366f1; }
  .accent-green { border-left-color: #22c55e; }
  .accent-cyan { border-left-color: #06b6d4; }
  .accent-red { border-left-color: #ef4444; }

  .stat-value { font-size: 1.1rem; font-weight: 700; color: #f1f5f9; }
  .stat-label { font-size: 0.6rem; color: #475569; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 2px; }

  /* Sections */
  .section { margin-bottom: 2rem; }
  .section h2 { font-size: 0.75rem; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.08em; margin: 0 0 0.25rem; }
  .section-desc { font-size: 0.75rem; color: #334155; margin: 0 0 0.75rem; }

  .waterfall-controls {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin-bottom: 0.75rem;
    font-size: 0.65rem;
    color: #94a3b8;
  }

  .waterfall-controls label {
    font-family: 'Fira Code', monospace;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .waterfall-controls select {
    min-width: 280px;
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 4px;
    color: #e2e8f0;
    padding: 0.35rem 0.45rem;
    font-size: 0.72rem;
  }

  /* Pipeline matrix */
  .pipeline-matrix { display: flex; flex-direction: column; gap: 3px; }
  .pipeline-row {
    display: grid;
    grid-template-columns: 24px 1fr 1.5fr 80px;
    gap: 0.5rem; align-items: center;
    padding: 0.45rem 0.75rem; background: #131c2e; border-radius: 3px;
    transition: background 0.15s;
  }
  .pipeline-row:hover { background: #1e293b; }

  .pipe-num {
    font-family: 'Fira Code', monospace; font-size: 0.6rem;
    color: #f59e0b; font-weight: 700;
  }
  .pipe-name { font-size: 0.8rem; font-weight: 600; color: #f1f5f9; }
  .pipe-detail { font-size: 0.65rem; color: #475569; font-family: 'Fira Code', monospace; }
  .pipe-status {
    font-family: 'Fira Code', monospace; font-size: 0.6rem;
    font-weight: 600; letter-spacing: 0.05em; text-align: right;
  }

  /* Frequency matrix */
  .freq-matrix { display: flex; flex-direction: column; gap: 4px; }
  .freq-row {
    display: grid;
    grid-template-columns: 42px 1fr 110px 70px;
    gap: 0.5rem; align-items: center;
    padding: 0.5rem 0.75rem; background: #131c2e; border-radius: 4px;
    border-left: 3px solid #1e293b; transition: all 0.15s;
  }
  .freq-row:hover { background: #1e293b; }

  .freq-badge {
    display: inline-block; padding: 2px 0; border-radius: 3px;
    color: #fff; font-size: 0.55rem; font-weight: 700;
    text-align: center; font-family: 'Fira Code', monospace;
    letter-spacing: 0.02em;
  }
  .freq-info { min-width: 0; }
  .freq-name { display: block; font-size: 0.8rem; font-weight: 600; color: #f1f5f9; }
  .freq-desc { display: block; font-size: 0.6rem; color: #475569; }
  .freq-value {
    font-family: 'Fira Code', monospace; font-size: 0.75rem; color: #fbbf24;
    background: #f59e0b10; padding: 2px 6px; border-radius: 3px; text-align: center;
  }
  .freq-priority {
    font-family: 'Fira Code', monospace; font-size: 0.6rem;
    font-weight: 600; text-align: right; text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  /* Capture grid */
  .capture-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 0.5rem; }
  .capture-card {
    display: block; padding: 0.65rem; background: #131c2e; border-radius: 5px;
    border: 1px solid #1e293b; text-decoration: none; color: inherit; transition: all 0.15s;
    cursor: pointer;
  }
  .capture-card:hover { border-color: #334155; background: #1e293b; }
  .capture-card.has-speech { border-color: #22c55e20; }
  .capture-card.alert { border-color: #ef444430; }

  .capture-header { display: flex; justify-content: space-between; margin-bottom: 0.3rem; }
  .capture-name { font-family: 'Fira Code', monospace; font-size: 0.65rem; color: #94a3b8; }
  .capture-time { font-size: 0.6rem; color: #334155; }
  .capture-speech { font-size: 0.75rem; color: #4ade80; font-weight: 600; display: flex; align-items: center; gap: 0.4rem; }
  .capture-nospeech { font-size: 0.7rem; color: #334155; }

  .stress-tag {
    font-family: 'Fira Code', monospace; font-size: 0.55rem;
    padding: 1px 5px; border-radius: 2px; font-weight: 600;
  }

  /* Model strip */
  .model-strip { display: flex; gap: 0.5rem; }
  .model-card {
    flex: 1; padding: 0.5rem 0.75rem;
    background: #131c2e; border-radius: 4px;
  }
  .model-label { display: block; font-size: 0.55rem; color: #475569; text-transform: uppercase; letter-spacing: 0.05em; }
  .model-value { display: block; font-size: 0.75rem; color: #94a3b8; font-family: 'Fira Code', monospace; margin-top: 2px; }

  /* Empty state */
  .empty-state {
    padding: 1.5rem; background: #131c2e; border-radius: 4px;
    font-size: 0.75rem; color: #334155; text-align: center;
  }

  /* Footer */
  footer {
    display: flex; justify-content: space-between;
    padding-top: 0.75rem; border-top: 1px solid #1e293b;
    font-size: 0.6rem; color: #334155;
  }

  .loading { text-align: center; padding: 3rem; color: #475569; }

  @media (max-width: 900px) {
    .stats-strip { flex-wrap: wrap; }
    .stat-card { flex: 1 1 45%; }
    .freq-row { grid-template-columns: 42px 1fr 90px; }
    .freq-priority { display: none; }
    .model-strip { flex-wrap: wrap; }
    .model-card { flex: 1 1 45%; }
    .waterfall-controls { flex-direction: column; align-items: flex-start; }
    .waterfall-controls select { width: 100%; min-width: 0; }
  }
</style>
