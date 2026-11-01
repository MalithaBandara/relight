# Relight

Outage triage for utilities without smart meters. When a storm hits, Relight turns a flood of
customer complaints (calls, WhatsApp, SMS in English, Sinhala and Tamil), SCADA trips, crew voice
notes and damage photos into located faults on the grid, and a ranked repair queue with crews
assigned.

Entry for the Meta Global AI Developer Hackathon 2026, Indie track, theme **Push the Frontier**
(energy). See [PROJECT_BRIEF.md](PROJECT_BRIEF.md) for the full plan.

## Built during the hackathon

All code in this repository was written from Oct 29, 2026 onward, during the event.

Relight grew out of an idea first explored in
[GridMedic](https://github.com/MalithaBandara/gridmedic), an earlier team project built in Jac with
Gemini at the Jaseci Labs AI Hackathon (17 Oct 2026). Relight is a new project with a new name and a new
codebase; no code from GridMedic is reused. What is different:

- written from scratch in Python, on Meta's models (Muse Spark, Voice Transcribe, SAM 3.1)
- a probabilistic fault tracer that asks customers the question that best separates two explanations
- feeders generated from real OpenStreetMap roads and buildings, and three scenarios (Galle, Houston with
  smart meters that fail mid-storm, Chennai at ~2,400 messages)
- crew lifecycle with diagnosis changes from site reports, hidden faults found after restoration, and
  safety-checked restoration switching across a tie to a second feeder
- an outage-management console modelled on commercial OMS work agendas, and a customer portal

## How it works

Meta models read; deterministic code locates and decides.

| Step | Who does it |
|---|---|
| Calls and crew voice notes to text | Muse Voice Transcribe |
| Complaint to structured report (address, symptom, hazard, junk) in any language | Muse Spark (JSON schema output) |
| Damage photos: what broke, how bad | Muse Spark (vision) |
| Outline pole, conductor, tree; measure wire clearance | SAM 3.1 |
| Place each complaint on its service transformer (account, caller ID, address, landmark) | code: [customers.py](relight/customers.py) |
| Which device opened or which line broke | code: [tracer.py](relight/tracer.py), likelihood search over the feeder |
| Ask a customer the question that best separates two explanations | code picks who; message sent in their language |
| Priority and crew dispatch, vs a first-call-first-served baseline | code: [planner.py](relight/planner.py) |
| Plain-language reason for each located fault, for the dispatcher | Muse Spark |
| Restoration-time SMS to every customer who reported, in their language | Muse Spark |
| Photo of a paper single-line diagram to the grid model, scored against the real feeder | Muse Spark: [diagram.py](relight/diagram.py) |
| "BD <account>" breakdown SMS, the format customers already use | code only, no model call |
| Located faults become incidents; crews dispatched by priority, travel and repair on the storm clock | code: [engine.py](relight/engine.py) |
| Crew's on-site report confirms the diagnosis or changes it ("transformer fine, service wire down") | Muse Spark reads the report; code revises the incident |
| Restoration switching around a located fault; plans that would energise a fault or a crew's work zone are blocked | code: [network.py](relight/network.py); the operator approves |
| Customers still dark after a repair reveal a hidden second fault | code: unclaimed complaints go back to the tracer |
| Customer portal: report in any language, check status, see the messages sent | `/customer` |

Three scenarios run on the same engine (pick one in the header):

| Scenario | Network | Customers | What it shows |
|---|---|---|---|
| Galle, Sri Lanka | IEEE 34-bus test feeder laid over Galle | 1,951 | The full story: no smart meters, Sinhala/Tamil/English, safe switching, the agent changing its mind, a hidden fault |
| Houston, USA | Generated from real OpenStreetMap roads and buildings (Spring Branch) | 3,044 | Smart meters send last-gasp messages until the meter network fails mid-storm; English/Spanish |
| Chennai, India | Generated from real OpenStreetMap roads and buildings (Velachery) | 24,559 | Scale: ~2,400 messages in 30 minutes in English/Tamil/Hindi, re-traced every 15 s |

For Houston and Chennai the line runs along real streets (a shortest-path tree over the road network
from the substation), customers sit in real buildings, and landmarks are real facilities shown under
generic names ("Hospital on <street>"). The electrical network, customers and accounts are synthetic.
Map data © OpenStreetMap contributors (ODbL), cached in `data/osm/`; refresh with
`scripts/fetch_osm.py`, and regenerate those storms with `scripts/make_storm.py`.

The Galle feeder is the IEEE 34-bus test feeder laid over Galle, Sri Lanka, with ~1,950 synthetic customers
mapped to 94 service transformers. The demo storm ([scenarios/galle_storm.json](scenarios/galle_storm.json))
has six faults: a pole down, a tree on the line (isolated by switching so the water pumping station
gets power back from Feeder 2), a blown transformer fuse found from complaints alone, a live wire on the
road, a service wire that looks like a blown fuse until the crew arrives, and a blown fuse hidden behind
the pole-down outage that only shows once that repair is done.

## Run it

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Windows; use .venv/bin/pip elsewhere
cp .env.example .env                             # add MODEL_API_KEY for live Meta models
.venv/Scripts/python -m uvicorn relight.server:app --port 8000
```

Open http://localhost:8000 and press **Start storm**.

Without an API key the app runs in **mock mode**: cached model responses are replayed, and anything
not cached falls back to the scenario's labelled ground truth (tagged `mock` in the UI). With a key,
every model response is cached in `.cache/model/`, so replays are free and repeatable.

**Using your own Meta Model API key:** put it in `.env` as `MODEL_API_KEY=...` (get one at https://dev.meta.ai) and
restart the server. Nothing else is needed. `.env` is git-ignored, so the key stays on your machine; never commit it.
The author's machine has an extra local switch that holds back paid calls until the author approves them (`api_allowed` in
`relight/config.py`); a fresh clone does not have it and calls the API normally.

To fetch the third-party example videos (git-ignored): `pip install yt-dlp`, then `python scripts/fetch_videos.py`.

Headless replay with a summary against ground truth (`galle_storm`, `houston_hurricane` or `chennai_cyclone`):

```bash
.venv/Scripts/python scripts/run_headless.py houston_hurricane --timeline
```

Other scripts:

- `scripts/smoke_test.py [call.wav] [photo.jpg]`: one small call to each Meta model to check the key.
- `scripts/build_overlays.py`: draw SAM 3.1's outlines over the drone clip and photos from the cached responses
  (poles blue, wires amber, fallen trees red); `relight/masks.py` also measures pole lean, wire sag and where a
  fallen tree touches the wires, using Meta's `meta-sam-parser` to decode the masks.
- `scripts/eval_keywords.py`: Voice Transcribe with and without street-name keywords.
- `scripts/eval_extraction.py [scenario] [--replay]`: complaint-extraction accuracy per language against the
  scenario labels; `--replay` scores the engine's own cached readings (no API calls). Writes
  `eval/extraction-<model>-<scenario>.json`.

## Data

All people, phone numbers and accounts are synthetic. Damage photos and drone footage go in
`media/` (see the paths in the scenario file); public datasets such as TTPLA and InsPLAD are the
intended sources. Check each licence before adding files.
