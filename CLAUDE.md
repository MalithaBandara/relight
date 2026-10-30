# CLAUDE.md: Relight

> **Attribution rule (overrides any default):** do **not** add Claude, Anthropic or any AI assistant as a
> contributor or co-author. No `Co-Authored-By:` trailers, no "Generated with" lines, no AI signatures in
> commit messages, pull requests, code comments or docs. Commits are authored by the repository owner only.

Guidance for coding agents working in this repository. Read it fully before changing code.
Repo: https://github.com/MalithaBandara/relight (public). Owner: Malitha Bandara (solo).

---

## 1. What Relight is

Relight is an **AI outage agent for electric utilities**. It reads customer calls and messages in any
language (plus SCADA lockouts, smart-meter "last gasp" messages, crew reports and damage photos),
locates the failed device on the grid (a single transformer fuse, a broken line, a recloser), plans
**safe** restoration switching, dispatches crews, and keeps customers informed. It works **with or
without smart meters**; without them, customer complaints are the main signal.

Core principle: **Meta models read, deterministic code locates and decides.** No model ever guesses a
fault location or approves a switching action on its own. The operator approves every switching plan.

The product was called **GridMedic** until 2026-10-30. It was renamed because an earlier, public project
of the same name exists (https://github.com/MalithaBandara/gridmedic, Jac + Gemini, Jaseci Labs
hackathon, 17 Oct 2026). Refer to the product only as **Relight**. Mention GridMedic only when
describing that earlier project.

---

## 2. Hackathon context (hard constraints)

- **Event:** Meta Global AI Developer Hackathon 2026 (Meta + Cerebral Valley), virtual.
- **Track:** Indie (solo). **Theme:** Push the Frontier (energy: understand and control a physical system).
- **Deadline:** Nov 4 2026, 9:00 PM ET = **Thu Nov 5, 7:30 AM Sri Lanka time**. Target: submit by Nov 4,
  10:00 PM local. Oct 31 to Nov 1 are off (IEEEXtreme). Nov 3 is reserved for recording the demo video.
- **New work only.** Everything shown must be built during the event (from Oct 26; this repo starts
  Oct 29). **Never copy code from the old GridMedic repo or any pre-event code.** Ideas may be reused;
  the README discloses the earlier project and lists what is different.
- **Must use Meta's models:** Muse Spark, Muse Voice Transcribe, SAM 3.1 (Meta Model API), Muse Glimmer
  (open weights). Muse Image, Muse Wonder and Muse Code are allowed but unused.
- **Judging:** Impact 30%, Use of Meta AI tooling 25%, Technical depth 20%, Demo 25%. Top 5 per track are
  ranked from the demo video.
- **Data:** only synthetic or public data. Use the Meta API in **Standard** mode (not Contributor).
- **Honesty rules for anything shown:** say on screen that customers are fictional; never use real
  utility names in customer-facing text (templates say "Outage desk", not a utility's name); real
  facilities from OpenStreetMap appear only under generic names ("Hospital on <street>"); never claim
  how a specific real utility operates; label mock output as mock.
- **Budget:** $150 Meta API credit. Partner credits (Baseten, Modal, Fireworks; $100 each) were applied
  for and cover **open-weights models only**. Never print, log or commit API keys.

---

## 3. Quick start

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # Windows; .venv/bin/pip elsewhere
cp .env.example .env                               # add MODEL_API_KEY for live Meta models
.venv/Scripts/python -m uvicorn relight.server:app --port 8000
```

- Control-room console: http://localhost:8000 (pick a scenario in the header, press **Run**).
- Customer portal: http://localhost:8000/customer
- In the Claude desktop app, start the server with the preview tool using the `relight` entry in
  `.claude/launch.json` (there is **no `--reload`**: restart the server after every Python change).

Environment variables (`.env`, see `.env.example`): `MODEL_API_KEY`, `META_API_BASE`
(`https://api.meta.ai/v1`), `SPARK_MODEL` (`muse-spark-1.3`), `TRANSCRIBE_MODEL`
(`muse-voice-transcribe-1.0`), `SAM_MODEL` (`sam-3.1`), `GLIMMER_BASE`, `GLIMMER_MODEL`, optional
`MODEL_MODE` (`live` / `mock`; defaults to `live` when a key is present).

---

## 4. Repository map

```
relight/                 Python package (FastAPI backend and all logic)
  config.py              paths and env settings; MODEL_MODE
  grid.py                Feeder: generic radial network built from a spec; IEEE 34-bus spec for Galle;
                         SECTIONS / DEVICES / SWITCHES constants; geometry helpers (haversine, bearing)
  osmnet.py              builds a feeder spec and customer DB from cached OpenStreetMap roads/buildings
  customers.py           SQLite customer DB (accounts, phones, addresses, transformer); Galle builder;
                         CustomerDB lookups (account, phone, fuzzy address, landmark)
  packs.py               scenario packs: network + customer DB + locale per scenario (cached)
  locales.py             per-country names, number formats, SMS code regex, message templates
                         (Sri Lanka, US, India)
  models.py              Meta Model API client (Spark chat/JSON schema, Voice Transcribe, SAM 3.1
                         segmentation) with on-disk response cache; SAM token parser
  extract.py             Spark prompts and JSON schemas for complaints and crew reports; mock fallbacks
                         (scenario labels, or keyword parser for unlabelled portal messages)
  vision.py              damage photos: Spark classifies, SAM outlines pole/wire, wire clearance in metres
  tracer.py              probabilistic fault tracer (candidates, likelihood, greedy search, confidence)
  network.py             power flow over buses/section bodies; switching plans and safety check
  planner.py             priority scoring, crew work steps, what-if schedule vs first-call baseline
  engine.py              the triage loop: evidence, incidents, crews, switching, notices, portal status
  callagent.py           AI call agent: answers every call in the caller's language from engine state
  voice.py               text to speech (edge-tts) with a phone-line filter; cached in media/audio/tts/
  scenario.py            scenario loader, simulated physical World, Replayer (clock, time-lapse)
  diagram.py             paper single-line diagram -> topology with Spark; scoring; diagram renderer
  server.py              FastAPI app, REST endpoints, WebSocket broadcast, scenario switching
scenarios/               galle_storm.json (hand-written), houston_hurricane.json and
                         chennai_cyclone.json (generated by scripts/make_storm.py)
scripts/
  run_headless.py        replay a scenario to completion, print incidents and ground-truth check (--calls)
  make_calls.py          synthesise the voiced callers in scenarios/calls/*.json -> media/audio/calls/
  make_storm.py          generate storms on OSM feeders (fault placement rules, complaints, meters)
  fetch_osm.py           download roads/buildings/landmarks from Overpass into data/osm/
  smoke_test.py          one small live call per Meta model (needs MODEL_API_KEY)
  eval_extraction.py     per-language extraction accuracy vs scenario labels (Spark or --glimmer)
web/                     index.html + app.js + style.css (console), customer.html (portal)
data/osm/*.json          cached OpenStreetMap extracts (committed; ODbL attribution in README)
data/*.db                generated customer databases (git-ignored; rebuilt on first use)
scenarios/calls/         per-scenario voiced calls (overlay on complaint ids: spoken words, withheld facts, voice)
media/diagrams/          rendered paper diagram; photos/drone go in media/ when added
media/audio/calls/       synthetic caller recordings (committed); media/audio/tts/ is a git-ignored cache
.cache/model/            cached model responses (git-ignored)
PROJECT_BRIEF.md         original plan, research, judging notes and ideas (historical; keep)
```

---

## 5. Architecture and data flow

```
scenario JSON --> Replayer (clock) --> Engine.handle(event)
                       ^                    |
                       | World (truth)      |-- complaint: transcribe? -> Spark extract -> locate -> claim/dedup
                       |  answers probes,   |-- scada lockout, ami last gasps, ami_status
                       |  crew site reports,|-- crew_note (patrol or dispatched crew) -> confirm / change diagnosis
                       |  follow-up calls   |-- drone / photo -> damage evidence
                       |                    v
                       |           recompute(): rebuild Evidence from unclaimed messages
                       |             -> Tracer.locate() -> suspects / new incidents (conf >= 0.8)
                       |             -> priority, switching plans, dispatch, explanations, notices
                       |                    |
                       +--- sim callbacks <-+--> broadcast over WebSocket -> web console
```

- **Engine** (`relight/engine.py`) is the single source of operational state. It never reads scenario
  truth; it only sees messages, SCADA, meters and crew reports.
- **World** (`relight/scenario.py`) is the simulated physical truth: faulted sections, blown fuses,
  dead service wires, real device states. It plays customers (probe answers, follow-up complaints),
  crews (site reports on arrival) and applies repairs and switching.
- `engine.sim` is the Replayer; callbacks: `probe()`, `crew_arrived()`, `switched()`, `repaired()`,
  `restored()`, `identify()` (scoring only).

### 5.1 Network model (`grid.py`, `network.py`)
- A **Feeder** is built from a spec: `root` bus, `buses`, `sections` (polylines with street names),
  `devices` (breaker / recloser / fuse; one per section head at most), `switches` (sectionalising
  switches on sections, a normally-open tie `TS-1` to a `feeder2` bus). Service transformers are placed
  along sections every `transformer_spacing` metres; every transformer has its own `XF-nnn` fuse.
- **Power flow** walks a graph of `("bus", id)` and `("sec", id)` nodes. A section body joins its
  upstream bus through the devices at its head and its downstream bus directly, so power can back-feed
  up a section when the tie closes. Faulted bodies are blocked. The graph is cached per feeder
  (`feeder.__dict__["_graph"]`); this cache is why Chennai runs fast.
- **NetworkState** (`open`, `faulted`, `dead_transformers`, `dead_customers`, `suspect`) is used for
  both the World's truth and the Engine's **belief** (`Engine.belief()`).

### 5.2 Fault tracer (`tracer.py`)
- Candidates: every protective device, every transformer fuse, and a `LINE-<section>` "unprotected
  break" per section. Candidates that would darken **exactly the same transformers** are merged (device
  preferred over line; zones united), because complaints cannot tell them apart; the crew decides.
- Score of a hypothesis (set of candidates) = sum over transformers of log-likelihood gain
  (reports with call probability `q(t)` vs false-report rate `EPS`; silence counted per
  `HOUSEHOLDS_PER_SIGNAL` customers because neighbours behave alike) + probe answers + smart meters
  (`METER_Q`, `METER_EPS`; silent meters count only while the meter network is up and traffic has
  settled for 60 s) + priors (`PRIORS`) + partial-power bonus for lines + SCADA consistency + located
  damage inside a candidate's protection zone (`DAMAGE_COMPAT`).
- Search: greedy forward selection with a backward pruning pass after each addition. Confidence =
  share of probability against alternatives that overlap the chosen candidate; the best rival drives the
  agent's question.

### 5.3 Incidents (`engine.py`)
- A suspect becomes an **incident** at confidence >= `LOCATED_AT` (0.8). If it overlaps an open
  incident by half or more, it **merges** into it instead (`_merge_into`, may widen the device).
- An incident **claims** its evidence (complaints on its transformers, its SCADA lockout, damage in its
  zone). The tracer only sees **unclaimed** evidence, so complaints after a restoration find hidden
  second faults.
- Fields worth knowing: `cand`, `kind` (`pole_down`, `tree_on_line`, `live_wire`, `wire_down`,
  `blown_fuse`, `service_wire`, `unknown`), `site_section`, `site_xf`, `dead_customers`, `out`
  (believed dark transformers, recomputed by `_refresh_outages`), `steps` (crew work), `plans`,
  `history` (diagnosis changes), `status` (`located` -> `dispatched` -> `on site` -> `restored`),
  `mind_changed`, `after_restore`, `switching` (operations applied).
- **Diagnosis change:** a crew report with `device_ok` or a different damage type revises the incident
  (`_site_findings`), replans steps (`_replan_steps`) and releases a crew that lacks the skills.
- **Patrol finds nothing:** if the device is still locked out, the patrol is extended (max 3); if the
  incident is closed while customers are still dark, the World makes them call back.

### 5.4 Crews and restoration
- `planner.STEPS` defines sequential work per kind (e.g. live wire: make safe with any crew, then line
  repair; tree: vegetation then line). `_dispatch` sends the nearest idle crew with the right skills to
  the next pending step of the highest-priority incident. `advance(until)` processes arrivals and
  finished work in time order and accumulates customer minutes interrupted (`cmi`).
- `_complete`: undo switching (tie switches first, never parallel feeders), close the incident's
  device, recompute live transformers, send "power restored" notices, tell the World (follow-ups).

### 5.5 Switching safety (`network.restoration_plans`, `check_plan`)
- Offered per incident with a known faulted section: reclose the device, close the tie, and
  "isolate then restore" (open the nearest switch above and below the fault, close the device, close
  the tie). Each plan is simulated step by step against the **belief**; it is **blocked** if a step newly
  energises a believed-faulted section, a zone whose fault is not pinned down yet (`suspect`), or a
  section where a crew is on site. Only plans that restore this incident's customers (or blocked
  shortcuts that would hit its fault) are shown. The operator approves via `POST /api/plan`.
- **Never** let code auto-apply plans in the live server. Only `scripts/run_headless.py` auto-approves,
  to exercise the path.

### 5.6 Messages and models
- Complaint path: `_transcript` (Voice Transcribe if `audio` exists) -> `_extract` (SMS code regex
  first: `BD`/`OUT`/`PWR <10-digit account>` needs no model; else Spark, or Glimmer when offline) ->
  `_locate` (account, address, caller ID, landmark, street) -> `_claim` -> `_apply` (dedup by account
  or sender; hazards; evidence).
- Mock mode: if a model call is not cached (or there is no key), extractors return the scenario's
  `truth` labels, labelled `mock (ground truth)`; unlabelled portal text uses `_keyword_fields`
  (`mock (keywords)`). Explanations and notices fall back to templates (`mock (template)`).
- Every model response is cached in `.cache/model/` keyed by a request hash: replays are free and
  deterministic. Changing a prompt changes the key.
- Offline mode (`set_offline`): text goes to Glimmer (`GLIMMER_BASE`, checked once for reachability),
  calls queue; on reconnect Spark reviews Glimmer's extractions and evidence is rebuilt.

### 5.6a Call agent (`callagent.py`)
- Every `channel: "call"` complaint (except answers to the agent's own questions) is answered by the agent.
  Phase 1, inside `_complaint` before the report is filed: greet, hear the caller, then confirm the address
  (located by caller ID), ask for it (not located), and either warn about a hazard already reported nearby
  (`known_hazard`, from earlier calls) or ask about hazards. What the caller adds is appended to the
  transcript and extracted again. Phase 2, in `_finish_calls` after the re-trace: repeat-caller notice,
  fixed safety line, escalation (live wire, fire, critical customer -> `Agent` log alarm), a question
  about next door if the tracer is torn between two candidates that differ within 400 m (answer becomes a
  probe reply, then re-trace), then the status (incident + crew state + ETR, restored-but-still-dark,
  or locating) and close. While calls are in progress the tracer's SMS question waits, so callers are asked
  first.
- Code chooses the act and its facts; **Muse Spark words every non-fixed line** in the caller's language
  (`CallAgent.say` -> `_spark`, `SPEAK_SYSTEM`). `facts_kept` rejects a Spark line that drops or changes any
  number, time, street name or id from the template (turn model `Code (Spark line failed fact check)`,
  `rejected` lists what was missing); then the template is spoken. No key / offline -> template
  (`mock (template)`). `FIXED` acts (greeting with the automated-assistant disclosure, safety lines,
  known-hazard warning, escalation, SMS fallback, close) are never sent to Spark. During a surge
  (`quiet_messages`) only voiced calls use Spark. Templates live in `locales.py` (`agent`, `caller`,
  `HAZARD_NAMES`, `READBACK`, `SITE_REPORTS`, `voices`). Simulated callers answer via `Replayer.answer` /
  `neighbour` from the truth labels.
- Voiced calls: `scenarios/calls/<scenario>.json` maps complaint ids to `spoken` (opening words),
  optional `withheld` (facts given only when asked; mock extraction hides them from the labels), `voice`,
  `rate`, `from` (unknown number). `scenario._voice_calls` applies it at load and sets `audio`.
  Regenerate audio with `scripts/make_calls.py [--force]`.
- Sinhala audio: Voice Transcribe has no Sinhala, so `_transcript` asks Spark to listen
  (`ModelClient.spark_listen`, request shape unverified). If a live model cannot read the call, the agent
  asks for the breakdown SMS and the World sends it (`sms_fallback`).
- Agent speech is synthesised on demand by `GET /api/call/{id}/{turn}.wav` (edge-tts, cached). Meta has
  no text-to-speech model; the voice is Microsoft's, everything that decides is Meta models + code.
- Crew reports are calls too (`_crew_note`): the crew's report is transcribed and extracted, the agent
  reads it back (`crew_summary`, act `readback`), the World confirms or says "Negative. Again: ..." when
  the extracted damage / device_ok / house range differ from the truth (then one re-extraction), and only
  then `_site_findings` runs; the agent acknowledges (`crew_changed` / `crew_logged` / `crew_unmatched`).
  Each crew reports in its own language, set per crew id in the calls overlay (`"crews": {"CREW-T1":
  {"language": "si"}}`): Galle T1/V1 Sinhala, T2 Tamil, line crews English; Houston T2/L2/V1 Spanish;
  Chennai Tamil and Hindi gangs, T1 English. Only the first crew on site files a report, so the
  troubleshooters' languages are the ones heard. The World writes site reports from `SITE_REPORTS[lang]`;
  the read-back is built from `READBACK[lang]` and worded by Spark. Sinhala crew audio goes to
  `spark_listen`; if no model can read a crew's call, the agent asks for a text report (`crew_text`).
  In live mode the World's text site reports are synthesised first so Voice Transcribe hears a real voice;
  Galle's patrol notes N1-N4 have recorded audio (calls overlay).
- Spark's English `summary_en` is shown under a caller's or crew's first words (`CallAgent.gloss`, live).

### 5.7 Scenario packs and locales
- A scenario's `pack` block: `locale` (`sri_lanka` / `us` / `india`), `network` (`{"type": "ieee34"}` or
  `{"type": "osm", "area": ..., transformer_spacing, reclosers, ...}`), `languages`, `start_hour`,
  optional `smart_meters` (`coverage`, `delay_s`, `network_fail_t`), `quiet_messages`, `retrace_s`.
- `packs.network(sc)` builds and caches `(Feeder, CustomerDB)` per area. OSM customer DBs live in
  `data/<area>.db`; Galle's in `data/galle.db`. **Delete the `.db` file after changing network or
  customer-generation settings**, or lookups will not match the feeder.
- High-volume scenarios (`retrace_s` > 0) re-trace at most every N seconds of storm time and summarise
  per-message log lines ("Processed N messages").

---

## 6. The three scenarios and the regression baseline

| Scenario | Network | Customers | Messages | Faults | Shows |
|---|---|---|---|---|---|
| `galle_storm` | IEEE 34-bus over Galle (hand-tuned) | 1,951 | ~69 | 6 | full story: Sinhala/Tamil/English, BD SMS, probe question, Lake Road diagnosis change, Temple Road isolate-and-tie switching, hidden fuse after restoration |
| `houston_hurricane` | OSM, Spring Branch, Houston | 3,044 | ~221 | 7 | smart meters until the meter network fails at t=600 s; English/Spanish; hidden fault; service-wire twist |
| `chennai_cyclone` | OSM, Velachery, Chennai | 24,559 | ~2,400 | 9 | scale; English/Tamil/Hindi; PWR SMS codes; quiet logging; re-trace every 15 s |

**Before every commit that touches `relight/` or `scenarios/`, run all three and check every real fault
is found and everyone is restored:**

```bash
.venv/Scripts/python scripts/run_headless.py galle_storm
.venv/Scripts/python scripts/run_headless.py houston_hurricane
.venv/Scripts/python scripts/run_headless.py chennai_cyclone
```

Expected: Galle 6/6 `found=True`, Houston 7/7, Chennai 9/9, and the last line
`Still dark at the end: 0 customers (believed); world says 0`. Chennai takes about 15 s; if it takes
minutes, something reintroduced per-call graph rebuilding or per-event re-tracing.
Use `--timeline` to see the full event log; `--no-switching` to skip auto-approval.

Regenerating generated scenarios (deterministic seeds):
```bash
.venv/Scripts/python scripts/make_storm.py houston_hurricane chennai_cyclone
```
`make_storm.py` keeps separate faults apart (no overlapping dark areas unless `hidden`), requires
customers behind each fault, puts the switch-zone tree on the main run between `SW-1` and `SW-2` inside
the first recloser's own zone, and guarantees at least two callers for small faults.

---

## 7. Server API

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | console (`web/index.html`) |
| GET | `/customer` | customer portal |
| GET | `/api/grid` | feeder GeoJSON, landmarks, crews, customers per transformer, scenario metadata |
| GET | `/api/state` | full engine snapshot |
| GET | `/api/scenarios` | list scenarios; current one |
| POST | `/api/scenario` | `{"id": ...}` switch scenario (stops replay, rebuilds engine; clients reload) |
| POST | `/api/control` | `{"action": start|pause|reset|speed|offline|online, "speed": n}` |
| POST | `/api/plan` | `{"incident": "I2", "plan": "isolate"}` operator approves a switching plan |
| GET | `/api/customer?q=` | portal status by account or phone |
| POST | `/api/customer/report` | `{"text", "who", "language"}` live complaint (processed like any other) |
| GET | `/api/call/{id}/{turn}.wav` | one line of an agent call: caller recording or synthesised speech |
| POST | `/api/diagram` | digitise the paper diagram (optional image upload) and score it |
| WS | `/ws` | snapshot on connect, then `state`, `timeline`, `message`, `probe`, `notice`, `photo`, `drone`, `scada`, `clock`, `reset`, `scenario`, `messages`, `network` |

All writes to the engine go through one `asyncio.Lock` in `server.py` (replay, operator, portal).

---

## 8. Meta Model API facts (from Meta's docs; nothing has been called live yet)

- Base URL `https://api.meta.ai/v1`, header `Authorization: Bearer $MODEL_API_KEY`, OpenAI-compatible.
- **Muse Spark** (`muse-spark-1.3`): `POST /chat/completions`, `response_format: {"type": "json_schema", ...}`;
  accepts text, image, video, audio, PDF; Spark always reasons. Pricing ~$1.25 / M input, $4.25 / M output.
- **Voice Transcribe** (`muse-voice-transcribe-1.0`): `POST /asr/transcribe?sessionId=...`, multipart
  `request` (JSON: mode, model, audioEncoding, optional `languageBias` list) + `audio` (WAV). 25 languages
  including Tamil, Hindi, Spanish, English, with code-switching. **Not Sinhala** (checked 2026-10-30; some
  third-party articles claim 70+ languages, Meta's page lists 25). Realtime WebSocket:
  `wss://api.meta.ai/v1/asr/realtime`. Speaker diarization: `mode: "DIARIZATION"` (file response has
  `turns[]` with `speaker`; realtime sends `speaker` events). Pricing **$0.18 per hour** of audio, streaming
  or not, billed per whole second; failed and 429 requests are not billed.
- **No text-to-speech or speech-to-speech model** exists on the Meta Model API (checked 2026-10-30).
- **SAM 3.1** (`sam-3.1`): `POST /responses` with `input_text` (short noun phrase) + `input_image`
  (URL or base64 data URL) or `input_video`. Output is special-token text:
  `<|box;x1=..;y1=..;x2=..;y2=..;w=..;h=..;c=..|><|mask;x=0;y=0;data=H,W,<enc>payload|>`, video lines
  prefixed `<Nf>`. Boxes are in source pixels; mask payload is base85 (not decoded yet; only boxes are
  used). `metadata.include_confidence: "true"` adds `c=`.
- **Muse Glimmer**: open weights, ~30B dense (plus ~1.8B vision encoder), text + image in; BF16 ~60 GB,
  Meta's quantised build under 20 GB. Not on the session laptop; the owner's RTX 5070 Ti (16 GB) needs a
  ~3-bit GGUF fully on GPU via llama.cpp `llama-server`, or a hosted endpoint (partner credits).
  Positioned as an optional on-premise mode, not a headline feature.
- Re-check docs at https://dev.meta.ai/docs/ before relying on any field above.

---

## 9. Conventions

- **Python 3.12**, standard library + FastAPI/uvicorn/httpx/python-dotenv/Pillow, plus edge-tts (optional:
  the call agent's voice; needs ffmpeg on PATH). Keep dependencies minimal; pin new ones in
  `requirements.txt`.
- Style matches the existing code: type hints, `from __future__ import annotations`, module docstrings
  that explain *why*, short comments only where the reason is not obvious, 120-character lines.
- Keep logic deterministic and explainable. Models produce structured evidence; code decides. Every
  timeline entry is tagged with the model or `Code` / `Agent` / `Crew` / `Operator` / `SCADA` /
  `Smart meters` that produced it; preserve that tagging (the UI and the "AI usage" counter rely on it).
- Model calls go through `ModelClient` (caching, mock fallback). Wrap calls so a failure degrades to mock
  instead of crashing a storm (`Extractor._call` pattern).
- Front end: plain HTML/CSS/JS, Leaflet 1.9.4 from unpkg, no build step. Console styling follows
  high-performance HMI practice (muted greys; colour only for event states and alarms); keep it that
  way. Re-render tables only when their HTML changes, and use delegated `pointerdown` handlers for
  buttons inside re-rendered panes (the storm re-renders often).
- Map data: OSM tiles are darkened in CSS; cite "(c) OpenStreetMap contributors" (ODbL).
- User-facing text: plain language, no hype. Non-English templates (Sinhala, Tamil, Hindi, Spanish)
  should be checked by native speakers before the video.

---

## 10. Environment gotchas (Windows)

- Shells: Git Bash and PowerShell 5.1. Large inline Python in a Bash heredoc has failed with quoting
  errors; write helper scripts to a file (scratchpad) and run them instead.
- The preview server keeps `data/*.db` open: stop it before deleting databases.
- `uvicorn` runs without `--reload`; restart after Python edits (front-end files are served fresh).
- Use `PYTHONIOENCODING=utf-8` when printing Sinhala/Tamil to the console.
- Kill long runs with the task-stop tool, not `taskkill`.

---

## 11. Git

- Branch: `main`, remote `origin` = `MalithaBandara/relight`. Commit only when the owner asks.
- Commit messages: imperative subject, body explaining what and why. **No co-author trailers or AI
  attribution of any kind** (see the rule at the top).
- Never commit `.env`, `.cache/`, `data/*.db`, `.venv/`. `data/osm/*.json` and
  `media/diagrams/feeder1_sld.png` are committed on purpose.

---

## 12. Status and open work (as of 2026-10-30)

Done (mock mode, verified headless and in the browser):
- multilingual complaint pipeline, dedup, junk, SMS codes, landmarks
- probabilistic tracer with agent questions; incidents with claim/merge; hidden faults after restoration
- crew lifecycle, diagnosis change from site reports, patrol extension, call-backs
- safety-checked restoration switching with operator approval; customer minutes interrupted
- smart meters with meter-network failure (Houston); scale (Chennai, ~2,400 messages in ~15 s)
- OMS-style console (work agenda, event details, event log, trouble calls, outbound, crews);
  customer portal; paper-diagram digitisation (scored, not yet wired into the engine)
- AI call agent (2026-10-30, owner's choice): answers every call in en/si/ta/es/hi with context from engine
  state, safety lines, escalation, next-door questions; 18 synthetic voiced calls across the three
  scenarios; "Agent calls" console tab with per-line and whole-call playback. Mock mode only so far.
- Crew reports by voice with read-back before acting (all crew reports; Galle patrol notes recorded);
  crews in Sinhala, Tamil, Hindi, Spanish and English; Spark words every non-safety agent line with a
  fact check (mock: templates). Untested live parts are listed in 12.3.

### 12.1 Who does what

**Agents must never** sign in to any account, create or handle API keys or tokens, submit forms, accept
terms, apply for credits, create hosted endpoints, or submit the hackathon entry on the owner's behalf.
Agents also must not pick which optional features to build: the owner decides (ask, then build).
If a task below is owner-only, say what is needed and stop; do not work around it.

#### Owner only (agents cannot do these)

Accounts, keys and forms
- [ ] Get the **Meta Model API key** and put it in `.env` as `MODEL_API_KEY=...` (never paste it in chat).
- [ ] Submit the **partner credit forms** (Baseten, Modal, Fireworks); answers are drafted.
- [ ] If credits arrive: **create the hosted Glimmer endpoint** in the partner dashboard and put its URL /
      key in `.env` (`GLIMMER_BASE`, `GLIMMER_MODEL`).
- [ ] **Submit on Cerebral Valley** by Nov 4, 10:00 PM Sri Lanka time (hard deadline Nov 5, 7:30 AM).

Media
- [x] ~~Record calls~~: the owner cannot record; calls are synthetic voices (edge-tts), labelled as such.
- [ ] **Listen to the voiced calls** in the console and say which voices or lines sound wrong.
- [ ] **Choose and download** damage photos and one drone clip; **confirm their licences**.
- [ ] If pole-tag reading is chosen: photograph a pole with a visible ID tag.
- [ ] If realistic paper-to-grid is chosen: draw a pole-numbered feeder sketch and write one meter-reader
      ledger page, then photograph both.

Checks and decisions
- [ ] **Native-speaker check** of Sinhala, Tamil, Hindi and Spanish messages and templates.
- [ ] **Decide which optional features to build** (shortlist in 12.2).

Video
- [ ] **Record the screen and the voice-over, and edit** to 2–3 minutes (Nov 3), from the agent's shot list
      and script.

#### Agent tasks

Blocked until the owner provides something
- [ ] *(needs `MODEL_API_KEY`)* Run `scripts/smoke_test.py`; fix request-format mismatches with the real API.
- [ ] *(needs `MODEL_API_KEY`)* Run all three scenarios live; keep the regression baseline (section 6) green.
- [ ] *(needs `MODEL_API_KEY`)* Run `scripts/eval_extraction.py`; put per-language accuracy in the README.
- [ ] *(needs `MODEL_API_KEY`)* Keep a running cost estimate under $150 (Voice Transcribe is $0.18/h).
- [ ] *(needs `MODEL_API_KEY`)* Run the voiced calls live: Voice Transcribe on en/ta/es/hi, Spark listening
      to the Sinhala call (`spark_listen` request shape), Spark rewording status lines; fix what breaks.
- [ ] *(needs photos)* Run the photo path live; finish SAM 3.1 mask decoding for wire clearance.
- [ ] *(needs a drone clip)* Drone damage assessment with SAM 3.1 video tracking.
- [x] Wire `audio` paths into the scenarios (done with synthetic calls; live test is the task above).
- [ ] *(needs the Glimmer endpoint)* Point `GLIMMER_BASE` at it and run the eval once with `--glimmer`.
- [ ] *(needs the owner's feature choice)* Build the chosen optional features (12.2).

Can start now
- [x] Call scripts in every language and the `media/audio/calls/` layout (scenarios/calls/*.json).
- [x] Crew voice reports with read-back (synthetic audio; same pipeline as calls).
- [ ] Find candidate public photo datasets and drone clips with their licences, for the owner to choose.
- [ ] Customer portal sample buttons for the Houston and Chennai scenarios (currently Galle only).
- [ ] Polish the console for recording (demo flow, click path, timing).
- [ ] Shot list, voice-over script and on-screen captions for the video.
- [ ] README: architecture diagram, "which Meta model does what", screenshots; accuracy table once
      measured.
- [ ] Submission description text and the final pre-submission checklist (links, public repo, theme
      "Push the Frontier").

### 12.2 Optional features (owner chooses; agent builds)

- **Pole-tag reading** from customer photos (SAM finds the plate, Spark reads the ID) → exact asset.
- **AI call agent** (chosen and built, see 5.6a). Possible next step: realtime mode over the Voice
  Transcribe WebSocket with diarization, so a call is handled turn by turn as it is spoken.
- **Live call copilot:** realtime Voice Transcribe + live field filling + Spark's suggested next question,
  for a human call-taker on the hard calls the agent escalates.
- **Drone damage assessment:** SAM 3.1 video tracking of poles and conductors; sag and broken-pole counts.
- **Realistic paper-to-grid:** hand-drawn pole-numbered sketch + meter-reader ledger → network and
  consumer index the engine runs on, with SAM symbol overlay and a review screen for flagged items.
- **Glimmer on-premise mode** through a hosted endpoint (no cascade work unless the owner asks).

### 12.3 Built but untested (verify once the API key is in)

Owner's rule (2026-10-30): build every feature in its intended form even when it cannot be tested yet, with a
mock/template fallback, and list it here. Tick items off (or fix them) after live testing; add new ones.

Call agent and crew calls
- [ ] Spark wording of agent lines (`SPEAK_SYSTEM`): naturalness per language, how often `facts_kept`
      rejects lines (Spark may write digits in local script or transliterate street names), latency per line.
- [ ] `spark_listen` (Sinhala calls and Sinhala crews): request shape (`input_audio` content part) and
      transcript quality; the SMS fallback (`not_understood`) and crew text fallback (`crew_by_text`).
- [ ] Voice Transcribe on the synthetic 8 kHz phone WAVs (en/ta/es/hi): `languageBias` value format,
      `ENDPOINTING` response field `transcript`, accuracy vs the scripted text.
- [ ] Spark extraction of non-English and code-mixed crew reports (crew schema), and of a caller's
      opening plus answers after the agent's questions (re-extraction).
- [ ] Read-back correction path with real Spark misreads (only tested with a stand-in reading).
- [ ] Live synthesis of the World's site reports before transcription (edge-tts latency in the loop).
- [ ] Neighbour question: Spark reading the caller's yes/no about next door as a probe answer.
- [ ] Voices: pronunciation of street names and numbers by each edge-tts voice; native-speaker check of
      every new Sinhala / Tamil / Spanish / Hindi line (agent, callers, crews, read-back words).

### 12.4 Order that saves the most time

1. Owner: API key into `.env`; submit credit forms.
2. Agent: live run and fixes; meanwhile the owner records audio from the scripts and picks media.
3. Owner chooses optional features; agent builds them.
4. Nov 3: agent prepares the shot list and script; owner records and edits.
5. Nov 4: agent finalises README and checks; owner submits.

When in doubt about scope, ask the owner. Do not remove features to save time; the owner prefers full
scope and builds with AI agents. Build features fully even when they cannot be tested yet, and record what
still needs testing in 12.3.
