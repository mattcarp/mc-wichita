const MALTA_TZ = "Europe/Malta";

export function formatMalta(isoOrSec) {
  let d;
  if (typeof isoOrSec === "number") {
    d = new Date(isoOrSec * 1000);
  } else if (isoOrSec) {
    d = new Date(isoOrSec);
  } else {
    return "—";
  }
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: MALTA_TZ,
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(d);
}

export function formatMaltaTimeShort(isoOrSec) {
  let d;
  if (typeof isoOrSec === "number") {
    d = new Date(isoOrSec * 1000);
  } else if (isoOrSec) {
    d = new Date(isoOrSec);
  } else {
    return "—";
  }
  const now = new Date();
  const sameDay =
    new Intl.DateTimeFormat("en-GB", { timeZone: MALTA_TZ, dateStyle: "short" }).format(d) ===
    new Intl.DateTimeFormat("en-GB", { timeZone: MALTA_TZ, dateStyle: "short" }).format(now);
  if (sameDay) {
    return new Intl.DateTimeFormat("en-GB", {
      timeZone: MALTA_TZ,
      hour: "2-digit",
      minute: "2-digit",
    }).format(d);
  }
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: MALTA_TZ,
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
}
