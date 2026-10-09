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
