import { ExtensionContext, PanelExtensionContext } from "@foxglove/extension";
import { initPositions } from "./positions";

const controls = [
  { label: "Global gain", name: "/foundation_node.policy_gain_scale", min: 0.1, max: 1, step: 0.01, speed: false },
  ...["abduction", "flexion", "knee"].map((group) => ({ label: `${group[0]!.toUpperCase()}${group.slice(1)} speed`, name: `/foundation_node.${group}.speed_motor_turns_s`, min: 5, max: 20, step: 0.1, speed: true })),
];

function initPanel(context: PanelExtensionContext): () => void {
  const root = context.panelElement;
  root.style.cssText = "padding:12px;overflow:auto;font:13px system-ui,sans-serif;color:inherit";
  const cleanup: Array<() => void> = [];
  const updates: Array<(parameters: ReadonlyMap<string, unknown> | undefined) => void> = [];
  context.watch("parameters");
  for (const control of controls) {
    const row = document.createElement("section");
    row.style.cssText = "padding:8px 0;border-bottom:1px solid #7776";
    const header = document.createElement("div"); header.style.cssText = "display:flex;gap:8px;align-items:baseline;justify-content:space-between";
    const label = document.createElement("strong"); label.textContent = control.label;
    const reported = document.createElement("span"); reported.textContent = "Unavailable"; reported.title = "Last reported ROS parameter, not motor-controller readback";
    header.append(label, reported);
    const inputs = document.createElement("div"); inputs.style.cssText = "display:flex;gap:8px;align-items:center;margin-top:6px";
    const slider = document.createElement("input"); slider.type = "range"; slider.min = String(control.min); slider.max = String(control.max); slider.step = String(control.step); slider.style.cssText = "flex:1;min-width:40px"; slider.setAttribute("aria-label", control.label);
    const number = document.createElement("input"); number.type = "number"; number.min = slider.min; number.max = slider.max; number.step = "any"; number.style.cssText = "width:65px;color:inherit;background:transparent"; number.setAttribute("aria-label", `${control.label} value`);
    const unit = document.createElement("span"); unit.textContent = control.speed ? "turns/s" : "×";
    inputs.append(slider, number, unit);
    const status = document.createElement("div"); status.style.cssText = "color:#e8b74b;min-height:1em;font-size:12px";
    const dismiss = document.createElement("button"); dismiss.textContent = "Dismiss"; dismiss.hidden = true;
    row.append(header, inputs, status, dismiss); root.append(row);
    let current: number | undefined;
    let pending: number | undefined;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let editing = false;
    let warning = "";
    const mixed = () => control.speed && current === -1;
    const setStatus = () => {
      status.textContent = warning || (pending != undefined ? "Requested — awaiting ROS report" : mixed() ? "Different configured values" : current != undefined && (current < control.min || current > control.max) ? "Reported value outside slider range" : "");
      dismiss.hidden = !warning;
    };
    const restore = () => {
      if (current == undefined) { number.value = ""; return; }
      const value = mixed() ? control.min : current;
      slider.value = String(Math.max(control.min, Math.min(control.max, value)));
      number.value = mixed() ? String(control.min) : String(value);
    };
    const send = (value: number) => {
      if (current == undefined) return;
      if (!Number.isFinite(value) || value < control.min || value > control.max) { warning = `Enter a value from ${control.min} to ${control.max}`; setStatus(); return; }
      if (timer != undefined) clearTimeout(timer);
      warning = ""; editing = false; pending = value;
      slider.value = String(value); number.value = String(value); setStatus();
      try { context.setParameter(control.name, value); }
      catch { pending = undefined; warning = "Request could not be sent"; restore(); setStatus(); return; }
      timer = setTimeout(() => { timer = undefined; pending = undefined; warning = "Request didn't go through (no matching ROS report)"; if (!editing) restore(); setStatus(); }, 3000);
    };
    slider.addEventListener("input", () => { editing = true; warning = ""; number.value = slider.value; setStatus(); });
    slider.addEventListener("change", () => send(Number(slider.value)));
    number.addEventListener("input", () => { editing = true; warning = ""; setStatus(); });
    number.addEventListener("change", () => { if (number.value.trim() === "") { warning = "Enter a value"; setStatus(); return; } send(Number(number.value)); });
    number.addEventListener("keydown", (event) => { if (event.key === "Enter") { event.preventDefault(); number.blur(); } });
    dismiss.addEventListener("click", () => { warning = ""; setStatus(); });
    const update = (parameters: ReadonlyMap<string, unknown> | undefined) => {
      const value = parameters?.get(control.name);
      current = typeof value === "number" && Number.isFinite(value) ? value : undefined;
      slider.disabled = current == undefined; number.disabled = current == undefined;
      reported.textContent = current == undefined ? "Unavailable" : mixed() ? "Mixed" : `${current} (ROS)`;
      if (pending != undefined && current != undefined && Math.abs(current - pending) < 1e-8) { if (timer != undefined) clearTimeout(timer); timer = undefined; pending = undefined; }
      if (!editing && pending == undefined) restore();
      setStatus();
    };
    cleanup.push(() => { if (timer != undefined) clearTimeout(timer); });
    updates.push(update);
  }
  context.onRender = (state, done) => { for (const update of updates) update(state.parameters); done(); };
  return () => { cleanup.forEach((fn) => fn()); root.replaceChildren(); };
}
export function activate(context: ExtensionContext): void { context.registerPanel({ name: "actuator-tuning", initPanel }); context.registerPanel({ name: "actuator-positions", initPanel: initPositions }); }
