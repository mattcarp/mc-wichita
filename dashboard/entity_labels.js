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
