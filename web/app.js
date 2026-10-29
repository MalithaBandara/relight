// GridMedic control room: renders the feeder, incoming messages, incidents and their crews,
// switching plans, and the agent's questions, all driven by the WebSocket stream from the server.

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const MODEL_CLASS = (m) => {
  if (!m) return "code";
  if (m.startsWith("mock")) return "mock";
  if (m.includes("SAM")) return "sam";
  if (m.includes("Voice")) return "voice";
  if (m.includes("Spark") || m.includes("Glimmer")) return "spark";
  if (m === "SCADA") return "scada";
  if (m === "Agent" || m === "Operator") return "agent";
  return "code";
};
const badge = (m) => `<span class="badge ${MODEL_CLASS(m)}">${esc(m)}</span>`;
const CHANNEL = { call: "📞", whatsapp: "💬", sms: "✉️", crew: "👷", web: "📱" };
const START_MIN = 15 * 60;
const clockOf = (t) => { const m = Math.floor(START_MIN + t / 60); return `${String(Math.floor(m / 60) % 24).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`; };

const map = L.map("map", { zoomControl: true });
// OpenStreetMap tiles, darkened in CSS (.leaflet-tile-pane) to suit the control-room look.
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: '&copy; OpenStreetMap contributors', maxZoom: 19,
}).addTo(map);

const layers = {
  lines: L.layerGroup().addTo(map),
  xfmr: L.layerGroup().addTo(map),
  devices: L.layerGroup().addTo(map),
  messages: L.layerGroup().addTo(map),
  faults: L.layerGroup().addTo(map),
  hazards: L.layerGroup().addTo(map),
  probes: L.layerGroup().addTo(map),
  dispatch: L.layerGroup().addTo(map),
  crews: L.layerGroup().addTo(map),
};
const xfmrMarkers = {};
const xfmrSection = {};
const deviceEls = {};
const sectionLines = {};
let tieLine = null;
let grid = null;
let state = null;
const openCards = new Set();
const crewMarkers = {};

async function loadGrid() {
  grid = await (await fetch("/api/grid")).json();
  $("#scenario-title").textContent = grid.title;
  const bounds = [];
  for (const f of grid.geojson.features) {
    const p = f.properties;
    if (p.kind === "section" || p.kind === "tie_line") {
      const ll = f.geometry.coordinates.map(([lon, lat]) => [lat, lon]);
      bounds.push(...ll);
      const line = L.polyline(ll, p.kind === "tie_line"
        ? { color: "#8b9bb0", weight: 2, dashArray: "6 6", opacity: 0.8 }
        : { color: "#5b7a99", weight: 3, opacity: 0.85 })
        .bindTooltip(p.kind === "tie_line" ? "Tie to Feeder 2 (through TS-1)" : `${p.street} · section ${p.id}`, { className: "gm", sticky: true })
        .addTo(layers.lines);
      if (p.kind === "tie_line") tieLine = line; else sectionLines[p.id] = line;
    } else if (p.kind === "transformer") {
      const [lon, lat] = f.geometry.coordinates;
      xfmrSection[p.id] = p.section;
      xfmrMarkers[p.id] = L.circleMarker([lat, lon], { radius: 4, color: "#3ddc97", weight: 1, fillOpacity: 0.9 })
        .bindTooltip(`${p.id} · ${grid.customers[p.id] || 0} customers`, { className: "gm" })
        .addTo(layers.xfmr);
    } else if (p.kind === "feeder2") {
      const [lon, lat] = f.geometry.coordinates;
      L.marker([lat, lon], { icon: L.divIcon({ className: "", html: `<div style="font-size:18px">🏭</div>`, iconSize: [18, 18] }) })
        .bindTooltip(p.label, { className: "gm" }).addTo(layers.devices);
    } else {
      const [lon, lat] = f.geometry.coordinates;
      const isSwitch = p.kind === "switch" || p.kind === "tie";
      const html = isSwitch ? `<div class="switch-icon ${p.kind === "tie" ? "open" : ""}" id="dev-${p.id}"></div>`
                            : `<div class="device-icon" id="dev-${p.id}"></div>`;
      L.marker([lat, lon], { icon: L.divIcon({ className: "", html, iconSize: [14, 14] }) })
        .bindTooltip(`${p.label} (${p.id})${p.scada ? " · remote" : ""}`, { className: "gm" }).addTo(layers.devices);
      deviceEls[p.id] = isSwitch ? "switch" : "device";
    }
  }
  for (const lm of grid.landmarks) {
    L.circleMarker([lm.lat, lm.lon], { radius: 3, color: "#8b9bb0", weight: 1, fillOpacity: 0.4 })
      .bindTooltip(lm.name + (lm.critical ? ` · critical: ${lm.critical}` : ""), { className: "gm" })
      .addTo(layers.lines);
  }
  L.marker(grid.substation, { icon: L.divIcon({ className: "", html: `<div style="font-size:20px">🏭</div>`, iconSize: [20, 20] }) })
    .bindTooltip("Wakwella substation (bus 800)", { className: "gm" }).addTo(layers.devices);
  map.fitBounds(bounds, { padding: [30, 30] });
  addLegend();
}

function addLegend() {
  const legend = L.control({ position: "bottomleft" });
  legend.onAdd = () => {
    const d = L.DomUtil.create("div", "legend");
    d.innerHTML = `<b>IEEE 34-bus feeder over Galle</b> · fictional data<br>
      <i style="background:#3ddc97"></i>transformer energised<br>
      <i style="background:#ff4d4f"></i>transformer out (GridMedic's belief)<br>
      <i style="background:#ffb020"></i>incident (ring = confidence)<br>
      <i style="background:#2ec4e6"></i>agent question to a customer<br>
      ▣ switch closed &nbsp; ▢ open &nbsp; ⚠️ hazard &nbsp; 🚚 crew`;
    return d;
  };
  legend.addTo(map);
}

// ---- rendering ---------------------------------------------------------------

function renderStats(s) {
  const c = s.counts;
  $("#s-messages").textContent = c.messages;
  $("#s-dupes").textContent = c.duplicates;
  $("#s-junk").textContent = c.junk;
  $("#s-bd").textContent = c.bd_sms;
  $("#s-out").textContent = c.customers_out;
  $("#s-langs").textContent = Object.keys(c.languages).map((l) => l.toUpperCase()).join(" · ") || "–";
  const found = s.truth.filter((t) => t.found).length;
  $("#s-located").textContent = `${found} / ${s.truth.length}`;
  if (s.plan && s.plan.plan && s.plan.plan.length) {
    $("#s-hazard").textContent = s.hazards.some((h) => h.kind === "live_wire")
      ? `${s.plan.hazard_wait_min} min (vs ${s.baseline.hazard_wait_min})` : "–";
    $("#s-custmin").textContent = `${Math.round((s.baseline.customer_minutes - s.plan.customer_minutes) / 60).toLocaleString()} h`;
  }
  $("#s-notified").textContent = c.notified ?? 0;
  $("#s-models").innerHTML = Object.entries(c.model_calls).map(([m, n]) => `${badge(m)}<span class="badge count">${n}</span>`).join(" ")
    || `<span class="k" style="color:var(--muted)">model calls appear here</span>`;
  setNetwork(s.offline, c.queued);
  const mode = $("#mode");
  mode.textContent = s.mode === "live" ? "LIVE · Meta Model API" : "MOCK · cached / ground truth";
  mode.className = `mode ${s.mode}`;
}

function stepsHtml(inc) {
  return inc.steps.map((st) => {
    const crew = st.crew ? (state.crews.find((c) => c.id === st.crew) || {}).name || st.crew : "waiting for a crew";
    const when = st.status === "enroute" ? `arrives ${clockOf(st.arrive_t)}` : st.status === "onsite" ? `done ~${clockOf(st.end_t)}` : st.status === "done" ? "done" : "";
    return `<span class="chip">${st.status === "done" ? "✓" : "🚚"} ${esc(st.task)} · ${esc(crew)}${when ? " · " + when : ""}</span>`;
  }).join("");
}

function plansHtml(inc) {
  if (!inc.plans.length || inc.status === "restored") return "";
  return `<div class="plans">${inc.plans.map((p) => p.safe
    ? `<div class="plan safe"><span class="tag">SAFE</span><span class="txt">${esc(p.title)}: ${esc(p.reason)}</span>
         <button data-inc="${inc.id}" data-plan="${p.id}">Approve</button></div>`
    : `<div class="plan blocked"><span class="tag">BLOCKED</span><span class="txt">${esc(p.title)}: ${esc(p.reason)}</span></div>`).join("")}</div>`;
}

function renderQueue(s) {
  const ol = $("#queue");
  if (!s.incidents.length && !s.suspects.length && !s.hazards.length) { ol.innerHTML = `<li class="empty">Waiting for the storm…</li>`; return; }
  const active = s.incidents.filter((i) => i.status !== "restored");
  const html = s.incidents.map((f) => {
    const rank = f.status === "restored" ? "✓" : active.indexOf(f) + 1;
    const crit = f.critical.map((c) => `<span class="chip crit">${esc(c)}</span>`).join("");
    const badges = (f.mind_changed ? `<span class="chip mind">↺ mind changed</span>` : "")
      + (f.after_restore ? `<span class="chip after">found after restoration</span>` : "")
      + (f.switching.length && f.status !== "restored" ? `<span class="chip">switched around fault</span>` : "");
    const explain = f.explanation ? `<div class="explain">${badge(f.explanation_model || "Muse Spark")} ${esc(f.explanation)}</div>` : "";
    const hist = f.history.map((h) => `<div class="history">↺ ${esc(h.before)} → ${esc(h.after)} (${esc(h.by)})</div>`).join("");
    const bd = Object.entries(f.breakdown).map(([k, v]) => `${esc(k)} ${v}`).join(" + ");
    const alt = f.alternative ? `Rival when located: ${esc(f.alternative.label)} (${Math.round(f.alternative.confidence * 100)}%)` : "";
    const eta = f.status === "restored" ? `restored ${clockOf(f.restored_at)}` : f.eta ? `back ≈ ${clockOf(f.eta)}` : "";
    return `<li class="fault ${f.kind} ${f.status === "restored" ? "restored" : ""} ${openCards.has(f.id) ? "open" : ""}" data-id="${f.id}">
      <div class="row"><span class="rank">${rank}</span><span class="title">${esc(f.id)} · ${esc(f.title)}</span>
        <span class="chip status ${esc(f.status)}">${esc(f.status)}</span><span class="prio">P ${f.priority}</span></div>
      <div class="sub">${esc(f.label)} · ${f.customers_out} customers · ${Math.round(f.confidence * 100)}% · ${eta}</div>
      <div class="conf"><div style="width:${Math.round(f.confidence * 100)}%"></div></div>
      ${hist}${explain}
      <div class="crews">${badges}${crit}${stepsHtml(f)}</div>
      ${plansHtml(f)}
      <div class="why">${f.reasons.map(esc).join("<br>")}<br>${alt}<br>Priority = ${bd}</div>
    </li>`;
  }).join("") + s.suspects.map((x) => `<li class="suspect">? Suspected: ${esc(x.label)} · ${Math.round(x.confidence * 100)}%${x.alternative ? ` vs ${esc(x.alternative.label)} ${Math.round(x.alternative.confidence * 100)}%` : ""}</li>`).join("");
  // Only touch the DOM when something changed, so buttons stay clickable while the storm runs.
  if (html === ol.dataset.html) return;
  ol.dataset.html = html;
  ol.innerHTML = html;
  ol.querySelectorAll("li.fault").forEach((li) => li.addEventListener("click", (ev) => {
    if (ev.target.tagName === "BUTTON") return;
    const id = li.dataset.id;
    openCards.has(id) ? openCards.delete(id) : openCards.add(id);
    li.classList.toggle("open");
    const f = state.incidents.find((x) => x.id === id);
    if (f) map.flyTo([f.lat, f.lon], 16, { duration: 0.8 });
  }));
}

// Delegated, and on pointerdown: the queue re-renders while the storm runs, so a click must not
// depend on the button surviving until mouseup.
$("#queue").addEventListener("pointerdown", async (ev) => {
  const b = ev.target.closest("button[data-plan]");
  if (!b || b.disabled) return;
  b.disabled = true;
  b.textContent = "…";
  const r = await (await fetch("/api/plan", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ incident: b.dataset.inc, plan: b.dataset.plan }) })).json();
  if (!r.ok) alert(`Refused: ${r.reason}`);
});

function renderMap(s) {
  const dead = new Set(s.dead_transformers);
  const deadSections = new Set();
  for (const [id, m] of Object.entries(xfmrMarkers)) {
    const out = dead.has(id);
    if (out) deadSections.add(xfmrSection[id]);
    m.setStyle(out ? { color: "#ff4d4f", fillColor: "#ff4d4f", radius: 5 } : { color: "#3ddc97", fillColor: "#3ddc97", radius: 4 });
  }
  for (const [id, line] of Object.entries(sectionLines)) {
    line.setStyle(deadSections.has(id) ? { color: "#a33a3c", weight: 4 } : { color: "#5b7a99", weight: 3 });
  }
  const open = new Set(s.open_devices);
  for (const id of Object.keys(deviceEls)) {
    const el = document.getElementById(`dev-${id}`);
    if (el) el.classList.toggle("open", open.has(id));
  }
  if (tieLine) tieLine.setStyle(open.has("TS-1") ? { color: "#8b9bb0", dashArray: "6 6", weight: 2 } : { color: "#3ddc97", dashArray: null, weight: 4 });

  layers.faults.clearLayers();
  for (const f of s.incidents) {
    if (f.status === "restored") continue;
    L.marker([f.lat, f.lon], {
      icon: L.divIcon({
        className: "fault-marker", iconSize: [46, 46], iconAnchor: [23, 23],
        html: `<div class="fault-ring ${f.kind}">${Math.round(f.confidence * 100)}%</div>
               <div class="fault-label">${esc(f.id)} ${esc(f.title)}${f.mind_changed ? " ↺" : ""}</div>`,
      }),
      zIndexOffset: 1000,
    }).addTo(layers.faults);
  }
  for (const x of s.suspects) {
    L.marker([x.lat, x.lon], { icon: L.divIcon({ className: "fault-marker", iconSize: [46, 46], iconAnchor: [23, 23],
      html: `<div class="fault-ring tentative">${Math.round(x.confidence * 100)}%</div>` }) }).addTo(layers.faults);
  }
  layers.hazards.clearLayers();
  for (const h of s.hazards) {
    L.marker([h.lat, h.lon], { icon: L.divIcon({ className: "", html: `<div class="hazard-icon ${h.safe ? "safe" : ""}">⚠️</div>`, iconSize: [26, 26] }), zIndexOffset: 2000 })
      .bindTooltip(`${h.id}: ${h.kind.replace("_", " ")} · ${h.evidence.length} reports${h.safe ? " · made safe" : ""}`, { className: "gm" }).addTo(layers.hazards);
  }
  layers.probes.clearLayers();
  for (const p of s.probes) {
    const on = p.answer && p.answer.includes("ON");
    L.marker([p.lat, p.lon], { icon: L.divIcon({ className: "", html: `<div class="probe-icon ${on ? "on" : ""}">${on ? "✓" : "?"}</div>`, iconSize: [26, 26] }) })
      .bindTooltip(`${p.id} to ${esc(p.street)} ${p.house_no}: ${p.answer || "awaiting reply"}`, { className: "gm" })
      .addTo(layers.probes);
  }
  renderCrews(s.crews);
}

function renderCrews(crews) {
  layers.dispatch.clearLayers();
  for (const c of crews) {
    const html = `<div class="crew-icon ${c.status === "enroute" ? "moving" : ""}">🚚</div>`;
    if (!crewMarkers[c.id]) {
      crewMarkers[c.id] = L.marker([c.lat, c.lon], { icon: L.divIcon({ className: "", html, iconSize: [18, 18] }), zIndexOffset: 1500 })
        .addTo(layers.crews);
    }
    crewMarkers[c.id].setLatLng([c.lat, c.lon]).setIcon(L.divIcon({ className: "", html, iconSize: [18, 18] }));
    crewMarkers[c.id].bindTooltip(`${c.name}: ${c.status}${c.task ? " · " + c.task : ""}${c.incident ? " (" + c.incident + ")" : ""}`, { className: "gm" });
    const inc = state && state.incidents.find((i) => i.id === c.incident);
    if (inc && c.status === "enroute") {
      L.polyline([[c.lat, c.lon], [inc.lat, inc.lon]], { color: "#ffb020", weight: 1.5, dashArray: "4 6", opacity: 0.8 }).addTo(layers.dispatch);
    }
  }
}

function addTimeline(e) {
  const li = document.createElement("li");
  li.className = MODEL_CLASS(e.model);
  li.innerHTML = `<span class="t">${esc(e.clock || clockOf(e.t))}</span>${badge(e.model)}<span class="txt"><b>${esc(e.title)}</b>${e.detail ? `<div>${esc(e.detail)}</div>` : ""}</span>`;
  const ul = $("#timeline");
  ul.prepend(li);
  while (ul.children.length > 250) ul.lastChild.remove();
}

function addMessage(m) {
  const f = m.fields || {};
  const li = document.createElement("li");
  const hazard = f.hazard && f.hazard !== "none";
  li.className = `${m.status} ${hazard ? "hazard" : ""} ${m.probe_reply ? "probe" : ""}`;
  const en = f.summary_en && f.summary_en !== m.text ? `<div class="en">→ ${esc(f.summary_en)}</div>` : "";
  const where = m.location && m.location.transformer ? ` · ${esc(m.location.transformer)}` : "";
  const owner = m.incident ? ` · ${esc(m.incident)}` : "";
  li.innerHTML = `<div class="meta">${CHANNEL[m.channel] || ""} <span class="id">${esc(m.id)}</span>
      <span class="lang">${esc(m.language)}</span>${badge(m.model)}${where}${owner}
      <span class="status ${m.status}">${esc(m.status === "duplicate" ? `dup of ${m.dup_of}` : m.status)}</span></div>
    <div class="text">${esc(m.text)}</div>${en}`;
  const ul = $("#feed");
  ul.prepend(li);
  while (ul.children.length > 150) ul.lastChild.remove();
  if (m.location && m.location.lat && m.status !== "junk") {
    const color = m.status === "duplicate" ? "#5b6675" : hazard ? "#ff4d4f" : m.channel === "crew" ? "#ffb020" : "#e6edf3";
    L.circleMarker([m.location.lat, m.location.lon], { radius: 3.5, color, weight: 1, fillOpacity: 0.9 })
      .bindTooltip(`${m.id}: ${esc(f.summary_en || m.text)}`, { className: "gm" }).addTo(layers.messages);
  }
}

function addProbeQuestion(p) {
  const li = document.createElement("li");
  li.className = "probe";
  li.innerHTML = `<div class="meta">💬 <span class="id">${esc(p.id)}</span><span class="lang">${esc(p.language)}</span>${badge("Agent")}
    to ${esc(p.street)} ${p.house_no} · ${esc(p.transformer)}<span class="status new">question sent</span></div>
    <div class="text">${esc(p.text)}</div>`;
  $("#feed").prepend(li);
}

function addNotice(n) {
  const li = document.createElement("li");
  li.className = "notice";
  li.innerHTML = `<div class="meta">📤 <span class="id">${esc(n.id)}</span><span class="lang">${esc(n.language)}</span>${badge(n.model)}
    to ${n.to.length} customer${n.to.length > 1 ? "s" : ""}<span class="status new">${n.kind === "restored" ? "power restored" : "restoration time sent"}</span></div>
    <div class="text">${esc(n.text)}</div>`;
  $("#feed").prepend(li);
}

function addPhoto(ph) {
  if (!ph.lat) return;
  const a = ph.analysis;
  const img = a.mock ? "" : `<img src="/${esc(ph.path)}">`;
  L.marker([ph.lat, ph.lon], { icon: L.divIcon({ className: "", html: `<div style="font-size:18px">📷</div>`, iconSize: [18, 18] }) })
    .bindPopup(`<div class="photo-pop">${img}<b>${esc(a.damage.replace("_", " "))}</b> · ${esc(a.severity)}<br>${esc(a.description)}${a.clearance_m != null ? `<br>Wire clearance ≈ ${a.clearance_m} m` : ""}<br>${a.models.map(badge).join(" ")}</div>`)
    .addTo(layers.messages);
}

function setNetwork(offline, queued) {
  $("#offline-banner").hidden = !offline;
  $("#queued").textContent = queued ?? 0;
  const b = $("#btn-net");
  b.textContent = offline ? "📴 Offline: Glimmer" : "📡 Online";
  b.classList.toggle("offline", !!offline);
  b.dataset.offline = offline ? "1" : "";
}

function applyState(s) {
  state = s;
  if (s.clock) $("#clock").textContent = s.clock;
  renderStats(s);
  renderQueue(s);
  renderMap(s);
}

function resetUI() {
  $("#timeline").innerHTML = "";
  $("#feed").innerHTML = "";
  layers.messages.clearLayers();
  openCards.clear();
}

// ---- wiring ----------------------------------------------------------------------

function connect() {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    switch (msg.type) {
      case "snapshot":
        resetUI();
        msg.state.timeline.forEach(addTimeline);
        msg.state.messages.forEach(addMessage);
        (msg.state.notices || []).forEach(addNotice);
        applyState(msg.state);
        break;
      case "state": applyState(msg.state); break;
      case "timeline": addTimeline(msg.entry); break;
      case "message": addMessage(msg.message); break;
      case "probe": addProbeQuestion(msg.probe); break;
      case "photo": addPhoto(msg); break;
      case "notice": addNotice(msg.notice); break;
      case "messages": $("#feed").innerHTML = ""; layers.messages.clearLayers(); msg.messages.forEach(addMessage); break;
      case "clock":
        $("#clock").textContent = msg.clock;
        $("#timelapse").hidden = !msg.timelapse;
        $("#progress-bar").style.width = `${Math.min(100, (100 * msg.elapsed) / msg.duration)}%`;
        if (msg.crews) renderCrews(msg.crews);
        break;
      case "reset": resetUI(); fetch("/api/state").then((r) => r.json()).then(applyState); break;
    }
  };
  ws.onclose = () => setTimeout(connect, 1000);
}

const control = (action) => fetch("/api/control", {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ action, speed: Number($("#speed").value) }),
});
$("#btn-start").onclick = () => control("start");
$("#btn-pause").onclick = () => control("pause");
$("#btn-reset").onclick = () => control("reset");
$("#speed").onchange = () => control("speed");
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
$("#btn-net").onclick = () => control($("#btn-net").dataset.offline ? "online" : "offline");

loadGrid().then(connect);
