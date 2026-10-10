<script lang="ts">
  import { page } from '$app/state';

  let { children } = $props();
</script>

<svelte:head>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Fira+Code:wght@400;600;700&display=swap" rel="stylesheet">
</svelte:head>

<nav>
  <a href="/" class="nav-brand">Kenneth</a>
  <div class="nav-links">
    <a href="/" class:active={page.url.pathname === '/'}>Dashboard</a>
    <a href="/sentinel" class:active={page.url.pathname === '/sentinel'}>Sentinel</a>
  </div>
</nav>

{@render children()}

<style>
  :global(*) { box-sizing: border-box; }
  :global(body) {
    margin: 0;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #0a0e1a;
    color: #cbd5e1;
  }

  nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.5rem 1.5rem;
    background: #080c17;
    border-bottom: 1px solid #1e293b;
    max-width: 1100px;
    margin: 0 auto;
  }

  .nav-brand {
    font-family: 'Inter', sans-serif;
    font-size: 0.7rem;
    font-weight: 700;
    color: #6366f1;
    text-decoration: none;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }

  .nav-links { display: flex; gap: 0.5rem; }

  .nav-links a {
    font-size: 0.65rem;
    color: #475569;
    text-decoration: none;
    padding: 3px 10px;
    border-radius: 3px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    transition: all 0.15s;
  }

  .nav-links a:hover { color: #94a3b8; background: #131c2e; }
  .nav-links a.active { color: #818cf8; background: #6366f118; }
</style>
