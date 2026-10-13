// One plural helper for every count on the dashboard. English rules via Intl.PluralRules:
// only 1 is singular; 0 and everything else take the plural ("0 ships", "1 ship", "2 ships").
const RULES = new Intl.PluralRules("en");
const IRREGULAR = { aircraft: "aircraft", msg: "msgs", h: "h", min: "min", kn: "kn", kt: "kt", ft: "ft", passes: "passes" };

export function pluralWord(n, one, many) {
  if (RULES.select(Number(n)) === "one") return one;
  return many ?? IRREGULAR[one] ?? `${one}s`;
}

export function plural(n, one, many) {
  return `${n} ${pluralWord(n, one, many)}`;
}
