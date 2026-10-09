/** Shared source / freshness labels for ships, planes, and satellites. */

export function provenanceLine(entity) {
  if (!entity) return "";
  const src = entity.source_label || "—";
  const fresh = entity.freshness_label || "—";
  return `${src} · ${fresh}`;
}

export function provenanceBadge(entity) {
  const tier = entity?.freshness || "stale";
  const text = provenanceLine(entity);
  return `<span class="prov-badge prov-${tier}">${text}</span>`;
}
