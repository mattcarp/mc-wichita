<script lang="ts">
  // Kenneth Sentinel -- Real-time RF monitoring and analysis
  // L'Avalanche design language

  const API = '';

  interface SystemStatus {
    online: boolean;
    sdr: { available: boolean; device: any };
    models: Record<string, string>;
    calibrated: boolean;
    captures: { total_files: number };
    location: { city: string; island: string; country: string };
  }

  interface Alert {
    file: string;
    has_speech: boolean;
    max_stress: number;
    alert_triggered: boolean;
    timestamp: string;
    transcription_preview: string | null;
    language: string | null;
  }

  interface Band {
    name: string;
    range: string;
    channels: number;
    priority: string;
    status: string;
    key_frequencies: Array<{ name: string; freq: string; priority: string }>;
  }

  let status: SystemStatus | null = $state(null);
  let alerts: Alert[] = $state([]);
  let bands: Band[] = $state([]);
  let loading = $state(true);
  let error = $state('');
  let selectedCapture: any = $state(null);
  let analyzing = $state(false);

  async function fetchAll() {
    try {
      const [statusRes, alertsRes, bandsRes] = await Promise.all([
        fetch(`${API}/api/sentinel/status`),
        fetch(`${API}/api/sentinel/recent-alerts`),
        fetch(`${API}/api/sentinel/frequency-bands`),
      ]);
      if (statusRes.ok) status = await statusRes.json();
      if (alertsRes.ok) {
        const data = await alertsRes.json();
        alerts = data.alerts || [];
      }
      if (bandsRes.ok) {
        const data = await bandsRes.json();
        bands = data.bands || [];
      }
      loading = false;
    } catch (e: any) {
      error = `Cannot reach sentinel API at ${API}`;
      loading = false;
    }
  }

  async function analyzeCapture(filename: string) {
    analyzing = true;
    try {
      const res = await fetch(`${API}/api/sentinel/analyze/${filename}`);
      if (res.ok) selectedCapture = await res.json();
    } catch (e) { console.error('Analysis failed', e); }
    analyzing = false;
  }

  $effect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 10000);
    return () => clearInterval(interval);
  });

  function stressColor(v: number): string {
    if (v < 0.35) return '#4ade80';
    if (v < 0.55) return '#f59e0b';
    return '#ef4444';
  }

  function priorityColor(p: string): string {
    if (p === 'critical') return '#ef4444';
    if (p === 'high') return '#f59e0b';
    return '#4ade80';
  }

  function timeAgo(ts: string): string {
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
  <title>Kenneth -- Sentinel</title>
</svelte:head>

<main>
  <header>
    <div class="header-left">
      <h1>Sentinel Monitor</h1>
      <span class="subtitle">Real-time RF scanning and voice stress analysis</span>
    </div>
    <div class="header-right">
      {#if status}
        <span class="server-status ok">SENTINEL ONLINE</span>
      {:else if !loading}
        <span class="server-status err">SENTINEL OFFLINE</span>
      {/if}
    </div>
  </header>

  {#if loading}
    <div class="loading">Connecting to Kenneth Sentinel...</div>
  {:else if error}
    <div class="error-state">
      <p>{error}</p>
      <p class="hint">Start the sentinel API: <code>python kenneth_sentinel_api.py</code></p>
    </div>
  {:else}

  <!-- Status bar -->
  <div class="status-bar">
    <div class="status-item">
      <span class="dot" class:online={status?.sdr?.available} class:offline={!status?.sdr?.available}></span>
      <span class="status-label">SDR</span>
      <span class="status-detail">{status?.sdr?.device?.label ?? 'Not connected'}</span>
    </div>
    <div class="status-item">
      <span class="dot online"></span>
      <span class="status-label">VAD</span>
      <span class="status-detail">{status?.models?.vad ?? 'Silero'}</span>
    </div>
    <div class="status-item">
      <span class="dot" class:online={status?.calibrated} class:offline={!status?.calibrated}></span>
      <span class="status-label">Stress</span>
      <span class="status-detail">{status?.calibrated ? 'RF-Calibrated' : 'Uncalibrated'}</span>
    </div>
    <div class="status-item">
      <span class="dot online"></span>
      <span class="status-label">STT</span>
      <span class="status-detail">{status?.models?.transcription ?? 'Whisper'}</span>
    </div>
    <div class="status-item location">
      <span class="status-label">{status?.location?.city}, {status?.location?.island}</span>
      <span class="status-detail">{status?.location?.country}</span>
    </div>
  </div>

  <!-- Frequency bands -->
  <section class="section">
    <h2>Frequency Bands</h2>
    <div class="bands-grid">
      {#each bands as band}
        <div class="band-card">
          <div class="band-header">
            <span class="band-name">{band.name}</span>
            <span class="band-range">{band.range}</span>
            <span class="band-status" class:active={band.status === 'monitoring'}>{band.status}</span>
          </div>
          <div class="band-freqs">
            {#each band.key_frequencies as freq}
              <div class="band-freq-row">
                <span class="bf-dot" style="background: {priorityColor(freq.priority)}"></span>
                <span class="bf-name">{freq.name}</span>
                <span class="bf-value">{freq.freq}</span>
              </div>
            {/each}
          </div>
        </div>
      {/each}
    </div>
  </section>

  <!-- Two-column: alerts + analysis -->
  <div class="content-grid">
    <section class="section">
      <h2>Voice Detections</h2>
      {#if alerts.length === 0}
        <div class="empty-state">No voice detections yet. Run the sentinel to begin scanning.</div>
      {:else}
        <div class="alert-list">
          {#each alerts as alert}
            <button class="alert-row" class:stressed={alert.alert_triggered} onclick={() => analyzeCapture(alert.file)}>
              <div class="alert-top">
                <span class="alert-file">{alert.file}</span>
                <span class="alert-time">{alert.timestamp ? timeAgo(alert.timestamp) : ''}</span>
              </div>
              <div class="alert-tags">
                {#if alert.language}
                  <span class="tag lang">{alert.language}</span>
                {/if}
                <span class="tag stress" style="background: {stressColor(alert.max_stress)}20; color: {stressColor(alert.max_stress)}">
                  stress {(alert.max_stress * 100).toFixed(0)}%
                </span>
                {#if alert.alert_triggered}
                  <span class="tag danger">ALERT</span>
                {/if}
              </div>
              {#if alert.transcription_preview}
                <p class="alert-transcript">"{alert.transcription_preview}"</p>
              {/if}
            </button>
          {/each}
        </div>
      {/if}
    </section>

    <section class="section">
      <h2>Analysis Detail</h2>
      {#if analyzing}
        <div class="empty-state">Analyzing...</div>
      {:else if selectedCapture}
        <div class="analysis">
          <div class="analysis-file">{selectedCapture.file}</div>

          {#if selectedCapture.has_speech}
            <div class="analysis-block">
              <h3>Voice Activity</h3>
              <div class="analysis-stats">
                <span>Speech: {(selectedCapture.vad?.speech_ratio * 100).toFixed(0)}%</span>
                <span>Segments: {selectedCapture.vad?.num_segments}</span>
                <span>Duration: {selectedCapture.vad?.total_duration?.toFixed(1)}s</span>
              </div>
            </div>

            {#if selectedCapture.segments?.length}
              <div class="analysis-block">
                <h3>Stress Analysis</h3>
                {#each selectedCapture.segments as seg}
                  <div class="seg-row">
                    <span class="seg-time">{seg.time}</span>
                    <span class="seg-level" style="color: {stressColor(seg.confidence)}">
                      {seg.stress_level?.toUpperCase()} {(seg.confidence * 100).toFixed(0)}%
                    </span>
                    {#if seg.speaker?.gender}
                      <span class="seg-speaker">{seg.speaker.gender.gender} / {seg.speaker.age?.age_range || '?'}</span>
                    {/if}
                  </div>
                {/each}
              </div>
            {/if}

            {#if selectedCapture.transcription}
              <div class="analysis-block">
                <h3>Transcription</h3>
                <div class="lang-info">
                  {selectedCapture.transcription.original?.language_name}
                  ({(selectedCapture.transcription.original?.language_confidence * 100).toFixed(0)}%)
                  {#if selectedCapture.transcription.likely_maltese}
                    <span class="tag maltese">Likely Maltese</span>
                  {/if}
                </div>
                <blockquote>{selectedCapture.transcription.original?.text}</blockquote>
                {#if selectedCapture.transcription.translation}
                  <h3>English Translation</h3>
                  <blockquote class="translated">{selectedCapture.transcription.translation.translated_text}</blockquote>
                {/if}
              </div>
            {/if}
          {:else}
            <div class="empty-state">No speech detected in this capture.</div>
          {/if}
        </div>
      {:else}
        <div class="empty-state">Select a detection to view full analysis.</div>
      {/if}
    </section>
  </div>

  {/if}

  <footer>
    <span>Kenneth Sentinel -- Real-time RF Intelligence</span>
    <span>{new Date().toISOString().split('T')[0]}</span>
  </footer>
</main>

<style>
  main { max-width: 1100px; margin: 0 auto; padding: 1.25rem 1.5rem; }

  header {
    display: flex; justify-content: space-between; align-items: flex-start;
    margin-bottom: 1.25rem; padding-bottom: 0.75rem; border-bottom: 1px solid #1e293b;
  }
  h1 { font-size: 1.1rem; font-weight: 600; color: #f1f5f9; margin: 0; }
  .subtitle { font-size: 0.65rem; color: #475569; text-transform: uppercase; letter-spacing: 0.05em; }
  .header-right { display: flex; align-items: center; gap: 0.5rem; }
  .server-status {
    padding: 2px 8px; border-radius: 3px;
    font-family: 'Fira Code', monospace; font-size: 0.6rem; font-weight: 600; letter-spacing: 0.05em;
  }
  .server-status.ok { background: #22c55e18; color: #4ade80; }
  .server-status.err { background: #ef444418; color: #ef4444; }

  /* Status bar */
  .status-bar {
    display: flex; gap: 1rem; flex-wrap: wrap;
    padding: 0.65rem 1rem; background: #131c2e; border-radius: 4px;
    margin-bottom: 1.5rem; border: 1px solid #1e293b;
  }
  .status-item { display: flex; align-items: center; gap: 0.4rem; }
  .status-label { font-size: 0.7rem; font-weight: 600; color: #94a3b8; }
  .status-detail { font-size: 0.6rem; color: #475569; font-family: 'Fira Code', monospace; }
  .dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
  .dot.online { background: #4ade80; box-shadow: 0 0 6px #4ade8060; }
  .dot.offline { background: #ef4444; }

  /* Sections */
  .section { margin-bottom: 1.5rem; }
  .section h2 { font-size: 0.75rem; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.08em; margin: 0 0 0.5rem; }

  /* Bands grid */
  .bands-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 0.5rem; }
  .band-card { background: #131c2e; border-radius: 4px; padding: 0.75rem; border: 1px solid #1e293b; }
  .band-header { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem; }
  .band-name { font-size: 0.8rem; font-weight: 600; color: #f1f5f9; flex: 1; }
  .band-range { font-family: 'Fira Code', monospace; font-size: 0.6rem; color: #fbbf24; }
  .band-status { font-size: 0.55rem; text-transform: uppercase; padding: 1px 6px; border-radius: 2px; background: #1e293b; color: #475569; font-weight: 600; letter-spacing: 0.03em; }
  .band-status.active { background: #22c55e18; color: #4ade80; }
  .band-freqs { display: flex; flex-direction: column; gap: 3px; }
  .band-freq-row { display: flex; align-items: center; gap: 0.4rem; font-size: 0.75rem; padding: 2px 0; }
  .bf-dot { width: 5px; height: 5px; border-radius: 50%; flex-shrink: 0; }
  .bf-name { flex: 1; color: #94a3b8; }
  .bf-value { font-family: 'Fira Code', monospace; font-size: 0.65rem; color: #475569; }

  /* Content grid */
  .content-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }

  /* Alerts */
  .alert-list { display: flex; flex-direction: column; gap: 4px; }
  .alert-row {
    display: block; width: 100%; text-align: left;
    padding: 0.6rem 0.75rem; background: #131c2e; border-radius: 4px;
    border: 1px solid #1e293b; border-left: 3px solid #1e293b;
    cursor: pointer; transition: all 0.15s;
    font-family: inherit; color: inherit;
  }
  .alert-row:hover { background: #1e293b; }
  .alert-row.stressed { border-left-color: #ef4444; }
  .alert-top { display: flex; justify-content: space-between; margin-bottom: 0.3rem; }
  .alert-file { font-family: 'Fira Code', monospace; font-size: 0.7rem; font-weight: 600; color: #f1f5f9; }
  .alert-time { font-size: 0.6rem; color: #334155; }
  .alert-tags { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 0.25rem; }
  .tag { padding: 1px 5px; border-radius: 2px; font-size: 0.55rem; font-weight: 600; font-family: 'Fira Code', monospace; }
  .tag.lang { background: #06b6d418; color: #22d3ee; }
  .tag.danger { background: #ef444418; color: #ef4444; }
  .tag.maltese { background: #f59e0b18; color: #fbbf24; }
  .alert-transcript { font-size: 0.7rem; color: #64748b; font-style: italic; margin: 0.25rem 0 0; }

  /* Analysis */
  .analysis-file { font-family: 'Fira Code', monospace; font-size: 0.8rem; color: #fbbf24; margin-bottom: 0.75rem; font-weight: 600; }
  .analysis-block { margin-bottom: 1rem; }
  .analysis-block h3 { font-size: 0.65rem; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin: 0 0 0.35rem; }
  .analysis-stats { display: flex; gap: 1rem; font-size: 0.75rem; font-family: 'Fira Code', monospace; color: #4ade80; }
  .seg-row { display: flex; gap: 0.75rem; padding: 3px 0; font-size: 0.7rem; border-bottom: 1px solid #1e293b08; }
  .seg-time { font-family: 'Fira Code', monospace; min-width: 80px; color: #475569; }
  .seg-level { font-weight: 600; min-width: 100px; }
  .seg-speaker { color: #475569; }
  .lang-info { font-size: 0.75rem; margin-bottom: 0.35rem; color: #94a3b8; }
  blockquote {
    margin: 0.35rem 0; padding: 0.5rem 0.75rem;
    background: #0f172a; border-radius: 3px; border-left: 2px solid #1e293b;
    font-size: 0.75rem; line-height: 1.5; color: #cbd5e1;
  }
  blockquote.translated { color: #94a3b8; }

  /* Empty */
  .empty-state { padding: 1.5rem; background: #131c2e; border-radius: 4px; font-size: 0.75rem; color: #334155; text-align: center; }
  .error-state { text-align: center; padding: 2rem; }
  .hint { color: #334155; font-size: 0.7rem; }
  code { background: #131c2e; padding: 2px 6px; border-radius: 3px; font-size: 0.7rem; font-family: 'Fira Code', monospace; color: #94a3b8; }

  footer {
    display: flex; justify-content: space-between;
    padding-top: 0.75rem; border-top: 1px solid #1e293b;
    font-size: 0.6rem; color: #334155;
  }

  .loading { text-align: center; padding: 3rem; color: #475569; }

  @media (max-width: 900px) {
    .content-grid { grid-template-columns: 1fr; }
    .bands-grid { grid-template-columns: 1fr; }
  }
</style>
