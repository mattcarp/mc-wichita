/** Shared source / freshness labels for ships, planes, and satellites. */

export function provenanceLine(entity) {
  if (!entity) return "";
  const src = entity.source_label || "—";
  const fresh = entity.freshness_label || "—";
  return `${src} · ${fresh}`;
}

export function provenanceBadge(entity, { showDefault = false } = {}) {
  if (!entity) return "";
  const tier = entity.freshness || "earlier";
  if (!showDefault && entity.data_source === "our_antenna" && tier !== "earlier") {
    return "";
  }
  const text = provenanceLine(entity);
  return `<span class="prov-badge prov-${tier}">${text}</span>`;
}

export function freshnessClass(tier) {
  if (tier === "now") return "fresh-now";
  if (tier === "recent") return "fresh-recent";
  return "fresh-earlier";
}

export function heardAntennaBadge(badge) {
  if (!badge) return "";
  const bands = (badge.bands || []).join(" · ") || "AIS / ADS-B";
  const count = badge.count ?? 0;
  const active = badge.active ? "heard-60-active" : "heard-60-idle";
  return `<span class="heard-60-badge ${active}" role="status">${badge.label || "Heard by my antenna, last 60 s"}: <strong>${count}</strong> <span class="muted">${bands}</span></span>`;
}

export function feedHealthChip(health) {
  if (!health) return "";
  const state = health.state || "unknown";
  return `<span class="feed-health feed-health-${state}" title="${health.coverage_label || health.state_label || ""}">${health.receiver || "Receiver"} · ${health.state_label || state}${health.coverage === "quiet" ? " · quiet" : ""}</span>`;
}
