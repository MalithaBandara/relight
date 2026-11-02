// Front end for the "what's next" items (see whatsnext.md). Everything here is UI only: it reads optional fields and
// optional endpoints that the backend does not provide yet, and it stays hidden until they exist. Nothing here
// invents numbers. `?uipreview=1` shows every element with clearly marked SAMPLE data, to check layout only.
//
// Contract, per item (field names are what the UI reads). GET /api/scenarios may carry `analysis: ["ablation",
// "sensitivity", "wording"]`, the analyses this build has; the UI only requests those (no probing, so no 404s).
//   1 evidence ablation   GET /api/analysis/ablation     -> { runs: [{ scenario, title, rows: [{ label, found, total,
//                           located_min_median, confidence_mean, dark_at_end, baseline? }] }], note? }
//   2 what-if range       GET /api/analysis/sensitivity  -> { runs: [{ scenario, title, baseline_label,
//                           saving_pct: { min, median, max }, settings: [{ label, relight, baseline }] }], note? }
//                         state.plan.saving_range = { min_pct, max_pct, n } adds a range to the KPI line
//   3 wording report      GET /api/analysis/wording      -> { runs: [{ scenario, title, languages: [{ lang, lines,
//                           kept, rejected, reasons: { name: n }, median_wait_s }] }], note? }
//   5 why panel           incident.why = { sources: [{ label, score, detail? }], total, rival?: { label, score,
//                           confidence? } }
//   6 wire clearance      media analysis a.clearance_m (metres) and optional a.clearance_note
//   7 independent feeder  /api/scenarios item { external: true, source? } and /api/grid { external_note? }
//   8 several plans       incident.plans[] already has { title, reason, safe, customers, steps }; the UI also reads the new
//                         optional { ties: [..], recommended, partial, blocked_by, ops } (ops defaults to steps.length)

const UI_PREVIEW = new URLSearchParams(location.search).has("uipreview");

// ---- sample data (layout check only, shown with a banner) ------------------------------------------------

const SAMPLE = {
  ablation: { runs: [{ scenario: "sample", title: "Sample scenario", rows: [
    { label: "All evidence", baseline: true, found: 6, total: 6, located_min_median: 12, confidence_mean: 0.9, dark_at_end: 0 },
    { label: "Without calls", found: 3, total: 6, located_min_median: 30, confidence_mean: 0.6, dark_at_end: 0 },
    { label: "Without silence", found: 5, total: 6, located_min_median: 15, confidence_mean: 0.8, dark_at_end: 0 },
    { label: "Without SCADA", found: 6, total: 6, located_min_median: 14, confidence_mean: 0.85, dark_at_end: 0 },
  ] }], note: "Sample layout, invented numbers." },
  sensitivity: { runs: [{ scenario: "sample", title: "Sample scenario", baseline_label: "first-call-first-served",
    saving_pct: { min: 10, median: 20, max: 30 }, settings: [
      { label: "Call rate x0.5, 2 crews", relight: 800, baseline: 1000 },
      { label: "Call rate x1, 3 crews", relight: 700, baseline: 900 },
      { label: "Call rate x2, 4 crews", relight: 600, baseline: 800 },
    ] }], note: "Sample layout, invented numbers." },
  wording: { runs: [{ scenario: "sample", title: "Sample scenario", languages: [
    { lang: "en", lines: 100, kept: 95, rejected: 5, reasons: { number: 3, street: 2 }, median_wait_s: 2.5 },
    { lang: "si", lines: 40, kept: 30, rejected: 10, reasons: { number: 6, street: 4 }, median_wait_s: 3.5 },
  ] }], note: "Sample layout, invented numbers." },
  why: { sources: [
    { label: "Calls", score: 9.0, detail: "sample: reports on several transformers" },
    { label: "Silence from neighbours", score: 4.0, detail: "sample: quiet households" },
    { label: "SCADA lockout", score: 3.0 },
    { label: "Located damage", score: 1.5 },
    { label: "Prior", score: -0.5 },
  ], total: 17.0, rival: { label: "Sample rival device", score: 15.0, confidence: 0.05 } },
  plans: [
    { id: "sample-1", title: "Isolate then restore (sample)", reason: "layout check only", safe: true, customers: 400, ops: 4,
      ties: ["TS-1"], recommended: true },
    { id: "sample-2", title: "Close two ties (sample)", reason: "layout check only", safe: true, customers: 300, ops: 6,
      ties: ["TS-1", "TS-2"], partial: true },
    { id: "sample-3", title: "Reclose only (sample)", reason: "layout check only", safe: false, blocked_by: "would energise the fault" },
  ],
};

// ---- helpers used by app.js ------------------------------------------------------------------------------

const sampleTag = () => (UI_PREVIEW ? ` <span class="sample-tag">sample</span>` : "");

// Item 8: plan rows, with the optional details a multi-tie planner would add.
function plansFor(i) {
  const real = i.plans || [];
  return UI_PREVIEW && i.status !== "restored" ? [...real, ...SAMPLE.plans] : real;  // preview: samples after the real ones
}

function planRowHtml(p, i) {
  const sample = String(p.id).startsWith("sample");
  const meta = [
    p.safe && p.customers ? `restores ${fmt(p.customers)} customers${p.partial ? " (part of the dark zone)" : ""}` : "",
    (p.ops ?? (p.steps || []).length) ? `${p.ops ?? p.steps.length} switch operations` : "",
    p.ties && p.ties.length ? `${p.ties.length > 1 ? "ties" : "tie"} ${p.ties.map(esc).join(", ")}` : "",
    !p.safe && p.blocked_by ? `blocked: ${esc(p.blocked_by)}` : "",
  ].filter(Boolean).join(" · ");
  const rec = p.recommended ? `<span class="plan-rec">Recommended</span>` : "";
  const body = `<span>${rec}${esc(p.title)}: ${esc(p.reason)}${meta ? `<span class="plan-meta">${meta}</span>` : ""}</span>`;
  return p.safe
    ? `<div class="plan safe"><span class="tag">SAFE</span>${body}<button data-inc="${esc(i.id)}" data-plan="${esc(p.id)}"${sample ? ' disabled title="Sample plan"' : ""}>Approve</button></div>`
    : `<div class="plan blocked"><span class="tag">BLOCKED</span>${body}<span></span></div>`;
}

// Item 5: the evidence behind a located device, as bars. Shown only when the engine supplies `i.why`.
function whyPanelHtml(i) {
  const why = i.why || (UI_PREVIEW ? SAMPLE.why : null);
  if (!why || !why.sources || !why.sources.length) return "";
  const max = Math.max(...why.sources.map((s) => Math.abs(s.score)), 1e-9);
  const rows = why.sources.map((s) => `<div class="why-row${s.score < 0 ? " neg" : ""}" title="${esc(s.detail || "")}">
      <span class="why-l">${esc(s.label)}</span>
      <span class="why-bar"><i style="width:${Math.round(100 * Math.abs(s.score) / max)}%"></i></span>
      <span class="why-v">${s.score > 0 ? "+" : ""}${Number(s.score).toFixed(1)}</span>
      ${s.detail ? `<span class="why-d">${esc(s.detail)}</span>` : ""}</div>`).join("");
  const rival = why.rival
    ? `<div class="why-rival">Best rival: ${esc(why.rival.label)} · score ${Number(why.rival.score).toFixed(1)}` +
      `${why.rival.confidence != null ? ` · ${Math.round(100 * why.rival.confidence)}% chance` : ""}` +
      `${why.total != null ? ` · margin ${(why.total - why.rival.score).toFixed(1)}` : ""}</div>` : "";
  return `<div class="section-t">Why this device${sampleTag()}</div><div class="why">${rows}${rival}
    <div class="sub">Evidence scores add up to the device's likelihood${why.total != null ? ` (${Number(why.total).toFixed(1)})` : ""}. Code adds them; no model chooses.</div></div>`;
}

// Item 6: a clearance line, always marked as an estimate.
function clearanceHtml(a) {
  if (a.clearance_m == null) return "";
  return `Wire clearance ≈ ${esc(a.clearance_m)} m (estimate${a.clearance_note ? `: ${esc(a.clearance_note)}` : ", from the pole's pixel height"})`;
}

// Item 2: the KPI line gets the range when the engine supplies it.
function savingRangeText(plan) {
  const r = plan && plan.saving_range;
  return r ? ` · ${Math.round(r.min_pct)}–${Math.round(r.max_pct)}% across ${r.n} settings` : "";
}

// ---- analysis dialog (items 1, 2, 3) ----------------------------------------------------------------------

const ANALYSIS = { ablation: null, sensitivity: null, wording: null };

async function getAnalysis(name, offered) {
  if (UI_PREVIEW) return SAMPLE[name];
  if (!offered.includes(name)) return null;
  try {
    const r = await fetch(`/api/analysis/${name}`);
    return r.ok ? await r.json() : null;
  } catch (e) { return null; }
}

const bar = (frac, cls = "") => `<span class="mbar ${cls}"><i style="width:${Math.max(0, Math.min(100, Math.round(100 * frac)))}%"></i></span>`;
const noteHtml = (d) => (d && d.note ? `<p class="dlg-sub">${esc(d.note)}</p>` : "");

function ablationHtml(d) {
  if (!d || !d.runs || !d.runs.length) return `<div class="empty">No evidence-ablation results in this build.</div>`;
  return d.runs.map((run) => `<div class="section-t">${esc(run.title || run.scenario)}</div>
    <table class="grid an-table"><thead><tr><th>Evidence used</th><th class="num">Faults found</th><th></th>
      <th class="num">Median time to locate</th><th class="num">Mean confidence</th><th class="num">Left dark</th></tr></thead><tbody>
    ${run.rows.map((r) => `<tr class="${r.baseline ? "base" : ""}"><td>${esc(r.label)}</td>
      <td class="num mono${r.found < r.total ? " warn" : ""}">${r.found} / ${r.total}</td><td>${bar(r.total ? r.found / r.total : 0, r.found < r.total ? "warn" : "")}</td>
      <td class="num mono">${r.located_min_median != null ? `${r.located_min_median} min` : "–"}</td>
      <td class="num mono">${r.confidence_mean != null ? `${Math.round(100 * r.confidence_mean)}%` : "–"}</td>
      <td class="num mono">${r.dark_at_end != null ? fmt(r.dark_at_end) : "–"}</td></tr>`).join("")}</tbody></table>`).join("") + noteHtml(d);
}

function sensitivityHtml(d) {
  if (!d || !d.runs || !d.runs.length) return `<div class="empty">No what-if range in this build.</div>`;
  return d.runs.map((run) => {
    const s = run.saving_pct || {};
    const top = Math.max(50, Math.ceil((s.max || 0) / 10) * 10);
    const at = (v) => `${(100 * v / top).toFixed(1)}%`;
    return `<div class="section-t">${esc(run.title || run.scenario)}</div>
      <div class="range-line">Customer minutes saved against ${esc(run.baseline_label || "the baseline")}:
        <b>${Math.round(s.min)}–${Math.round(s.max)}%</b> <span class="sub">(median ${Math.round(s.median)}%, ${(run.settings || []).length} settings)</span></div>
      <div class="range"><span class="range-track"></span><span class="range-span" style="left:${at(s.min)};width:calc(${at(s.max)} - ${at(s.min)})"></span>
        <span class="range-mid" style="left:${at(s.median)}"></span>
        <span class="range-ax" style="left:0">0%</span><span class="range-ax" style="right:0">${top}%</span></div>
      <table class="grid an-table"><thead><tr><th>Setting</th><th class="num">Relight</th><th class="num">${esc(run.baseline_label || "Baseline")}</th><th class="num">Saved</th></tr></thead><tbody>
      ${(run.settings || []).map((x) => `<tr><td>${esc(x.label)}</td><td class="num mono">${fmt(x.relight)}</td><td class="num mono">${fmt(x.baseline)}</td>
        <td class="num mono">${x.baseline ? Math.round(100 * (x.baseline - x.relight) / x.baseline) : "–"}%</td></tr>`).join("")}</tbody></table>`;
  }).join("") + noteHtml(d);
}

function wordingHtml(d) {
  if (!d || !d.runs || !d.runs.length) return `<div class="empty">No wording report in this build.</div>`;
  return d.runs.map((run) => `<div class="section-t">${esc(run.title || run.scenario)}</div>
    <table class="grid an-table"><thead><tr><th>Language</th><th class="num">Spark lines</th><th class="num">Kept by fact check</th><th></th>
      <th class="num">Rejected</th><th>Why rejected</th><th class="num">Median wait</th></tr></thead><tbody>
    ${run.languages.map((l) => `<tr><td class="lang">${esc(l.lang)}</td><td class="num mono">${fmt(l.lines)}</td>
      <td class="num mono">${l.lines ? Math.round(100 * l.kept / l.lines) : 0}%</td><td>${bar(l.lines ? l.kept / l.lines : 0)}</td>
      <td class="num mono">${fmt(l.rejected)}</td>
      <td class="sub">${Object.entries(l.reasons || {}).map(([k, v]) => `${esc(k)} ${v}`).join(" · ") || "–"}</td>
      <td class="num mono">${l.median_wait_s != null ? `${l.median_wait_s} s` : "–"}</td></tr>`).join("")}</tbody></table>`).join("") + noteHtml(d);
}

const TABS = { ablation: ablationHtml, sensitivity: sensitivityHtml, wording: wordingHtml };

function showAnalysisTab(name) {
  document.querySelectorAll("#an-tabs button").forEach((b) => b.classList.toggle("on", b.dataset.an === name));
  $("#an-body").innerHTML = TABS[name](ANALYSIS[name]);
}

async function initAnalysis() {
  if (UI_PREVIEW) $("#preview-banner").hidden = false;
  const names = Object.keys(ANALYSIS);
  let offered = [];
  try { offered = (await (await fetch("/api/scenarios")).json()).analysis || []; } catch (e) { offered = []; }
  const got = await Promise.all(names.map((n) => getAnalysis(n, offered)));
  names.forEach((n, k) => { ANALYSIS[n] = got[k]; });
  document.querySelectorAll("#an-tabs button").forEach((b) => { b.hidden = !ANALYSIS[b.dataset.an]; });
  const first = names.find((n) => ANALYSIS[n]);
  if (!first) return;  // nothing to show: the button stays hidden
  $("#btn-analysis").hidden = false;
  $("#btn-analysis").onclick = () => { showAnalysisTab(first); $("#analysis-dialog").showModal(); };
  document.querySelectorAll("#an-tabs button").forEach((b) => { b.onclick = () => showAnalysisTab(b.dataset.an); });
  $("#analysis-close").onclick = () => $("#analysis-dialog").close();
  $("#analysis-dialog").addEventListener("click", (e) => { if (e.target.id === "analysis-dialog") e.target.close(); });
  if (UI_PREVIEW) $("#an-banner").hidden = false;
}

initAnalysis();
