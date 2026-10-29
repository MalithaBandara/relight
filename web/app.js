// GridMedic live map: renders the feeder, incoming messages, located faults, the agent's
// questions and crew dispatch, all driven by the WebSocket stream from the server.

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmtClock = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

const MODEL_CLASS = (m) => {
  if (!m) return "code";
  if (m.startsWith("mock")) return "mock";
  if (m.includes("SAM")) return "sam";
  if (m.includes("Voice")) return "voice";
  if (m.includes("Spark") || m.includes("Glimmer")) return "spark";
  if (m === "SCADA") return "scada";
  if (m === "Agent") return "agent";
  return "code";
};
const badge = (m) => `<span class="badge ${MODEL_CLASS(m)}">${esc(m)}</span>`;
const CHANNEL = { call: "📞", whatsapp: "💬", sms: "✉️", crew: "👷" };

const map = L.map("map", { zoomControl: true, preferCanvas: false });
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
const deviceMarkers = {};
const sectionLines = {};
let grid = null;
let state = null;
const openFaults = new Set();

async function loadGrid() {
  grid = await (await fetch("/api/grid")).json();
  $("#scenario-title").textContent = grid.title;
  const bounds = [];
  for (const f of grid.geojson.features) {
    const p = f.properties;
    if (p.kind === "section") {
      const ll = f.geometry.coordinates.map(([lon, lat]) => [lat, lon]);
      bounds.push(...ll);
      sectionLines[p.id] = L.polyline(ll, { color: "#5b7a99", weight: 3, opacity: 0.85 })
        .bindTooltip(`${p.street} · section ${p.id}`, { className: "gm", sticky: true })
        .addTo(layers.lines);
    } else if (p.kind === "transformer") {
      const [lon, lat] = f.geometry.coordinates;
      xfmrMarkers[p.id] = L.circleMarker([lat, lon], { radius: 4, color: "#3ddc97", weight: 1, fillOpacity: 0.9 })
        .bindTooltip(`${p.id} · ${grid.customers[p.id] || 0} customers`, { className: "gm" })
        .addTo(layers.xfmr);
    } else {
      const [lon, lat] = f.geometry.coordinates;
      deviceMarkers[p.id] = L.marker([lat, lon], {
        icon: L.divIcon({ className: "", html: `<div class="device-icon" id="dev-${p.id}"></div>`, iconSize: [12, 12] }),
      }).bindTooltip(`${p.label} (${p.id})${p.scada ? " · SCADA" : ""}`, { className: "gm" }).addTo(layers.devices);
    }
  }
  for (const lm of grid.landmarks) {
    L.circleMarker([lm.lat, lm.lon], { radius: 3, color: "#8b9bb0", weight: 1, fillOpacity: 0.4 })
      .bindTooltip(lm.name + (lm.critical ? ` · critical: ${lm.critical}` : ""), { className: "gm" })
      .addTo(layers.lines);
  }
  for (const c of grid.crews) {
    L.marker([c.lat, c.lon], { icon: L.divIcon({ className: "", html: `<div class="crew-icon">🚚</div>`, iconSize: [18, 18] }) })
      .bindTooltip(`${c.name} (${c.skills.join(", ")})`, { className: "gm" }).addTo(layers.crews);
  }
  const sub = grid.substation;
  L.marker(sub, { icon: L.divIcon({ className: "", html: `<div style="font-size:20px">🏭</div>`, iconSize: [20, 20] }) })
    .bindTooltip("Wakwella substation (bus 800)", { className: "gm" }).addTo(layers.devices);
  map.fitBounds(bounds, { padding: [30, 30] });
  addLegend();
}

function addLegend() {
  const legend = L.control({ position: "bottomleft" });
  legend.onAdd = () => {
    const d = L.DomUtil.create("div", "legend");
    d.innerHTML = `<b>IEEE 34-bus feeder over Galle</b><br>
      <i style="background:#3ddc97"></i>transformer energised<br>
      <i style="background:#ff4d4f"></i>transformer out (inferred)<br>
      <i style="background:#ffb020"></i>located fault (ring = confidence)<br>
      <i style="background:#2ec4e6"></i>agent question to a customer<br>
      ⚠️ public hazard &nbsp; 🚚 crew`;
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
  $("#s-langs").textContent = Object.keys(c.languages).map((l) => l.toUpperCase()).join(" · ") || "–";
  const found = s.truth.filter((t) => t.found).length;
  $("#s-located").textContent = `${found} / ${s.truth.length}`;
  if (s.plan && s.plan.plan && s.plan.plan.length) {
    $("#s-hazard").textContent = s.hazards.some((h) => h.kind === "live_wire")
      ? `${s.plan.hazard_wait_min} min (vs ${s.baseline.hazard_wait_min})` : "–";
    const saved = (s.baseline.customer_minutes - s.plan.customer_minutes) / 60;
    $("#s-custmin").textContent = `${Math.round(saved).toLocaleString()} h`;
  }
  $("#s-models").innerHTML = Object.entries(c.model_calls).map(([m, n]) => `${badge(m)}<span class="badge count">${n}</span>`).join(" ")
    || `<span class="k" style="color:var(--muted)">model calls appear here</span>`;
  $("#s-notified").textContent = c.notified ?? 0;
  setNetwork(s.offline, c.queued);
  const mode = $("#mode");
  mode.textContent = s.mode === "live" ? "LIVE · Meta Model API" : "MOCK · cached / ground truth";
  mode.className = `mode ${s.mode}`;
}

function renderQueue(s) {
  const ol = $("#queue");
  if (!s.faults.length && !s.hazards.length) { ol.innerHTML = `<li class="empty">Waiting for the storm…</li>`; return; }
  ol.innerHTML = s.faults.map((f, i) => {
    const d = f.dispatch;
    const tentative = f.confidence < 0.8;
    const crews = d ? d.steps.map((st) => `<span class="chip">🚚 ${esc(st.crew_name)}: ${esc(st.task)} · +${st.start_min}m</span>`).join("") : "";
    const crit = f.critical.map((c) => `<span class="chip crit">${esc(c)}</span>`).join("");
    const bd = Object.entries(f.breakdown).map(([k, v]) => `${esc(k)} ${v}`).join(" + ");
    const explain = f.explanation ? `<div class="explain">${badge(f.explanation_model || "Muse Spark")} ${esc(f.explanation)}</div>` : "";
    const alt = f.alternative ? `Rival: ${esc(f.alternative.label)} (${Math.round(f.alternative.confidence * 100)}%)` : "";
    return `<li class="fault ${f.kind} ${tentative ? "tentative" : ""} ${openFaults.has(f.id) ? "open" : ""}" data-id="${f.id}">
      <div class="row"><span class="rank">${i + 1}</span><span class="title">${esc(f.title)}</span><span class="prio">P ${f.priority}</span></div>
      <div class="sub">${esc(f.label)} · ${f.customers_out} customers · ${Math.round(f.confidence * 100)}% confident${d ? ` · restore ≈ +${d.restore_min} min` : ""}</div>
      <div class="conf"><div style="width:${Math.round(f.confidence * 100)}%"></div></div>
      ${explain}
      <div class="crews">${crit}${crews}</div>
      <div class="why">${f.reasons.map(esc).join("<br>")}<br>${alt}<br>Priority = ${bd}</div>
    </li>`;
  }).join("");
  ol.querySelectorAll("li.fault").forEach((li) => li.addEventListener("click", () => {
    const id = li.dataset.id;
    openFaults.has(id) ? openFaults.delete(id) : openFaults.add(id);
    li.classList.toggle("open");
    const f = state.faults.find((x) => x.id === id);
    if (f) map.flyTo([f.lat, f.lon], 16, { duration: 0.8 });
  }));
}

function renderMap(s) {
  const out = new Set(s.faults.flatMap((f) => f.transformers));
  for (const [id, m] of Object.entries(xfmrMarkers)) {
    m.setStyle(out.has(id) ? { color: "#ff4d4f", fillColor: "#ff4d4f", radius: 5 } : { color: "#3ddc97", fillColor: "#3ddc97", radius: 4 });
  }
  const outSections = new Set();
  for (const f of s.faults) for (const t of f.transformers) {
    const p = grid.geojson.features.find((x) => x.properties.id === t);
    if (p) outSections.add(p.properties.section);
  }
  for (const [id, line] of Object.entries(sectionLines)) {
    line.setStyle(outSections.has(id) ? { color: "#a33a3c", weight: 4 } : { color: "#5b7a99", weight: 3 });
  }
  for (const dev of Object.keys(deviceMarkers)) {
    const el = document.getElementById(`dev-${dev}`);
    if (el) el.classList.toggle("open", s.scada_open.includes(dev));
  }

  layers.faults.clearLayers();
  layers.dispatch.clearLayers();
  for (const f of s.faults) {
    const tentative = f.confidence < 0.8;
    L.marker([f.lat, f.lon], {
      icon: L.divIcon({
        className: "fault-marker", iconSize: [46, 46], iconAnchor: [23, 23],
        html: `<div class="fault-ring ${f.kind} ${tentative ? "tentative" : ""}">${Math.round(f.confidence * 100)}%</div>
               <div class="fault-label">${esc(f.title)} · ${esc(f.device)}</div>`,
      }),
      zIndexOffset: 1000,
    }).addTo(layers.faults);
    if (f.dispatch) {
      for (const st of f.dispatch.steps) {
        const crew = grid.crews.find((c) => c.id === st.crew);
        if (crew) L.polyline([[crew.lat, crew.lon], [f.lat, f.lon]], { color: "#ffb020", weight: 1.5, dashArray: "4 6", opacity: 0.7 }).addTo(layers.dispatch);
      }
    }
  }
  layers.hazards.clearLayers();
  for (const h of s.hazards) {
    L.marker([h.lat, h.lon], { icon: L.divIcon({ className: "", html: `<div class="hazard-icon">⚠️</div>`, iconSize: [26, 26] }), zIndexOffset: 2000 })
      .bindTooltip(`${h.id}: ${h.kind.replace("_", " ")} · ${h.evidence.length} reports`, { className: "gm" }).addTo(layers.hazards);
  }
  layers.probes.clearLayers();
  for (const p of s.probes) {
    const f = s.faults.find((x) => x.id === p.fault);
    const on = p.answer && p.answer.includes("ON");
    if (f) L.polyline([[f.lat, f.lon], [p.lat, p.lon]], { color: on ? "#3ddc97" : "#2ec4e6", weight: 2, dashArray: "2 6" }).addTo(layers.probes);
    L.marker([p.lat, p.lon], { icon: L.divIcon({ className: "", html: `<div class="probe-icon ${on ? "on" : ""}">${on ? "✓" : "?"}</div>`, iconSize: [26, 26] }) })
      .bindTooltip(`${p.id} to ${esc(p.street)} ${p.house_no}: ${p.answer || "awaiting reply"}`, { className: "gm", permanent: false })
      .addTo(layers.probes);
  }
}

function addTimeline(e) {
  const li = document.createElement("li");
  li.className = MODEL_CLASS(e.model);
  li.innerHTML = `<span class="t">${fmtClock(e.t)}</span>${badge(e.model)}<span class="txt"><b>${esc(e.title)}</b>${e.detail ? `<div>${esc(e.detail)}</div>` : ""}</span>`;
  const ul = $("#timeline");
  ul.prepend(li);
  while (ul.children.length > 200) ul.lastChild.remove();
}

function addMessage(m) {
  const f = m.fields || {};
  const li = document.createElement("li");
  const hazard = f.hazard && f.hazard !== "none";
  li.className = `${m.status} ${hazard ? "hazard" : ""} ${m.probe_reply ? "probe" : ""}`;
  const en = f.summary_en && f.summary_en !== m.text ? `<div class="en">→ ${esc(f.summary_en)}</div>` : "";
  const where = m.location && m.location.transformer ? ` · ${esc(m.location.transformer)}` : "";
  li.innerHTML = `<div class="meta">${CHANNEL[m.channel] || ""} <span class="id">${esc(m.id)}</span>
      <span class="lang">${esc(m.language)}</span>${badge(m.model)}${where}
      <span class="status ${m.status}">${esc(m.status === "duplicate" ? `dup of ${m.dup_of}` : m.status)}</span></div>
    <div class="text">${esc(m.text)}</div>${en}`;
  const ul = $("#feed");
  ul.prepend(li);
  while (ul.children.length > 120) ul.lastChild.remove();
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

function addNotice(n) {
  const li = document.createElement("li");
  li.className = "notice";
  li.innerHTML = `<div class="meta">📤 <span class="id">${esc(n.id)}</span><span class="lang">${esc(n.language)}</span>${badge(n.model)}
    to ${n.to.length} customer${n.to.length > 1 ? "s" : ""}<span class="status new">restoration time sent</span></div>
    <div class="text">${esc(n.text)}</div>`;
  $("#feed").prepend(li);
}

function applyState(s) {
  state = s;
  renderStats(s);
  renderQueue(s);
  renderMap(s);
}

function resetUI() {
  $("#timeline").innerHTML = "";
  $("#feed").innerHTML = "";
  layers.messages.clearLayers();
  openFaults.clear();
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
        $("#clock").textContent = fmtClock(msg.elapsed);
        $("#progress-bar").style.width = `${(100 * msg.elapsed) / msg.duration}%`;
        break;
      case "reset": resetUI(); applyState({ ...state, faults: [], hazards: [], probes: [], scada_open: [], counts: { messages: 0, duplicates: 0, junk: 0, languages: {}, model_calls: {} }, truth: state.truth.map((t) => ({ ...t, found: false })), plan: {}, baseline: {} }); $("#s-hazard").textContent = "–"; $("#s-custmin").textContent = "–"; break;
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
