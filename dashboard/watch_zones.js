const V = "?v=20261010-gev1";

let drawPoints = [];
let drawing = false;

export async function loadWatchZones() {
  const res = await fetch("/api/watch-zones");
  if (!res.ok) return [];
  const data = await res.json();
  return data.zones || [];
}

export async function saveWatchZone(zone) {
  const res = await fetch("/api/watch-zones", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(zone),
  });
  return res.ok ? res.json() : null;
}

export function initWatchZones(map, ui) {
  const btn = ui?.drawBtn;
  const status = ui?.status;
  if (!map || !btn) return;

  const refresh = async () => {
    const zones = await loadWatchZones();
    map.setWatchZones(zones);
  };

  btn.addEventListener("click", () => {
    drawing = !drawing;
    drawPoints = [];
    btn.setAttribute("aria-pressed", drawing ? "true" : "false");
    if (status) status.textContent = drawing ? "Tap map corners to draw a watch zone (double-click to finish)." : "";
    map.setWatchDrawMode(drawing, {
      onPoint: (lon, lat) => {
        drawPoints.push([lon, lat]);
        map.setWatchDraft(drawPoints);
      },
      onFinish: async () => {
        if (drawPoints.length < 3) return;
        const id = `zone-${Date.now()}`;
        const name = ui?.nameInput?.value?.trim() || "Watch zone";
        await saveWatchZone({ id, name, polygon: [...drawPoints, drawPoints[0]] });
        drawing = false;
        btn.setAttribute("aria-pressed", "false");
        drawPoints = [];
        map.setWatchDraft([]);
        map.setWatchDrawMode(false, null);
        if (status) status.textContent = `Saved “${name}”. Alerts go to the Heard log.`;
        await refresh();
      },
    });
  });

  refresh();
}
