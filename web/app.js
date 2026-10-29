// GridMedic outage-operations console. Layout follows utility OMS practice: a network viewer, a
// sortable work agenda of outage events with an event-details pane, and a dock with the event log,
// trouble calls, outbound messages and crews. Everything is driven by the server's WebSocket stream.

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmt = (n) => Number(n || 0).toLocaleString();

const MODEL_CLASS = (m) => {
  if (!m) return "code";
  if (m.startsWith("mock")) return "mock";
  if (m.includes("SAM")) return "sam";
  if (m.includes("Voice")) return "voice";
  if (m.includes("Spark") || m.includes("Glimmer")) return "spark";
  if (m === "SCADA" || m === "Smart meters") return "scada";
  if (m === "Agent" || m === "Operator") return "agent";
  return "code";
};
const badge = (m) => `<span class="badge ${MODEL_CLASS(m)}">${esc(m)}</span>`;
const CHANNEL = { call: "Call", whatsapp: "Chat", sms: "SMS", crew: "Crew", web: "Web", app: "App" };
// OMS-style event status codes
const STATUS = { located: "PRED", dispatched: "DISP", "on site": "ONS", restored: "REST" };
const STATUS_TEXT = { PRED: "Predicted, crew not yet assigned", DISP: "Crew dispatched", ONS: "Crew on site", REST: "Restored", SUSP: "Suspected" };
let START_MIN = 15 * 60;
const clockOf = (t) => { const m = Math.floor(START_MIN + t / 60); return `${String(Math.floor(m / 60) % 24).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`; };

const map = L.map("map", { zoomControl: true, preferCanvas: true });
// OpenStreetMap tiles, desaturated and darkened in CSS (.leaflet-tile-pane) so the network reads first.
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "&copy; OpenStreetMap contributors", maxZoom: 19 }).addTo(map);

const layers = {
  lines: L.layerGroup().addTo(map), xfmr: L.layerGroup().addTo(map), devices: L.layerGroup().addTo(map),
  messages: L.layerGroup().addTo(map), hazards: L.layerGroup().addTo(map), probes: L.layerGroup().addTo(map),
  dispatch: L.layerGroup().addTo(map), crews: L.layerGroup().addTo(map), events: L.layerGroup().addTo(map),
};
const xfmrMarkers = {}, xfmrSection = {}, devKind = {}, sectionLines = {}, crewMarkers = {};
let tieLine = null, grid = null, state = null, selected = null;
let sortKey = "priority", sortDir = -1;
const history = [];

// ---- network viewer -------------------------------------------------------------------

async function loadGrid() {
  grid = await (await fetch("/api/grid")).json();
  START_MIN = grid.start_hour * 60;
  const served = Object.values(grid.customers).reduce((a, b) => a + b, 0);
  $("#scenario-sub").textContent = `${grid.country} · ${grid.network === "osm" ? "feeder built on real OpenStreetMap roads" : "IEEE 34-bus test feeder"} · ${fmt(served)} customers · fictional customer data`;
  const list = await (await fetch("/api/scenarios")).json();
  $("#scenario").innerHTML = list.scenarios.map((s) => `<option value="${s.id}" ${s.id === list.current ? "selected" : ""}>${esc(s.title)}</option>`).join("");
  const bounds = [];
  for (const f of grid.geojson.features) {
    const p = f.properties;
    const [lon, lat] = f.geometry.type === "Point" ? f.geometry.coordinates : [0, 0];
    if (p.kind === "section" || p.kind === "tie_line") {
      const ll = f.geometry.coordinates.map(([x, y]) => [y, x]);
      bounds.push(...ll);
      const line = L.polyline(ll, p.kind === "tie_line" ? { color: "#6b7480", weight: 2, dashArray: "5 6" } : { color: "#5b86ad", weight: 2.5 })
        .bindTooltip(p.kind === "tie_line" ? "Tie to Feeder 2 (through TS-1)" : `${esc(p.street)} · section ${p.id}`, { className: "gm", sticky: true })
        .addTo(layers.lines);
      if (p.kind === "tie_line") tieLine = line; else sectionLines[p.id] = line;
    } else if (p.kind === "transformer") {
      xfmrSection[p.id] = p.section;
      xfmrMarkers[p.id] = L.circleMarker([lat, lon], { radius: 2.5, color: "#5b86ad", weight: 1, fillOpacity: 1 })
        .bindTooltip(`${p.id} · ${grid.customers[p.id] || 0} customers`, { className: "gm" }).addTo(layers.xfmr);
    } else if (p.kind === "feeder2") {
      L.marker([lat, lon], { icon: L.divIcon({ className: "", html: `<div class="dev breaker"></div>`, iconSize: [10, 10] }) })
        .bindTooltip(esc(p.label), { className: "gm" }).addTo(layers.devices);
    } else {
      const sw = p.kind === "switch" || p.kind === "tie";
      devKind[p.id] = p.kind;
      L.marker([lat, lon], { icon: L.divIcon({ className: "", html: `<div id="dev-${p.id}" class="${sw ? "sw" : "dev " + p.kind}${p.kind === "tie" ? " open" : ""}"></div>`, iconSize: [11, 11] }) })
        .bindTooltip(`${esc(p.label)} (${p.id})${p.scada ? " · remote" : ""}`, { className: "gm" }).addTo(layers.devices);
    }
  }
  for (const lm of grid.landmarks.filter((l) => l.critical)) {
    L.circleMarker([lm.lat, lm.lon], { radius: 4, color: "#e5484d", weight: 1.5, fillOpacity: 0 })
      .bindTooltip(`${esc(lm.name)} · critical: ${esc(lm.critical)}`, { className: "gm" }).addTo(layers.lines);
  }
  L.marker(grid.substation, { icon: L.divIcon({ className: "", html: `<div class="dev breaker" style="width:14px;height:14px"></div>`, iconSize: [14, 14] }) })
    .bindTooltip(esc(grid.substation_label), { className: "gm" }).addTo(layers.devices);
  map.fitBounds(bounds, { padding: [20, 20] });
  addLegend();
}

function addLegend() {
  const legend = L.control({ position: "bottomleft" });
  legend.onAdd = () => {
    const d = L.DomUtil.create("div", "legend");
    d.innerHTML = `
      <div class="row"><i class="ln" style="border-color:#5b86ad"></i>Energised</div>
      <div class="row"><i class="ln" style="border-color:#6b7480;border-top-style:dashed"></i>De-energised (believed)</div>
      <div class="row"><i class="sq" style="background:var(--st-pred)"></i>Predicted · <i class="sq" style="background:var(--st-disp)"></i>Dispatched · <i class="sq" style="background:var(--st-ons)"></i>On site</div>
      <div class="row"><i class="sq" style="background:var(--alarm)"></i>Public hazard · <span style="color:#e5484d">○</span> Critical customer</div>
      <div class="row">● recloser · ■ breaker · ▣ switch closed / ▢ open</div>`;
    return d;
  };
  legend.addTo(map);
}

function eventStatus(i) { return STATUS[i.status] || "PRED"; }

function renderNetwork(s) {
  const dead = new Set(s.dead_transformers);
  const deadSections = new Set();
  for (const [id, m] of Object.entries(xfmrMarkers)) {
    const out = dead.has(id);
    if (out) deadSections.add(xfmrSection[id]);
    m.setStyle(out ? { color: "#e5484d", fillColor: "#e5484d", radius: 3 } : { color: "#5b86ad", fillColor: "#5b86ad", radius: 2.5 });
  }
  for (const [id, line] of Object.entries(sectionLines)) {
    line.setStyle(deadSections.has(id) ? { color: "#6b7480", weight: 2.5, dashArray: "4 5" } : { color: "#5b86ad", weight: 2.5, dashArray: null });
  }
  const open = new Set(s.open_devices);
  for (const id of Object.keys(devKind)) {
    const el = document.getElementById(`dev-${id}`);
    if (el) el.classList.toggle("open", open.has(id));
  }
  if (tieLine) tieLine.setStyle(open.has("TS-1") ? { color: "#6b7480", dashArray: "5 6", weight: 2 } : { color: "#3fb47c", dashArray: null, weight: 3 });

  layers.events.clearLayers();
  const liveWire = (i) => i.kind === "live_wire" && s.hazards.some((h) => h.kind === "live_wire" && !h.safe);
  for (const i of s.incidents) {
    if (i.status === "restored") continue;
    const st = eventStatus(i);
    const html = `<div class="ev-marker"><div class="ev-sym ${st} ${liveWire(i) ? "hazard" : ""} ${selected === i.id ? "sel" : ""}"></div>
      <span class="ev-label">${esc(i.id)} ${esc(i.title)}${i.mind_changed ? " ↺" : ""}</span></div>`;
    L.marker([i.lat, i.lon], { icon: L.divIcon({ className: "", html, iconSize: [180, 18], iconAnchor: [9, 9] }), zIndexOffset: 1000 })
      .on("click", () => select(i.id)).addTo(layers.events);
  }
  for (const x of s.suspects) {
    L.marker([x.lat, x.lon], { icon: L.divIcon({ className: "", html: `<div class="ev-marker"><div class="ev-sym SUSP"></div><span class="ev-label">? ${Math.round(x.confidence * 100)}%</span></div>`, iconSize: [90, 18], iconAnchor: [9, 9] }) })
      .bindTooltip(`Suspected: ${esc(x.label)}`, { className: "gm" }).addTo(layers.events);
  }
  layers.hazards.clearLayers();
  for (const h of s.hazards.filter((h) => !h.safe)) {
    L.circleMarker([h.lat, h.lon], { radius: 9, color: "#e5484d", weight: 2, fillOpacity: 0.15 })
      .bindTooltip(`${h.id}: ${h.kind.replace("_", " ")} · ${h.evidence.length} reports`, { className: "gm" }).addTo(layers.hazards);
  }
  layers.probes.clearLayers();
  for (const p of s.probes) {
    const on = p.answer && p.answer.includes("ON");
    L.marker([p.lat, p.lon], { icon: L.divIcon({ className: "", html: `<div class="probe ${on ? "on" : ""}">${on ? "✓" : "?"}</div>`, iconSize: [16, 16] }) })
      .bindTooltip(`${p.id} to ${esc(p.street)} ${p.house_no}: ${p.answer || "awaiting reply"}`, { className: "gm" }).addTo(layers.probes);
  }
  renderCrewMarkers(s.crews);
}

function renderCrewMarkers(crews) {
  layers.dispatch.clearLayers();
  for (const c of crews) {
    const short = c.id.replace("CREW-", "");
    const html = `<div class="crew ${c.status}">${esc(short)}</div>`;
    const icon = L.divIcon({ className: "", html, iconSize: [26, 14], iconAnchor: [13, 7] });
    if (!crewMarkers[c.id]) crewMarkers[c.id] = L.marker([c.lat, c.lon], { icon, zIndexOffset: 1500 }).addTo(layers.crews);
    crewMarkers[c.id].setLatLng([c.lat, c.lon]).setIcon(icon)
      .bindTooltip(`${esc(c.name)}: ${c.status}${c.task ? " · " + esc(c.task) : ""}${c.incident ? " (" + c.incident + ")" : ""}`, { className: "gm" });
    const inc = state && state.incidents.find((i) => i.id === c.incident);
    if (inc && c.status === "enroute") L.polyline([[c.lat, c.lon], [inc.lat, inc.lon]], { color: "#4aa3df", weight: 1.5, dashArray: "3 5" }).addTo(layers.dispatch);
  }
}

// ---- KPIs ----------------------------------------------------------------------------------

function renderKpis(s) {
  const c = s.counts;
  const served = c.served || 1;
  $("#k-out").textContent = fmt(c.customers_out);
  $("#k-out-sub").textContent = `${(100 * c.customers_out / served).toFixed(1)}% of ${fmt(served)} served`;
  history.push([s.elapsed, c.customers_out]);
  if (history.length > 400) history.splice(0, history.length - 400);
  drawSpark();
  $("#k-events").textContent = c.incidents_open;
  $("#k-events-sub").textContent = `${c.incidents_restored} restored · ${s.suspects.length} suspected`;
  $("#k-calls").textContent = fmt(c.calls);
  $("#k-calls-sub").textContent = `${fmt(c.duplicates)} dup · ${c.junk} junk · ${fmt(c.bd_sms)} SMS codes`;
  $("#k-crit").textContent = c.critical_out;
  $("#k-crit").className = `v ${c.critical_out ? "bad" : ""}`;
  $("#k-haz").textContent = c.hazards_open;
  $("#k-haz").className = `v ${c.hazards_open ? "bad" : ""}`;
  $("#k-haz-sub").textContent = s.hazards.some((h) => h.kind === "live_wire") && s.plan && s.plan.plan
    ? `live wire safe in ${s.plan.hazard_wait_min} min (vs ${s.baseline.hazard_wait_min})` : "none reported";
  const cr = c.crews || {};
  $("#k-crews").textContent = `${cr.onsite || 0} · ${cr.enroute || 0} · ${cr.idle || 0}`;
  $("#k-cmi").textContent = fmt(c.cmi);
  if (s.plan && s.plan.plan && s.plan.plan.length) {
    const saved = Math.round((s.baseline.customer_minutes - s.plan.customer_minutes) / 60);
    $("#k-cmi-sub").textContent = `plan saves ${fmt(saved)} customer-h vs first-call`;
  }
  $("#k-langs").textContent = Object.keys(c.languages).map((l) => l.toUpperCase()).join(" ") || "–";
  $("#k-msg-sub").textContent = `${fmt(c.messages)} messages · ${c.notified} customers notified`;
  $("#k-models").innerHTML = Object.entries(c.model_calls).map(([m, n]) => `${badge(m)}<span class="badge count">${fmt(n)}</span>`).join("") || `<span class="s">no model calls yet</span>`;
  const found = s.truth.filter((t) => t.found).length;
  $("#k-truth").textContent = `scenario check: ${found}/${s.truth.length} real faults diagnosed`;
  // status chips
  const net = $("#btn-net");
  net.textContent = s.offline ? "Network down · Glimmer" : "Network online";
  net.className = `chip ${s.offline ? "bad" : "ok"}`;
  net.dataset.offline = s.offline ? "1" : "";
  $("#offline-banner").hidden = !s.offline;
  $("#queued").textContent = c.queued || 0;
  const ami = $("#ami-chip");
  ami.hidden = c.ami === null || c.ami === undefined;
  if (!ami.hidden) {
    ami.textContent = c.ami ? `Meters online · ${fmt(c.meter_msgs)} last gasps` : `Meter network down · ${fmt(c.meter_msgs)} received`;
    ami.className = `chip ${c.ami ? "live" : "bad"}`;
  }
  $("#mode").textContent = s.mode === "live" ? "LIVE · Meta Model API" : "MOCK · cached / ground truth";
  $("#mode").className = `chip ${s.mode === "live" ? "live" : ""}`;
}

function drawSpark() {
  if (history.length < 2) return;
  const t0 = history[0][0], t1 = history[history.length - 1][0] || 1;
  const max = Math.max(...history.map((h) => h[1]), 1);
  const pts = history.map(([t, v]) => `${(120 * (t - t0) / Math.max(t1 - t0, 1)).toFixed(1)},${(30 - 28 * v / max).toFixed(1)}`);
  $("#spark").innerHTML = `<path class="area" d="M0,32 L${pts.join(" L")} L120,32Z"/><path class="line" d="M${pts.join(" L")}"/>`;
}

// ---- work agenda -------------------------------------------------------------------------

function agendaRows(s) {
  return s.incidents.map((i) => {
    const crew = i.steps.filter((st) => st.crew && st.status !== "done").map((st) => (s.crews.find((c) => c.id === st.crew) || {}).id || st.crew).map((x) => x.replace("CREW-", "")).join(",");
    return { ...i, st: eventStatus(i), calls: i.reports.length, crit: i.critical.length, crew };
  });
}

function renderAgenda(s) {
  const rows = agendaRows(s).sort((a, b) => {
    if ((a.status === "restored") !== (b.status === "restored")) return a.status === "restored" ? 1 : -1;
    const va = a[sortKey], vb = b[sortKey];
    return (va > vb ? 1 : va < vb ? -1 : 0) * sortDir;
  });
  const suspects = s.suspects.map((x) => `<tr title="${esc(x.reasons.join("; "))}"><td class="mono">–</td><td><span class="st SUSP">SUSP</span></td><td>Suspected</td>
    <td class="trunc">${esc(x.label)}</td><td class="num">–</td><td class="num">–</td><td class="num">–</td><td></td><td></td><td class="num">${Math.round(x.confidence * 100)}%</td><td></td></tr>`);
  const html = rows.map((i) => `<tr data-id="${i.id}" class="${i.status === "restored" ? "restored" : ""} ${selected === i.id ? "sel" : ""} ${i.kind === "live_wire" && i.status !== "restored" ? "hazard" : ""}">
      <td class="mono">${esc(i.id)}</td><td><span class="st ${i.st}" title="${STATUS_TEXT[i.st]}">${i.st}</span></td>
      <td>${esc(i.title)}${i.mind_changed ? " ↺" : ""}</td><td class="trunc" title="${esc(i.label)}">${esc(i.label)}</td>
      <td class="num">${fmt(i.customers_out)}</td><td class="num">${i.calls}</td><td class="num">${i.crit || ""}</td>
      <td class="mono">${esc(i.crew)}</td><td class="mono">${i.status === "restored" ? "done" : i.eta ? clockOf(i.eta) : "–"}</td>
      <td class="num">${Math.round(i.confidence * 100)}%</td><td class="num">${Math.round(i.priority)}</td></tr>`).join("") + suspects.join("");
  const tb = $("#agenda tbody");
  if (tb.dataset.html !== html) { tb.dataset.html = html; tb.innerHTML = html; }
  $("#agenda-sub").textContent = `${s.counts.incidents_open} open · ${s.counts.incidents_restored} restored`;
  document.querySelectorAll("#agenda th").forEach((th) => th.classList.toggle("sorted", th.dataset.sort === sortKey));
}

$("#agenda tbody").addEventListener("click", (ev) => {
  const tr = ev.target.closest("tr[data-id]");
  if (tr) select(tr.dataset.id, true);
});
document.querySelectorAll("#agenda th[data-sort]").forEach((th) => th.addEventListener("click", () => {
  sortDir = sortKey === th.dataset.sort ? -sortDir : (["id", "title", "label", "crew", "status"].includes(th.dataset.sort) ? 1 : -1);
  sortKey = th.dataset.sort;
  if (state) renderAgenda(state);
}));

function select(id, fly) {
  selected = id;
  if (!state) return;
  renderAgenda(state);
  renderDetails(state);
  renderNetwork(state);
  const i = state.incidents.find((x) => x.id === id);
  if (i && fly) map.flyTo([i.lat, i.lon], Math.max(map.getZoom(), 16), { duration: 0.6 });
}

// ---- event details --------------------------------------------------------------------------

function renderDetails(s) {
  const box = $("#details");
  const i = s.incidents.find((x) => x.id === selected);
  if (!i) { box.innerHTML = `<div class="empty">Select an event to see its details.</div>`; box.dataset.html = ""; return; }
  const st = eventStatus(i);
  const flags = (i.mind_changed ? `<span class="flag mind">Diagnosis changed</span>` : "")
    + (i.after_restore ? `<span class="flag after">Found after restoration</span>` : "")
    + (i.critical.length ? `<span class="flag crit">${i.critical.length} critical</span>` : "");
  const callers = s_messages.filter((m) => m.incident === i.id && m.channel !== "crew").slice(-6).reverse();
  const steps = i.steps.map((x) => {
    const crew = x.crew ? (s.crews.find((c) => c.id === x.crew) || {}).name || x.crew : "–";
    return `<tr><td>${esc(crew)}</td><td>${esc(x.task)}</td><td>${esc(x.status)}</td><td class="mono">${x.depart_t != null ? clockOf(x.depart_t) : "–"}</td>
      <td class="mono">${x.arrive_t != null ? clockOf(x.arrive_t) : "–"}</td><td class="mono">${x.end_t != null ? clockOf(x.end_t) : "–"}</td></tr>`;
  }).join("");
  const plans = i.status !== "restored" && i.plans.length ? `<div class="section-t">Restoration switching</div>${i.plans.map((p) => p.safe
    ? `<div class="plan safe"><span class="tag">SAFE</span><span>${esc(p.title)}: ${esc(p.reason)}</span><button data-inc="${i.id}" data-plan="${p.id}">Approve</button></div>`
    : `<div class="plan blocked"><span class="tag">BLOCKED</span><span>${esc(p.title)}: ${esc(p.reason)}</span><span></span></div>`).join("")}` : "";
  const html = `
    <div class="det-head"><span class="st ${st}">${st}</span><h3>${esc(i.id)} · ${esc(i.title)}</h3>${flags}</div>
    <div class="fields">
      <div><span>Device</span><b title="${esc(i.label)}">${esc(i.cand)}</b></div>
      <div><span>Customers out</span><b>${fmt(i.customers_out)}</b></div>
      <div><span># Calls</span><b>${i.reports.length}</b></div>
      <div><span>Confidence</span><b>${Math.round(i.confidence * 100)}%</b></div>
      <div><span>First call</span><b>${clockOf(i.first_t)}</b></div>
      <div><span>Located</span><b>${clockOf(i.located_at)}</b></div>
      <div><span>Est. restore</span><b>${i.status === "restored" ? "–" : i.eta ? clockOf(i.eta) : "–"}</b></div>
      <div><span>Restored</span><b>${i.restored_at ? clockOf(i.restored_at) : "–"}</b></div>
    </div>
    <div class="sub" style="margin-bottom:6px">${esc(i.label)}</div>
    ${i.explanation ? `<div class="explain">${badge(i.explanation_model || "Muse Spark")} ${esc(i.explanation)}</div>` : ""}
    ${i.history.map((h) => `<div class="history">↺ ${clockOf(h.t)} ${esc(h.before)} → ${esc(h.after)} (${esc(h.by)})</div>`).join("")}
    ${i.critical.length ? `<div class="crit-list">Critical: ${i.critical.map(esc).join(" · ")}</div>` : ""}
    ${plans}
    <div class="section-t">Crew assignments</div>
    <table class="mini"><tr><th>Crew</th><th>Task</th><th>Status</th><th>Dispatched</th><th>On site</th><th>Done</th></tr>${steps}</table>
    <div class="section-t">Evidence</div>
    <ul class="reasons">${i.reasons.map((r) => `<li>${esc(r)}</li>`).join("")}${i.alternative ? `<li>Rival when located: ${esc(i.alternative.label)} (${Math.round(i.alternative.confidence * 100)}%)</li>` : ""}</ul>
    <div class="section-t">Priority</div>
    <div class="sub">${Object.entries(i.breakdown).map(([k, v]) => `${esc(k)} ${v}`).join(" + ")} = <b>${Math.round(i.priority)}</b></div>
    <div class="section-t">Latest callers</div>
    <table class="mini">${callers.map((m) => `<tr><td class="mono">${clockOf(m.t)}</td><td>${CHANNEL[m.channel] || m.channel}</td><td class="lang">${esc(m.language)}</td>
      <td title="${esc(m.text)}">${esc((m.fields.summary_en || m.text).slice(0, 70))}</td></tr>`).join("")}</table>`;
  if (box.dataset.html !== html) { box.dataset.html = html; box.innerHTML = html; }
}

// Delegated, on pointerdown: the pane re-renders while the storm runs.
$("#details").addEventListener("pointerdown", async (ev) => {
  const b = ev.target.closest("button[data-plan]");
  if (!b || b.disabled) return;
  b.disabled = true;
  b.textContent = "…";
  const r = await (await fetch("/api/plan", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ incident: b.dataset.inc, plan: b.dataset.plan }) })).json();
  if (!r.ok) alert(`Refused: ${r.reason}`);
});

// ---- dock tables -------------------------------------------------------------------------------

let s_messages = [];
const MAX_ROWS = 300;

function prepend(tbodyId, html, cls = "") {
  const tb = document.getElementById(tbodyId);
  const tr = document.createElement("tr");
  tr.className = `fresh ${cls}`;
  tr.innerHTML = html;
  tb.prepend(tr);
  while (tb.children.length > MAX_ROWS) tb.lastChild.remove();
}

function addLog(e) {
  const alarm = /Hazard|locked out|lockout|Meter network down|Refused|still dark/i.test(e.title);
  prepend("log", `<td class="mono">${esc(e.clock || clockOf(e.t))}</td><td>${badge(e.model)}</td><td>${esc(e.title)}</td><td>${esc(e.detail)}</td>`, alarm ? "alarm" : "");
}

function addCall(m) {
  s_messages.push(m);
  if (s_messages.length > 5000) s_messages = s_messages.slice(-4000);
  const f = m.fields || {};
  const loc = m.location || {};
  const clues = [f.symptom && f.symptom !== "none" ? f.symptom.replace("_", " ") : "", f.hazard && f.hazard !== "none" ? f.hazard.replace("_", " ").toUpperCase() : ""].filter(Boolean).join(" · ");
  const en = f.summary_en && f.summary_en !== m.text ? `<div class="en">${esc(f.summary_en)}</div>` : "";
  prepend("calls", `<td class="mono">${clockOf(m.t)}</td><td>${CHANNEL[m.channel] || esc(m.channel)}</td><td class="lang">${esc(m.language)}</td>
    <td class="msg">${esc(m.text)}${en}</td><td>${esc(clues)}</td>
    <td>${loc.street ? esc(`${loc.street} ${loc.house_no || ""}`) : esc(loc.method || "–")}${loc.transformer ? ` <span class="sub">${esc(loc.transformer)}</span>` : ""}</td>
    <td>${badge(m.model)}</td><td class="status-${m.status}">${esc(m.status === "duplicate" ? `dup ${m.dup_of}` : m.status)}</td><td class="mono">${esc(m.incident || "")}</td>`,
  f.hazard && f.hazard !== "none" ? "alarm" : "");
  if (loc.lat && m.status !== "junk" && m.status !== "duplicate") {
    L.circleMarker([loc.lat, loc.lon], { radius: 2.5, color: f.hazard && f.hazard !== "none" ? "#e5484d" : "#c9d2dc", weight: 0, fillOpacity: 0.75 })
      .bindTooltip(`${m.id}: ${esc(f.summary_en || m.text)}`, { className: "gm" }).addTo(layers.messages);
  }
}

function addOutbound(kind, x) {
  prepend("outbound", `<td class="mono">${clockOf(x.t)}</td><td>${kind}</td><td class="lang">${esc(x.language)}</td>
    <td>${x.to.length ? `${x.to.length} customer${x.to.length > 1 ? "s" : ""}` : esc(x.street)}</td><td class="msg">${esc(x.text)}</td><td>${badge(x.model || "Agent")}</td>`);
}

function renderCrewTable(s) {
  const html = s.crews.map((c) => `<tr><td>${esc(c.name)}</td><td>${esc(c.skills.join(", "))}</td><td class="crew-st">${esc(c.status)}</td>
    <td class="mono">${esc(c.incident || "")}</td><td>${esc(c.task || "")}</td></tr>`).join("");
  const tb = $("#crews");
  if (tb.dataset.html !== html) { tb.dataset.html = html; tb.innerHTML = html; }
}

document.querySelectorAll("#dock-tabs button").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll("#dock-tabs button, .dock-body .tab").forEach((x) => x.classList.toggle("on", x.dataset.tab === b.dataset.tab));
}));
document.querySelectorAll("#layers input").forEach((cb) => cb.addEventListener("change", () => {
  const extra = cb.dataset.layer === "crews" ? [layers.dispatch] : [];
  for (const l of [layers[cb.dataset.layer], ...extra]) cb.checked ? map.addLayer(l) : map.removeLayer(l);
}));

function addPhoto(ph) {
  if (!ph.lat) return;
  const a = ph.analysis;
  const img = a.mock ? "" : `<img src="/${esc(ph.path)}">`;
  L.circleMarker([ph.lat, ph.lon], { radius: 5, color: "#3cc2a0", weight: 2, fillOpacity: 0 })
    .bindPopup(`<div class="photo-pop">${img}<b>${esc(a.damage.replace("_", " "))}</b> · ${esc(a.severity)}<br>${esc(a.description)}${a.clearance_m != null ? `<br>Wire clearance ≈ ${a.clearance_m} m` : ""}<br>${a.models.map(badge).join(" ")}</div>`)
    .addTo(layers.messages);
}

// ---- state ------------------------------------------------------------------------------------

function applyState(s) {
  state = s;
  if (s.clock) $("#clock").textContent = s.clock;
  renderKpis(s);
  renderAgenda(s);
  renderDetails(s);
  renderNetwork(s);
  renderCrewTable(s);
}

function resetUI() {
  for (const id of ["log", "calls", "outbound"]) document.getElementById(id).innerHTML = "";
  layers.messages.clearLayers();
  s_messages = [];
  history.length = 0;
  selected = null;
}

function connect() {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    switch (msg.type) {
      case "snapshot":
        resetUI();
        msg.state.timeline.slice(-MAX_ROWS).forEach(addLog);
        msg.state.messages.forEach((m) => (m.channel === "crew" ? s_messages.push(m) : addCall(m)));
        (msg.state.notices || []).forEach((n) => addOutbound(n.kind === "restored" ? "Restored" : "ETR", n));
        msg.state.probes.forEach((p) => addOutbound("Question", { ...p, to: [] }));
        applyState(msg.state);
        break;
      case "state": applyState(msg.state); break;
      case "timeline": addLog(msg.entry); break;
      case "message": if (msg.message.channel === "crew") s_messages.push(msg.message); else addCall(msg.message); break;
      case "probe": addOutbound("Question", { ...msg.probe, to: [] }); break;
      case "photo": addPhoto(msg); break;
      case "notice": addOutbound(msg.notice.kind === "restored" ? "Restored" : "ETR", msg.notice); break;
      case "messages": $("#calls").innerHTML = ""; layers.messages.clearLayers(); s_messages = []; msg.messages.forEach(addCall); break;
      case "clock":
        $("#clock").textContent = msg.clock;
        $("#timelapse").hidden = !msg.timelapse;
        $("#progress-bar").style.width = `${Math.min(100, (100 * msg.elapsed) / msg.duration)}%`;
        if (msg.crews) renderCrewMarkers(msg.crews);
        break;
      case "reset": resetUI(); fetch("/api/state").then((r) => r.json()).then(applyState); break;
      case "scenario": location.reload(); break;
    }
  };
  ws.onclose = () => setTimeout(connect, 1000);
}

// ---- controls ---------------------------------------------------------------------------------

const control = (action) => fetch("/api/control", {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, speed: Number($("#speed").value) }),
});
$("#btn-start").onclick = () => control("start");
$("#btn-pause").onclick = () => control("pause");
$("#btn-reset").onclick = () => control("reset");
$("#speed").onchange = () => control("speed");
$("#btn-net").onclick = () => control($("#btn-net").dataset.offline ? "online" : "offline");
$("#scenario").onchange = () => fetch("/api/scenario", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: $("#scenario").value }) });

const dlg = $("#map-dialog");
$("#btn-map").onclick = () => dlg.showModal();
$("#dlg-close").onclick = () => dlg.close();
$("#dlg-file").onchange = (e) => { const f = e.target.files[0]; if (f) $("#dlg-img").src = URL.createObjectURL(f); };
$("#dlg-run").onclick = async () => {
  const out = $("#dlg-result");
  out.innerHTML = `<span class="k">Reading the diagram…</span>`;
  const body = new FormData();
  const file = $("#dlg-file").files[0];
  if (file) body.append("image", file);
  const r = await (await fetch("/api/diagram", { method: "POST", body })).json();
  const s = r.score;
  out.innerHTML = `${badge(r.model)}
    <div class="big">${s.connections_correct} / ${s.connections_total}</div><div class="k">connections correct (precision ${Math.round(s.precision * 100)}%)</div>
    <div class="big">${s.devices_correct} / ${s.devices_total}</div><div class="k">protective devices placed correctly</div>
    ${s.missing.length ? `<div class="k">Missed: ${s.missing.map(esc).join(", ")}</div>` : ""}
    ${s.extra.length ? `<div class="k">Not on the feeder: ${s.extra.map(esc).join(", ")}</div>` : ""}`;
};

loadGrid().then(connect);
