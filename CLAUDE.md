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
- **Must use Meta's models:** Muse Spark, Muse Voice Transcribe, SAM 3.1 (Meta Model API). The rules also allow
  open-weights Muse Glimmer, Muse Image, Muse Wonder and Muse Code; all are unused (Glimmer dropped 2026-11-01:
  offline mode removed, it only did text extraction and the owner chose to spend the time on the Meta Model API models).
- **Judging:** Impact 30%, Use of Meta AI tooling 25%, Technical depth 20%, Demo 25%. Top 5 per track are
  ranked from the demo video.
- **Data:** only synthetic or public data. Use the Meta API in **Standard** mode (not Contributor).
- **Honesty rules for anything shown:** say on screen that customers are fictional; never use real
  utility names in customer-facing text (templates say "Outage desk", not a utility's name); real
  facilities from OpenStreetMap appear only under generic names ("Hospital on <street>"); never claim
  how a specific real utility operates; label mock output as mock.
- **No API calls without the owner's GO (owner's rule, 2026-10-30).** On the owner's machine no session may call the
  Meta Model API unless the owner's latest message contains the word **GO** in capitals. Enforced, not
  just written: the git-ignored marker `.claude/require_go` switches the rule on; `relight/models.py` then refuses every
  live request unless `config.api_allowed()`; hooks in the git-ignored `.claude/settings.local.json` (script
  `.claude/hooks/api_gate.py`) open the gate only for a turn whose owner message contains GO, close it when the turn
  ends and at session start, and block tool calls that try to open it or remove the marker. Never try to work around
  this. Without GO, work from the cache and mock mode, and ask the owner for GO (with a cost estimate) before anything
  that needs the API. The owner can also run with `RELIGHT_ALLOW_API=1` set in their own shell (ignored in `.env`).
  A fresh clone has no marker and no local hooks, so anyone else uses their own key in `.env` with no restriction.
- **API key:** lives only in `.env` (git-ignored; `.env.example` has an empty key). The same hook refuses any tool
  call that reads, writes or commits `.env`, so the key never enters a session or the repo. Only the owner edits it.
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
(`muse-voice-transcribe-1.0`), `SAM_MODEL` (`sam-3.1`), optional
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
  vision.py              damage photos: Spark classifies, SAM outlines pole/wire, wire clearance in metres;
                         drone/clip survey (poles and wires followed, what lies across them); pole-tag reading
  poles.py               pole register (a tagged pole every 45 m per section, synthetic) and tag lookup
  masks.py               SAM 3.1 pixel masks (Meta's `meta-sam-parser`): lean, sag, pixel contact, outline overlays
  tracer.py              probabilistic fault tracer (candidates, likelihood, greedy search, confidence)
  network.py             power flow over buses/section bodies; switching plans and safety check
  planner.py             priority scoring, crew work steps, what-if schedule vs first-call baseline
  engine.py              the triage loop: evidence, incidents, crews, switching, notices, portal status
  callagent.py           AI call agent: answers every call in the caller's language from engine state
  realtime.py            realtime Voice Transcribe line per live call (WebSocket, diarization, street keywords,
                         per-utterance cache, paced mock)
  copilot.py             call-taker copilot on hard live calls: live fields, Spark's next line, file/end
  voice.py               text to speech (edge-tts) with a phone-line filter; cached in media/audio/tts/
  scenario.py            scenario loader, simulated physical World, Replayer (clock, time-lapse)
  diagram.py             paper single-line diagram -> topology with Spark; scoring; diagram renderer
  server.py              FastAPI app, REST endpoints, WebSocket broadcast, scenario switching
scenarios/               galle_storm.json (hand-written), houston_hurricane.json and
                         chennai_cyclone.json (generated by scripts/make_storm.py)
scripts/
  run_headless.py        replay a scenario to completion, print incidents and ground-truth check (--calls)
  make_calls.py          synthesise the voiced callers in scenarios/calls/*.json -> media/audio/calls/
  build_overlays.py      draw SAM outlines over clips and photos from the cache -> media/overlays/ (no API calls)
  check_offline.py       checks that need no model call (fact check, realtime replay, uploads, masks, pole tags)
  eval_keywords.py       Voice Transcribe with and without street-name `keywords` (needs GO)
  make_storm.py          generate storms on OSM feeders (fault placement rules, complaints, meters)
  fetch_osm.py           download roads/buildings/landmarks from Overpass into data/osm/
  smoke_test.py          one small live call per Meta model (needs MODEL_API_KEY)
  eval_extraction.py     per-language extraction accuracy vs scenario labels (Spark; `--replay` scores cached engine readings)
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
  first: `BD`/`OUT`/`PWR <10-digit account>` needs no model; else Spark) ->
  `_locate` (account, address, caller ID, landmark, street) -> `_claim` -> `_apply` (dedup by account
  or sender; hazards; evidence).
- Mock mode: if a model call is not cached (or there is no key), extractors return the scenario's
  `truth` labels, labelled `mock (ground truth)`; unlabelled portal text uses `_keyword_fields`
  (`mock (keywords)`). Explanations and notices fall back to templates (`mock (template)`).
- Every model response is cached in `.cache/model/` keyed by a request hash: replays are free and
  deterministic. Changing a prompt changes the key.

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
  `rejected` lists what was missing); then the template is spoken. No key -> template
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
- **Live calls** (console "Live calls" switch, `engine.live_calls`; off by default and in headless runs): a voiced
  call plays out in real time on one realtime Voice Transcribe line (`realtime.Line`): handshake with
  `languageBias` and the feeder's street/landmark names as `keywords`, 24 kHz PCM in 80 ms frames paced at real
  time (silence between turns), `DIARIZATION` mode; `speechStart`/`transcript`/`speaker`/`speechComplete` events
  become `live_partial` / `live_turn` broadcasts. The agent's own lines are not sent (their words are known; in the
  first live run their transcript arrived ~3.5 s late and was taken for the caller's next answer). A turn belongs
  to whoever's audio was on the line at its `speechStart`; the diarization label is shown, not trusted (the agent
  and caller got the same label "A"). What a live session heard per utterance is cached in `.cache/model/asr-rt-*.json` and replayed at the same
  pace; without the API the script is paced out word by word (`mock (script)`), and the opening falls back to the
  file endpoint's cached transcript. Sinhala: Spark listens after each utterance. The storm waits while the agent
  is on a live call (the call runs inside `handle`, under the writer lock). `realtime.SPEED` speeds up mock
  pacing for tests.
- **Hand-over and copilot** (`engine.handover`, "Hard live calls to me"): a live call that `CallAgent.urgent`
  flags (live wire, fire, critical customer) gets the fixed `transfer` line and is parked (`engine.parked`); a
  `Copilot` (`engine.copilots`) runs outside the lock. Code reads partial transcripts at once (`_quick`: hazard
  words, house + street, account), Spark reads each finished caller turn (`_read`), code places the caller and
  shows customer, critical flag, transformer, incident, crew, ETR, hazards nearby. `_options` lists what is
  still worth saying (safety, hazards, address, medical equipment `ask_medical`, the tracer's next-door question,
  then status and close after filing); Spark picks and words one (`SUGGEST_SYSTEM`, same fact check, fixed lines
  verbatim) with an English line and a reason. The call-taker clicks Say it / another option / types / holds the
  mic (`/ws/mic/{id}`, mixed into the line; live only). `File report` -> `engine.file_call` (same reading,
  placing, re-trace; withheld facts count as given once asked); `End call` files if needed and closes the line.
  While a copilot is open, new calls are answered by the agent at once (a live agent call would hold the lock).
  Simulated callers answer the copilot from the truth (`medical_yes` / `medical_no` from the critical flag).
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
| POST | `/api/control` | `{"action": start|pause|reset|speed|live_calls|handover, "speed": n, "on": bool}` |
| POST | `/api/plan` | `{"incident": "I2", "plan": "isolate"}` operator approves a switching plan |
| POST | `/api/copilot` | `{"id": "C03", "action": say|file|end, "act"?, "text"?}` call-taker on a handed-over call |
| GET | `/api/customer?q=` | portal status by account or phone |
| POST | `/api/customer/upload` | multipart `file` (photo or video, max 60 MB) -> `{"path"}` under `media/uploads/` |
| POST | `/api/customer/report` | `{"text", "who", "language", "media"}` live complaint (processed like any other) |
| GET | `/api/call/{id}/{turn}.wav` | one line of an agent call: caller recording or synthesised speech |
| POST | `/api/diagram` | digitise the paper diagram (optional image upload) and score it |
| WS | `/ws` | snapshot on connect, then `state`, `timeline`, `message`, `probe`, `notice`, `photo`, `drone`, `scada`, `clock`, `reset`, `scenario`, `messages`, `network`, `live`, `live_call`, `live_turn`, `live_partial`, `copilot` |
| WS | `/ws/mic/{id}` | call-taker microphone: 24 kHz mono s16le frames, mixed into the call's realtime line |

All writes to the engine go through one `asyncio.Lock` in `server.py` (replay, operator, portal).

---

## 8. Meta Model API facts (from Meta's docs; checked live 2026-10-30 where marked)

- **Checked live (2026-10-30):** Spark JSON-schema extraction (si, ta), Spark audio (`input_audio`, Sinhala),
  Spark video (`video_url` data URL), SAM 3.1 image and video (`input_video`) all work with the request shapes in
  `models.py`. Voice Transcribe rejects 8 kHz WAV ("expected mono s16le at 16000 or 24000 Hz"); `_wav_16k` upsamples
  phone audio first. `languageBias` takes language names (`["Tamil", "English"]`); the response has `transcript`.
  SAM 3.1 returned **413** for a 7.6 MB video (~10 MB base64): keep clips small (480p, 10 fps, ~3 MB).
  Spark spends ~1,230 reasoning tokens per call (billed as output). Galle live run: 195 calls, 24 min, $1.13; the
  2.9 MB drone clip then passed (Spark + SAM tracking 3 poles, 8 spans, the trunk; $0.12). Galle is cached live.
  Houston and Chennai not run live yet (owner: skip for now; estimates ~$1.6–2 / 30 min and ~$9–10 / 2.5–3 h).

- Base URL `https://api.meta.ai/v1`, header `Authorization: Bearer $MODEL_API_KEY`, OpenAI-compatible.
- **Muse Spark** (`muse-spark-1.3`): `POST /chat/completions`, `response_format: {"type": "json_schema", ...}`;
  accepts text, image, video, audio, PDF; Spark always reasons. Pricing ~$1.25 / M input, $4.25 / M output.
- **Voice Transcribe** (`muse-voice-transcribe-1.0`): `POST /asr/transcribe?sessionId=...`, multipart
  `request` (JSON: mode, model, audioEncoding, optional `languageBias` list) + `audio` (WAV). 25 languages
  including Tamil, Hindi, Spanish, English, with code-switching. **Not Sinhala** (checked 2026-10-30; some
  third-party articles claim 70+ languages, Meta's page lists 25). Realtime WebSocket:
  `wss://api.meta.ai/v1/asr/realtime`. Speaker diarization: `mode: "DIARIZATION"` (file response has
  `turns[]` with `speaker`; realtime sends `speaker` events). Realtime protocol (Meta's reference, read
  2026-10-30; **checked live 2026-10-30** on one English call, all as documented: handshake ~3 s, partials
  every ~0.3 s, `speechComplete` ~3.5 s after the speech ends, `speaker` "A"): no auth header; first text frame `{"authorization": {"accessToken": "Bearer
  KEY"}, "audioEncoding": "PCM_24KHZ"|"PCM_16KHZ", "model", "mode": PUSH_TO_TALK|ENDPOINTING|DIARIZATION,
  "partialMode", "emitAudioProgress", "keywords", "languageBias"}` within 10 s; reply has `sessionId`; binary
  80 ms PCM frames at real time (too slow or fast -> close 1008); end with `{"type": "endStream"}`; events
  `transcript` (`final`), `speechStart`/`speechEnd`/`speechComplete` (`turnId`, `transcript`), `speaker`
  (`label`), `audioProgress`, `error`. Pricing **$0.18 per hour** of audio, streaming
  or not, billed per whole second; failed and 429 requests are not billed.
- **No text-to-speech or speech-to-speech model** exists on the Meta Model API (checked 2026-10-30).
- **Checked live 2026-11-01:** Voice Transcribe `keywords` work on the file endpoint (in the `request` part) and the
  realtime handshake, but **each keyword must be 30 characters or fewer** (HTTP 400 "ASR keyword 0 exceeds the maximum
  length of 30 characters"); `models.fit_keywords` cleans names ("Clinic on Wirt Road" -> "Wirt Road") for both. With the
  feeder's street and landmark names as keywords the street was heard right in 11 of 13 clips where the caller names it
  (Galle 4->5 of 5, Houston 1->3 of 3, Chennai 1->3 of 5), against 6 of 13 without (synthetic voices, small sample).
  Realtime with 100 keywords: handshake 4.7 s, three clips back to back, transcripts exact, no errors.
  Spark `reasoning_effort` (top-level field: minimal|low|medium|high|xhigh|max; `none` is a 400): `minimal` cut extraction
  latency 4.4 -> 2.4 s (~74% fewer output tokens) and Sinhala line wording 9.9 -> 2.8 s (~88% fewer), same results on a
  tiny sample. Off by default (`SPARK_EFFORT` unset) so no cached request key changes; set it to adopt, then re-run
  Galle/Houston (~$1.1 / ~$1.5) because every request changes. Spark listening to Sinhala needs a domain hint in the
  prompt (done in `spark_listen`): without it C02 came out as near-nonsense and was filed as junk; with it, at
  `minimal` effort, it reads "Hospital Road ... a pole has fallen" in 8.5 s (house number still off: 40 for 47; higher
  efforts were slower and invented place names).
- **SAM 3.1** (`sam-3.1`): `POST /responses` with `input_text` (short noun phrase) + `input_image`
  (URL or base64 data URL) or `input_video`. Output is special-token text:
  `<|box;x1=..;y1=..;x2=..;y2=..;w=..;h=..;c=..|><|mask;x=0;y=0;data=H,W,<enc>payload|>`, video lines
  prefixed `<Nf>`. Boxes are in source pixels; mask payload is base85 (not decoded yet; only boxes are
  used). `metadata.include_confidence: "true"` adds `c=`.
- **Muse Glimmer** (not used): open weights (Apache 2.0), ~30B dense, text + image in; Q4_K_M GGUF ~15.6 GiB; hosted on
  OpenRouter at $0.30 / $1.20 per M tokens (DeepInfra). Dropped 2026-11-01; the offline mode that used it was removed.
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
- Realtime call agent and call-taker copilot (2026-10-30, owner's choice): "Live calls" switch plays voiced calls
  in real time with partial transcripts; hard calls (live wire, fire, critical customer) go to a human call-taker
  panel with live fields and suggested lines. Verified in mock mode (headless driver and browser); see 12.3.
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
- [x] Get the **Meta Model API key** and put it in `.env` (done; verified 2026-11-01: mode is live, key set).
- [x] ~~Partner credit forms~~ (Baseten, Modal, Fireworks): closed, and no longer needed (they only covered Glimmer, now dropped).
- [ ] **Submit on Cerebral Valley** by Nov 4, 10:00 PM Sri Lanka time (hard deadline Nov 5, 7:30 AM).

Media
- [x] ~~Record calls~~: the owner cannot record; calls are synthetic voices (edge-tts), labelled as such.
- [ ] **Listen to the voiced calls** in the console and say which voices or lines sound wrong.
- [x] Damage photos: nine from Wikimedia Commons, wired into all three scenarios (`media/photos/CREDITS.md`).
      Still missing: a blown-fuse photo for Galle's `crew_fuse.jpg`.
- [x] Drone clip and four customer videos (owner's choice, 2026-10-30): third-party clips, git-ignored, credited in
      `media/videos/CREDITS.md`; `scripts/fetch_videos.py` downloads and trims them after a fresh clone.
- [ ] Pole-tag reading (chosen 2026-11-01): send a photo of a pole with a visible ID tag. The agent adds the tag to
      the scenario's `pack.pole_aliases` (tag + street + house number) so the register finds it.
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
- [x] Run `scripts/smoke_test.py`; fix request-format mismatches (done 2026-10-30, see section 8 "Checked live").
- [ ] *(needs GO)* Run all three scenarios live: **Galle done 2026-10-30, Houston done 2026-11-01 (7/7, 0 dark, 184
      Spark entries, 25 Spark-worded agent lines, 0 fact-check rejects; both cached); Chennai still mock**
      (66 timeline entries are `mock (ground truth)`; it takes ~2.5-3 h, so run it in the owner's own shell with
      `RELIGHT_ALLOW_API=1`). Keep the regression baseline green.
- [x] Extraction accuracy measured 2026-11-01 for Galle and Houston with `scripts/eval_extraction.py <scenario>
      --replay` (scores the engine's own cached Spark readings; free). Muse Spark vs scenario labels, fields right:
      Galle (46 scored; re-measured after the Sinhala listening fix) street 91%, house_no 94%, symptom 94%, hazard 94%,
      junk 100% (en 29, si 11, ta 6; Sinhala symptom 82% is the weakest, Tamil hazard 5 of 6); Houston (161 scored) street 97%, house_no 98%, symptom 99%, hazard 99%,
      junk 100% (en 117, es 44). Not scored: SMS codes (no model) and complaints that made no message of their own.
      Misses on calls are mostly facts the caller gave only later or that come from caller ID (labels hold them), and
      the Sinhala call C02 (now read well enough to be filed as a fallen wire, not junk). Put the table in the README. Not run for Chennai or without `--replay`
      (that mode sends fresh requests: ~$2.6 for Galle+Houston; it refuses to score mock output).
- Gate gotcha: GO opens the API only for the turn that carries it. A background task's completion notice starts a new
  turn with the gate closed, so a long run must be polled in the foreground until it ends.
- Gate gotcha 2: while GO is open, **never replay an uncached scenario** (Chennai) with `run_headless.py`: every
  uncached request goes out live. On 2026-11-01 a Chennai regression run started that way and was stopped within
  minutes (~60 small calls, under $1). Run Chennai's baseline only on a turn without GO.
- [ ] *(needs `MODEL_API_KEY`)* Keep a running cost estimate under $150 (Voice Transcribe is $0.18/h).
- [ ] *(needs `MODEL_API_KEY`)* Run the voiced calls live: Voice Transcribe on en/ta/es/hi, Spark listening
      to the Sinhala call (`spark_listen` request shape), Spark rewording status lines; fix what breaks.
- [ ] *(needs photos)* Run the photo path live; finish SAM 3.1 mask decoding for wire clearance.
- [x] Drone damage assessment with SAM 3.1 video tracking (finished 2026-11-01, see 12.2).
- [x] Wire `audio` paths into the scenarios (done with synthetic calls; live test is the task above).
- [ ] *(needs the owner's feature choice)* Build the chosen optional features (12.2).

Can start now
- [x] Call scripts in every language and the `media/audio/calls/` layout (scenarios/calls/*.json).
- [x] Crew voice reports with read-back (synthetic audio; same pipeline as calls).
- [x] Find candidate public photo datasets and drone clips with their licences, for the owner to choose
      (`media/CANDIDATES.md`).
- [x] Customer portal sample buttons for the Houston and Chennai scenarios (`SAMPLES` in `web/customer.html`).
- [x] Console polish (2026-11-02): "Meta models" panel (`ModelClient.report`, per-model requests/tokens/cost/wait; header
      button), fictional/synthetic footer line, `/?run=<speed>` autorun for recording. Wait times only exist for live calls
      made after 2026-11-02 (`_latency_s` in the cache file).
- [x] Shot list, voice-over and captions: `docs/DEMO.md`.
- [x] README rewritten (architecture diagram, model table, accuracy, limits). Still missing: screenshots.
- [x] Submission text and final checklist: `docs/SUBMISSION.md`.

### 12.2 Optional features (owner chooses; agent builds)

- **Pole-tag reading** (chosen and built 2026-11-01): `vision.read_pole_tag` has SAM 3.1 find the plate
  ("pole number plate"), crops and enlarges it, and Spark reads it (if SAM finds none, Spark looks at the whole photo
  once). `poles.PoleRegister.lookup` names the pole (exact, or OCR-tolerant when a fold of look-alikes O/0, I/1, S/5,
  B/8 matches exactly one pole). `Engine._pole_tag` then places the photo's damage at that pole, nearest transformer
  on its section, with crew-level weight (4.0). Mock mode: the event's `media_pole_tag`; none for other photos. The
  register is synthetic (tags `P-0001`...); a scenario's `pack.pole_aliases` (`tag`, `street`, `house_no`) maps a real
  photographed tag to the pole nearest that address. Shown in the console photo popup and the portal `seen` panel.
- **AI call agent** (chosen and built, see 5.6a), with **realtime mode** over the Voice Transcribe WebSocket
  with diarization (chosen and built 2026-10-30): calls handled turn by turn as they are spoken.
- **Live call copilot** (chosen and built 2026-10-30, see 5.6a): realtime transcript, live field filling,
  Spark's suggested next line, for a human call-taker on the hard calls the agent hands over.
- **Drone damage assessment** (finished 2026-11-01): `vision.drone_survey` counts from SAM 3.1's tracks: poles and
  wires followed (a wire counts if its track spans 40% of the clip; SAM splits wires into pieces), poles lying (box
  wider than tall), and which wires an obstruction (fallen tree) crosses. Galle's Temple Road clip: 3 poles, 6 wires
  followed, trunk crosses 4 of 6. The survey is shown in the timeline detail and the map popup; it flags, it does not
  move the fault. **Masks** (added 2026-11-01, owner approved the dependency): `masks.py` decodes SAM's base85 lossless
  masks with Meta's `meta-sam-parser` 0.1.0 (read before use: pure Python, no network or process calls; ~4 us per pixel,
  so decodes are cached in `.cache/masks` and the survey samples 12 frames). From masks: pole lean (long thin masks only:
  a pole seen from above is a blob and gets none), wire sag as a share of its span, real pixel contact between a fallen
  tree and the wires (Temple Road: touches 6 of 10 wire tracks), and the outlines drawn over the clip
  (`media/overlays/temple_road_span_sam.mp4`, built by `scripts/build_overlays.py`) and over photos (built on first
  analysis). Photos also get the largest pole's lean (rough, street-level). SAM tags a traffic-light post as a pole too.
- **Realistic paper-to-grid:** hand-drawn pole-numbered sketch + meter-reader ledger → network and
  consumer index the engine runs on, with SAM symbol overlay and a review screen for flagged items.
- **Glimmer on-premise mode**: dropped 2026-11-01 (see section 2); code and docs removed.

### 12.3 Built but untested (verify once the API key is in)

Owner's rule (2026-10-30): build every feature in its intended form even when it cannot be tested yet, with a
mock/template fallback, and list it here. Tick items off (or fix them) after live testing; add new ones.

Call agent and crew calls
- [ ] Spark wording of agent lines (`SPEAK_SYSTEM`): naturalness per language, how often `facts_kept`
      rejects lines (Spark may write digits in local script or transliterate street names), latency per line.
- [x] `spark_listen` request shape works (2026-10-30). Quality checked 2026-11-01 on the one Sinhala call (C02): near
      nonsense without a domain hint, usable with it (see section 8); crew R4 read "Cinnamon Gardens, Lane 55, T 093".
      Still open: the SMS fallback (`not_understood`) and crew text fallback (`crew_by_text`) paths with real audio.
- [ ] Voice Transcribe on the synthetic 8 kHz phone WAVs (en/ta/es/hi): `languageBias` value format,
      `ENDPOINTING` response field `transcript`, accuracy vs the scripted text.
- [ ] Spark extraction of non-English and code-mixed crew reports (crew schema), and of a caller's
      opening plus answers after the agent's questions (re-extraction).
- [ ] Read-back correction path with real Spark misreads (only tested with a stand-in reading).
- [ ] Live synthesis of the World's site reports before transcription (edge-tts latency in the loop).
- [ ] Neighbour question: Spark reading the caller's yes/no about next door as a probe answer.
- [ ] Voices: pronunciation of street names and numbers by each edge-tts voice; native-speaker check of
      every new Sinhala / Tamil / Spanish / Hindi line (agent, callers, crews, read-back words).

Realtime calls and copilot (`realtime.py`, `copilot.py`)
- [x] Realtime WebSocket against the live API (2026-10-30): handshake with `keywords` (2 names), event shapes and
      latencies as documented, transcript of C01 exact. 100 `keywords` and three clips on one line checked 2026-11-01.
- [x] Live run 2026-10-30 of C01 (agent), C03 and C31 (hand-overs, copilot driven by its top suggestion): every
      caller and call-taker utterance heard by realtime and attributed by `speechStart` time; Spark read the
      realtime "nine zero zero ..." as account 9000000000; Spark's copilot choices sensible, no fact-check rejects.
      Diarization gave everyone label "A" (labels shown, not trusted). Cost of the GO turns: ~$0.33 Spark (33 calls,
      ~2,100 output tokens each) + ~30 min of line time (~$0.09).
- [ ] Copilot latency: Spark takes ~20 s per call, so code's line is now shown at once and Spark's reading and
      wording replace it when they arrive (measured live: ~10 s from the call-taker speaking to code's next line,
      mostly the spoken audio). Not yet seen live: how often Spark's line lands before a human speaks; Spark
      reasoning effort could be lowered if the API allows it (see https://dev.meta.ai/docs/reasoning).
- [ ] Line noise: the realtime model produced a turn ("Yeah") while nobody was speaking; turns outside any
      utterance are now ignored, and only real microphone audio becomes a call-taker turn. Watch for it again.
- [ ] Test driver for live runs lives in the session scratchpad only (`live_test.py --tts --only=C01,C03,C31`);
      move it to `scripts/` if more live runs are needed.
- [ ] Cached realtime replays (`asr-rt-*`): pace and partials look right after one live run.
- [ ] Copilot suggestions from Spark (`SUGGEST_SYSTEM`): choice quality, wording per language, fact-check rejects,
      latency between the caller's last word and the next suggestion (Spark reasons ~1,200 tokens per call).
- [ ] Microphone path: AudioWorklet at 24 kHz in Chrome, frames mixed into the line, the call-taker's speech
      transcribed and answered; a real human voice on the line (owner cannot record: maybe skip in the video).
- [ ] Sinhala live calls: Spark listening per utterance (latency) and the copilot reading Sinhala partials (code's
      quick read only knows Latin-script street names).
- [ ] Native-speaker check of the new lines: `transfer`, `ask_medical`, `medical_yes` / `medical_no` (si, ta, es, hi).
- [ ] Call-taker voices (`voices.taker`): en-GB Sonia for Sri Lanka is a stand-in; Sameera / Kumar double as caller voices.

Photos and videos (`vision.py`, `models.py`)
- [x] Spark and SAM 3.1 on the nine Commons photos, live (2026-11-01): outlines, lean 3-13 degrees on the leaning poles;
      wire clearance in metres is still unmeasured (needs a pole fully in frame).
- [ ] Spark watching a clip (`spark_video_json`: `video_url` content part, unverified) and SAM 3.1 tracking
      (`segment_video`: `input_video` part, unverified); request size limits for a 7.6 MB drone clip.
- [ ] Portal uploads from a phone (MOV from iPhone, large files) and the `seen` panel with real model output.
      (Offline 2026-11-01: MOV and 50 MB MP4 accepted, >60 MB gives 413; HEIC gives 415.)
- [ ] Pole-tag reading live, partly done 2026-11-01: on the nine photos (none has a legible plate) no false tag was
      reported; on Houston's tree photo SAM found a plate box and Spark said it was too blurred, so no guess. Still open:
      the owner's photographed tag (needs the photo, `pack.pole_aliases`). Stand-in tests: `scripts/check_offline.py`.
- [x] Voice Transcribe `keywords` on the file endpoint measured 2026-11-01 (`scripts/eval_keywords.py`, results in
      section 8): 11 of 13 vs 6 of 13. **Not adopted in the engine yet**: it changes every transcript and so every
      downstream Spark request (re-run Galle ~$1.1 and Houston ~$1.5). The realtime line already uses them.
- [ ] Drone survey on a second clip.

### 12.4 Order that saves the most time

1. Owner: API key into `.env`; submit credit forms.
2. Agent: live run and fixes; meanwhile the owner records audio from the scripts and picks media.
3. Owner chooses optional features; agent builds them.
4. Nov 3: agent prepares the shot list and script; owner records and edits.
5. Nov 4: agent finalises README and checks; owner submits.

When in doubt about scope, ask the owner. Do not remove features to save time; the owner prefers full
scope and builds with AI agents. Build features fully even when they cannot be tested yet, and record what
still needs testing in 12.3.
