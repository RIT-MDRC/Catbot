import { PanelExtensionContext } from "@foxglove/extension";

const names = ["fla", "flf", "flk", "fra", "frf", "frk", "bla", "blf", "blk", "bra", "brf", "brk"];
const topic = "/body/state/position";
const statusTopic = "/rpi/supervisor/status";
type Sample = { actuator_name?: unknown; valid?: unknown; position_degrees?: unknown };

/** Visualizes logical degrees against the repository's default hardware limits. */
export function initPositions(context: PanelExtensionContext): () => void {
  const root = context.panelElement;
  root.style.cssText = "padding:10px;overflow:auto;font:12px system-ui,sans-serif;color:inherit";
  const note = document.createElement("div");
  note.textContent = "Measured logical angles · normalized to default limits (hips ±40°, knees ±55°) · not policy actions";
  note.style.cssText = "font-size:11px;opacity:.8;margin-bottom:8px";
  root.append(note);
  const lock = document.createElement("div"); lock.textContent = "Supervisor status unavailable · controls read-only"; lock.style.cssText = "color:#e8b74b;font-size:11px;margin-bottom:6px"; root.append(lock);
  const rows = new Map<string, { value: HTMLElement; bar: HTMLInputElement }>();
  for (const name of names) {
    const row = document.createElement("div"); row.style.cssText = "display:flex;align-items:center;gap:7px;margin:4px 0";
    const label = document.createElement("strong"); label.textContent = name.toUpperCase(); label.style.width = "32px";
    const bar = document.createElement("input"); bar.type = "range"; bar.min = "-1"; bar.max = "1"; bar.step = "0.01"; bar.value = "0"; bar.disabled = true; bar.style.cssText = "flex:1;min-width:30px;height:8px;visibility:hidden"; bar.setAttribute("aria-label", `${name} normalized position`);
    const value = document.createElement("span"); value.textContent = "unavailable"; value.style.cssText = "min-width:115px;text-align:right";
    row.append(label, bar, value); root.append(row); rows.set(name, { value, bar });
  }
  let lastAt = 0;
  let lastStatusAt = 0;
  const clear = (message: string) => { for (const row of rows.values()) { row.value.textContent = message; row.bar.style.visibility = "hidden"; } };
  context.subscribe([{ topic }, { topic: statusTopic }]); context.watch("currentFrame");
  context.onRender = (state, done) => {
    for (const event of state.currentFrame ?? []) {
      if (event.topic === statusTopic) {
        const status = event.message as { mode?: unknown };
        lastStatusAt = Date.now();
        lock.textContent = status.mode === "running" ? "Locked · policy motion active" : "Controls read-only · manual commands not available";
        continue;
      }
      if (event.topic !== topic) continue;
      const data = event.message as { actuators?: Sample[] };
      if (!Array.isArray(data?.actuators)) { clear("invalid message"); lastAt = Date.now(); continue; }
      clear("unavailable"); lastAt = Date.now();
      for (const sample of data.actuators) {
        if (typeof sample.actuator_name !== "string") continue;
        const row = rows.get(sample.actuator_name); if (!row) continue;
        const degrees = sample.position_degrees;
        if (sample.valid !== true || typeof degrees !== "number" || !Number.isFinite(degrees)) continue;
        const limit = sample.actuator_name.endsWith("k") ? 55 : 40;
        const normalized = degrees / limit;
        row.bar.value = String(Math.max(-1, Math.min(1, normalized)));
        row.bar.style.visibility = "visible";
        row.value.textContent = `${normalized.toFixed(2)}  (${degrees.toFixed(1)}°)${Math.abs(normalized) > 1 ? " !" : ""}`;
      }
    }
    done();
  };
  const interval = setInterval(() => { if (lastAt && Date.now() - lastAt > 2000) clear("stale"); if (lastStatusAt && Date.now() - lastStatusAt > 2000) lock.textContent = "Supervisor status stale · controls read-only"; }, 500);
  return () => { clearInterval(interval); context.unsubscribeAll(); root.replaceChildren(); };
}
