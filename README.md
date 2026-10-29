# GridMedic

Outage triage for utilities without smart meters. When a storm hits, GridMedic turns a flood of
customer complaints (calls, WhatsApp, SMS in English, Sinhala and Tamil), SCADA trips, crew voice
notes and damage photos into located faults on the grid, and a ranked repair queue with crews
assigned.

Entry for the Meta Global AI Developer Hackathon 2026, Indie track, theme **Push the Frontier**
(energy). See [PROJECT_BRIEF.md](PROJECT_BRIEF.md) for the full plan.

## Built during the hackathon

All code in this repository was written from Oct 29, 2026 onward, during the event. An earlier
team project with the same name (Jaseci hackathon) inspired the idea; none of its code is reused.

## How it works

Meta models read; deterministic code locates and decides.

| Step | Who does it |
|---|---|
| Calls and crew voice notes to text | Muse Voice Transcribe |
| Complaint to structured report (address, symptom, hazard, junk) in any language | Muse Spark (JSON schema output) |
| Damage photos: what broke, how bad | Muse Spark (vision) |
| Outline pole, conductor, tree; measure wire clearance | SAM 3.1 |
| Place each complaint on its service transformer (account, caller ID, address, landmark) | code: [customers.py](gridmedic/customers.py) |
| Which device opened or which line broke | code: [tracer.py](gridmedic/tracer.py), likelihood search over the feeder |
| Ask a customer the question that best separates two explanations | code picks who; message sent in their language |
| Priority and crew dispatch, vs a first-call-first-served baseline | code: [planner.py](gridmedic/planner.py) |
| Plain-language reason for each located fault, for the dispatcher | Muse Spark |
| Restoration-time SMS to every customer who reported, in their language | Muse Spark |
| Network down: keep triaging text messages on this laptop | Muse Glimmer (open weights, local server) |
| Network back: review and correct the offline extractions, rebuild the evidence | Muse Spark |
| Photo of a paper single-line diagram to the grid model, scored against the real feeder | Muse Spark: [diagram.py](gridmedic/diagram.py) |

The feeder is the IEEE 34-bus test feeder laid over Galle, Sri Lanka, with ~1,950 synthetic customers
mapped to 94 service transformers. The demo storm ([scenarios/galle_storm.json](scenarios/galle_storm.json))
has four faults: a pole down, a tree on the line, a blown transformer fuse found from complaints alone,
and a live wire on the road.

## Run it

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Windows; use .venv/bin/pip elsewhere
cp .env.example .env                             # add MODEL_API_KEY for live Meta models
.venv/Scripts/python -m uvicorn gridmedic.server:app --port 8000
```

Open http://localhost:8000 and press **Start storm**.

Without an API key the app runs in **mock mode**: cached model responses are replayed, and anything
not cached falls back to the scenario's labelled ground truth (tagged `mock` in the UI). With a key,
every model response is cached in `.cache/model/`, so replays are free and repeatable.

Headless replay with a summary against ground truth:

```bash
.venv/Scripts/python scripts/run_headless.py --timeline
```

Other scripts:

- `scripts/smoke_test.py [call.wav] [photo.jpg]`: one small call to each Meta model to check the key.
- `scripts/eval_extraction.py [--glimmer]`: complaint-extraction accuracy per language against the
  scenario labels; writes `eval/extraction-<model>.json`.

Offline mode expects Muse Glimmer behind an OpenAI-compatible server (vLLM, SGLang or llama.cpp) at
`GLIMMER_BASE`. Without one, the **Online/Offline** toggle still works and labels the offline steps `mock`.

## Data

All people, phone numbers and accounts are synthetic. Damage photos and drone footage go in
`media/` (see the paths in the scenario file); public datasets such as TTPLA and InsPLAD are the
intended sources. Check each licence before adding files.
