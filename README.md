<h1 align="center">Relight</h1>

<p align="center">
  <strong>An autonomous AI outage agent for electric utilities.</strong><br>
  From one dark house to a major storm, it answers every call, finds the failed device on the grid, dispatches crews,<br>
  keeps customers updated, and prepares safe restoration switching for the operator to approve.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white" alt="Python 3.12">
  <img src="https://img.shields.io/badge/models-Muse%20Spark%20%C2%B7%20Voice%20Transcribe%20%C2%B7%20SAM%203.1-0467DF" alt="Models: Muse Spark, Voice Transcribe, SAM 3.1">
  <img src="https://img.shields.io/badge/status-hackathon%20prototype-orange" alt="Status: hackathon prototype">
  <img src="https://img.shields.io/badge/data-synthetic-lightgrey" alt="Data: synthetic">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License: Apache 2.0"></a>
</p>

<p align="center">
  <a href="#what-the-agent-does-on-its-own">The agent</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="#results">Results</a> ·
  <a href="#limits">Limits</a> ·
  <a href="#development">Development</a>
</p>

<p align="center"><strong><a href="https://youtu.be/Wdf_SaKpP8I">▶ Watch the 3-minute demo video</a></strong></p>

![The Relight control-room console during the Galle storm: feeder map, work agenda, event details with switching plans, and event log](docs/img/console.png)

<p align="center"><em>The console mid-storm on the Galle scenario, replaying cached live model responses. For the selected event, two switching plans are blocked because a crew is working on the line, and a safe plan waits for the operator to approve it.</em></p>

> [!IMPORTANT]
> **Relight is a prototype and everything shown is synthetic.** It runs on a simulated utility and has not been used by
> a real one. Every customer, address, phone number and account is fictional. Caller and crew voices are synthetic. Maps
> come from OpenStreetMap. Damage photos and clips are third-party and credited in the repository. The clips themselves
> are not in the repository: see [Videos](#videos).

## Overview

Relight works an outage on its own, whether one house is dark or a storm has taken out a whole feeder. It reads what
people send (calls, SMS and chat in their own language; crew voice reports; damage photos and drone clips) and acts on
it: it answers callers, questions customers when the evidence is unclear, finds the failed device on the grid,
dispatches crews, changes its diagnosis when a crew reports something different, and keeps customers updated. It works
with or without smart meters: where a utility has none, the customers' own complaints are the sensor.

The design rests on one rule:

**Meta models read, watch, hear and speak. Deterministic code locates and decides. The agent acts. Critical decisions are
forwarded to the operator.**

Relight runs the response without waiting to be told what to do. Muse Spark, Muse Voice Transcribe and SAM 3.1 turn messy
human evidence (speech, text, photos, video) into structured facts, and a probabilistic tracer decides which device opened
or which line broke. From there the agent takes the initiative: it asks customers for the evidence it is missing, sends
crews, revises its diagnosis when they report back, finds faults hidden behind the first, and keeps customers updated.

Its autonomy has deliberate limits. A model never guesses where a fault is, and the agent never applies a switching plan by
itself: a safety-checked planner works out how to restore power and forwards each plan to the operator to approve.

Built solo for the **Meta Global AI Developer Hackathon 2026** (Indie track, theme *Push the Frontier*: understand and
control a physical system).

## What the agent does on its own

Each new report runs the same cycle, and what the agent does next produces the evidence for the following one:

1. **Read.** Spark, Voice Transcribe and SAM 3.1 turn each call, message, photo and crew report into structured facts.
2. **Decide.** The tracer works out what failed and how sure it is, and the planner ranks the work.
3. **Act.** The agent asks a question, sends a crew, answers a caller or sends customers an update.
4. **Check the result.** Answers, crew reports and calls from people still in the dark go back into step 1, so the agent
   corrects itself.

| When this happens | The agent does this, without being told |
|---|---|
| A call comes in | Answers in the caller's language, confirms the address, warns about hazards and gives the current status |
| The evidence fits two explanations | Finds the customer whose answer separates them, asks by text or during a call, and traces again |
| One house is dark and nobody else reports it | After 150 seconds, asks a neighbour on the same transformer; if the neighbour has power, opens a service-wire job |
| A fault reaches 80% confidence | Opens an incident, ranks it, sends the nearest idle crew with the right skills, and tells the people who reported it when power should be back |
| A crew finds something different | Reads the report back; once the crew confirms, changes the diagnosis, replans the work, and releases the crew if it can't do the repair |
| A patrol finds nothing and the device is still locked out | Extends the patrol, up to three patrols |
| People are still dark after a repair | Treats their calls as new evidence and finds the fault hidden behind the first |
| A hospital's backup generator fails | Raises that outage's priority |
| A restoration estimate moves by 15 minutes or more | Texts the affected customers the new time |
| A caller reports a live wire or fire, or a critical customer calls | Gives the safety line and flags the call to the control room; in live-call mode it can put the call through to a call-taker |
| Restoration switching could help | Proposes plans, blocks any unsafe one, and **stops for the operator** |

### Measured: a storm with nobody at the console

`python scripts/run_headless.py galle_storm --no-switching --timeline` replays a storm with no operator action and no
plan approved. Every fault was found and everyone was restored:

| Storm | Calls answered | Crew reports read back | Questions asked | Crews dispatched | Updates sent | Faults found | Dark at the end | Operator actions |
|---|---|---|---|---|---|---|---|---|
| Galle | 25 | 11 | 4 | 12 | 131 | 6 of 6 | 0 | **0** |
| Houston | 84 | 7 | 5 | 13 | 713 | 7 of 7 | 0 | **0** |
| Chennai | 883 | 9 | 2 | 15 | 6,563 | 9 of 9 | 0 | **0** |

The three smaller outages (`house_fuse`, `tree_on_line`, `hospital_generator`) offer no plan to approve and also end with
every fault found and nobody dark.

- **What the operator adds.** The agent can finish a storm alone, but switching gets people back sooner. With the one plan
  approved per storm, customer-minutes interrupted fall by 24% in Galle (94,264 to 71,618), 49% in Houston (223,936 to
  115,002) and 54% in Chennai (3,536,841 to 1,621,162).
- **What these runs are.** Crews and customers are simulated, and a finished repair closes the device in the simulation.
  Slower restoration also brings call-backs that never ran live, so 72 of Houston's 330 messages and 735 of Chennai's 3,741
  use the scenario's labels instead of a live reading, tagged `mock`. Galle has none.

## Highlights

- **Calls and texts in the customer's native language, with the context of their outage.** An AI call agent answers every
  call knowing the address on file, hazards reported nearby, whether the caller has already reported, the fault, the
  crew's status and when power should be back. People who text get the fault type and restoration time too. The agent
  also warns about hazards, escalates live wires and critical customers, and asks a neighbour when the tracer is torn
  between two explanations.
- **Realtime calls with a human in the loop.** Voiced calls play in real time on a Voice Transcribe realtime line; hard
  calls are handed to a call-taker with a copilot that fills the report live and suggests the next line.
- **Crews report by voice.** The agent reads each report back and nothing changes until the crew confirms. A crew can say
  the transformer is fine and the service wire is down, and Relight changes its diagnosis and replans the work.
- **Photos and drone clips.** SAM 3.1 outlines and tracks poles, wires and fallen trees; Spark reads the damage and the
  pole-number plate, and the pole is named from a register, not guessed.
- **Hidden second faults.** After a restoration, callers who are still dark reveal a fault hidden behind the first.
- **Customers and crews as users.** A customer can check their supply, report a problem or talk to the outage desk by
  voice; a crew has its own page.

<table>
  <tr>
    <th width="50%">Customer portal (<code>/customer</code>)</th>
    <th width="50%">Crew page (<code>/crew</code>)</th>
  </tr>
  <tr>
    <td><img src="docs/img/customer.png" alt="The customer portal: check my supply, report a problem, talk to the outage desk"></td>
    <td><img src="docs/img/crew.png" alt="The crew page: pick a crew, say or type a report, the agent reads it back"></td>
  </tr>
</table>

## Contents

- [What the agent does on its own](#what-the-agent-does-on-its-own)
- [Highlights](#highlights)
- [Quick start](#quick-start)
- [Usage](#usage)
- [Videos](#videos)
- [How it works](#how-it-works)
- [Results](#results)
- [Cost](#cost)
- [Limits](#limits)
- [Configuration](#configuration)
- [HTTP API](#http-api)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [What's next](#whats-next)
- [Security](#security)
- [Contributing](#contributing)
- [Credits and data](#credits-and-data)
- [License](#license)

## Quick start

You don't need an API key. The model responses from the live runs are committed in `.cache/`, so a fresh clone replays
them for free.

**Requirements**

| | Needed for |
|---|---|
| Python 3.12 | Everything |
| `ffmpeg` on the PATH | Optional: voice playback (without it, calls show as text) |
| [Meta Model API key](https://dev.meta.ai) | Optional: new model calls, and speech from the portal and crew microphones |

**Install and run** (Windows, PowerShell)

```powershell
git clone https://github.com/MalithaBandara/relight.git
cd relight
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m uvicorn relight.server:app --port 8000
```

**macOS or Linux**

```bash
git clone https://github.com/MalithaBandara/relight.git
cd relight
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn relight.server:app --port 8000
```

> [!IMPORTANT]
> Relight is developed on Windows 11. The macOS and Linux commands above were also run on a fresh clone on GitHub's hosted
> machines (2026-11-05), with no key and no `ffmpeg`: every scenario, the offline checks and the unit tests passed, and the
> pages and their scripts loaded. That check did not cover using the pages in a browser, voice playback, microphones or new
> model calls.

Open <http://localhost:8000>, pick a scenario in the header and press **Run**.

> [!NOTE]
> **The five storm video clips are not in this repository, so they won't show up in a fresh clone.** Their events show
> "video not added yet" and a `mock` label. Everything else replays normally. To see the clips analysed, or to try your
> own, see [Videos](#videos).

## Usage

### Pages

| URL | Who it is for |
|---|---|
| <http://localhost:8000> | Operator: map, work agenda, event log, trouble calls, crews, and switching plans to approve |
| <http://localhost:8000/customer> | Customer: check supply, report a problem, talk to the outage desk |
| <http://localhost:8000/crew> | Field crew: say or type a report, attach a photo, confirm the read-back |

### Scenarios

Eight scenarios run on the same engine. Pick one in the console header, or replay it without the browser using its ID.

| ID | What it shows |
|---|---|
| `galle_storm` | The full story: messages in three languages, a changed diagnosis, switching around a fault, a hidden fuse |
| `houston_hurricane` | Smart meters that fail mid-storm; English and Spanish |
| `chennai_cyclone` | Scale: about 2,400 messages in three languages |
| `house_fuse` | One house dark: one caller, a neighbour asked, a service fault found by elimination |
| `tree_on_line` | One tree on a lateral: about 160 customers, a tree crew then a line crew |
| `hospital_generator` | A hospital's backup generator fails and it calls |
| `ieee123_storm` | Independent test on the IEEE 123-node feeder, with faults from a separate script |
| `two_tie_demo` | Several safe switching plans on an invented feeder with two ties |

### Replay without the browser

```bash
python scripts/run_headless.py galle_storm               # incidents and a check against the scenario's truth
python scripts/run_headless.py galle_storm --timeline    # also print the full event log
python scripts/run_headless.py galle_storm --calls       # also print every voiced call and crew report
python scripts/run_headless.py galle_storm --no-switching  # nobody approves anything: the agent works the storm alone
```

Headless runs approve safe switching plans automatically to exercise that path. The server never does: there, the
operator approves every plan. A run ends by printing what is still dark, for example:

```text
What-if customer-minutes: Relight 68,940 vs first-call-first-served 98,129; live wire made safe after 2 vs 90 min
Still dark at the end: 0 customers (believed); world says 0
```

## Videos

**The five storm clips are not in this repository.** They are third-party footage whose pages state no licence, so they
aren't ours to redistribute. You can see them in the [demo video](https://youtu.be/Wdf_SaKpP8I).

| Clip (where it goes) | Used in | Source |
|---|---|---|
| `media/drone/temple_road_span.mp4` | Galle: drone patrol `D1` | [11Alive, YouTube](https://www.youtube.com/watch?v=ChaqvH8k02g) |
| `media/videos/tree_on_live_line.mp4` | Galle: message `C24`, portal sample | [Jahangir Alam (Linemanbd15), Facebook](https://www.facebook.com/watch/?v=1033433662993562) |
| `media/videos/limb_on_pole.mp4` | Houston: message `C41`, portal sample | [Neil Sackman, Facebook](https://www.facebook.com/watch/?v=2942484986199463) |
| `media/videos/salina_tree_on_pole.mp4` | Houston: message `C282` | [Megan Brandon via KOTV News On 6, Facebook](https://www.facebook.com/watch/?v=1084130850192135) |
| `media/videos/indonesia_tree_explosion.mp4` | Chennai: message `C408`, portal sample | [VBear media, YouTube](https://www.youtube.com/shorts/T0CASmx3fkU) |

### What you see without them

The storms still replay and end the same way: the same faults are found and everyone is restored. For the five events
above:

- The event log shows `mock (ground truth)` and "video not added yet", and the damage type comes from the scenario's label.
- The map marker's popup has no video, no Muse Spark description, no SAM 3.1 tracking and no drone survey.
- The portal's three video sample buttons fill in the message but can't attach a clip, and show "Attach a photo or a video."
- `scripts/cost_report.py` counts no video requests, so its totals come out lower than the [Cost](#cost) table.

### See the clips analysed by the models

This needs a [Meta Model API key](https://dev.meta.ai), `ffmpeg` on the PATH and an internet connection.

1. Add your key as described in [Configuration](#configuration).
2. Download and trim the clips into the paths above (commands for Windows; on macOS or Linux use `.venv/bin/`):

   ```powershell
   .venv\Scripts\pip install yt-dlp
   .venv\Scripts\python scripts\fetch_videos.py
   ```

   If a source has gone offline, the script prints `FAILED` for that clip and carries on. That event stays as a placeholder.
3. Start the server, pick the scenario and press **Run**. When a clip's event comes up, the log shows
   `Muse Spark + SAM 3.1` with what the models read. Click the marker on the map to see the clip and the results.

> [!WARNING]
> The script re-encodes each clip, so a file may not match the committed responses byte for byte. Any clip that doesn't
> match goes to the API as new requests, which are billed. From the runs behind the [Cost](#cost) table, that comes to
> about $0.36 for Galle's two clips, $0.55 for Houston's two and $0.30 for Chennai's one. New results are cached, so later
> replays are free, but they may differ slightly from the figures in this README.

To draw SAM 3.1's outlines over the drone clip after a run (no API calls; it can take a few minutes):

```powershell
.venv\Scripts\python scripts\build_overlays.py media\drone\temple_road_span.mp4
```

### Try your own video

Analysis needs a key. Without one, your clip still goes through, but its result reads "(mock) not analysed yet".

First make the clip small with the command below. Meta's limit for a video sent inline, which is how Relight sends it, is
[50 MB](https://dev.meta.ai/docs/file-handling#size-limits), and short clips work best: our drone clip is 2.3 MB at 10
frames per second. If the event log shows `video analysis failed`, try a shorter clip. At $0.20 per 1,000 frames, tracking
up to four kinds of object through 30 seconds at 10 frames per second costs about 25¢.

```bash
ffmpeg -i my_clip.mp4 -an -vf "scale='min(854,iw)':-2,fps=10" -t 30 -c:v libx264 -crf 30 -preset slow my_clip_small.mp4
```

**From the customer portal (no files to edit):**

1. Start the server, pick a scenario in the console and press **Run**.
2. Open <http://localhost:8000/customer> and go to **Report a problem**.
3. Type a message that names an address on that scenario's feeder. In Galle, for example:
   `Tree on the wires at 20 Hospital Road. Video attached.`
4. Add your clip and send it. Use the MP4 from the command above: the portal also takes MOV and WebM, up to 60 MB, but Meta's
   docs [list only MP4](https://dev.meta.ai/docs/file-handling#supported-file-types) for video.

The result appears under your report, and the clip appears as a marker on the console's map.

**As part of a scenario:** put the clip anywhere under `media/`, restart the server after each edit, and use a path relative
to the repository root.

- For a customer message, edit `"videos"` in `scenarios/calls/<scenario>.json`, using a message's `id` from the scenario:

  ```json
  "videos": {"C24": {"file": "media/videos/my_clip_small.mp4", "damage": "tree_on_line"}}
  ```

  `damage` is only the label used when no model reads the clip.
- For the drone patrol, change the `"file"` of event `D1` in `scenarios/galle_storm.json`.

What the models read from a clip counts as damage evidence, so a different clip can change a run from the numbers in
[Results](#results).

## How it works

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/architecture-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="docs/img/architecture-light.png">
  <img alt="How Relight works. Calls and crew voice reports go to Muse Voice Transcribe, then Muse Spark; calls in languages Voice Transcribe lacks go straight to Muse Spark. SMS, chat, portal messages and BD codes go to Muse Spark. Photos and drone clips go to SAM 3.1, then Muse Spark. Muse Spark's structured reports and damage findings, with SCADA lockouts and smart meters, go to the engine, then the fault tracer, then incidents and priority. From there the agent answers calls, asks questions and sends updates, and it dispatches crews and replans the work. Customers' answers and call-backs and crews' site reports feed back in at the top. Safety-checked switching plans reach the console once the operator approves them." src="docs/img/architecture-light.png">
</picture>

### What each Meta model does

| Model | Job in Relight | Measured |
|---|---|---|
| **Muse Spark** (`muse-spark-1.3`) | Reads every complaint and crew report into a JSON schema (street, house number, symptom, hazard, junk) in five languages. Words the call agent's replies and the dispatcher's explanations. Classifies damage photos and watches drone clips. **Listens directly to calls in a language Voice Transcribe doesn't cover.** Reads pole-number plates. | Accuracy below. `reasoning_effort: minimal` cut extraction latency from 4.4 to 2.4 s and agent-line wording in that language from 9.9 to 2.8 s. |
| **Muse Voice Transcribe** | Phone calls to text (English, Spanish, Hindi etc.), through the file endpoint and a realtime WebSocket line with speaker diarization. The feeder's street names go in as `keywords`. | Street heard right in 11 of 13 clips with keywords against 6 of 13 without. $0.18 per hour of audio. |
| **SAM 3.1** | Outlines poles, wires and fallen trees in photos and tracks them through drone clips. Finds the pole-number plate for Spark to read. Pixel masks (decoded with Meta's `meta-sam-parser`) give pole lean, wire sag and where a fallen tree actually touches the wires. | Temple Road clip: 3 poles and 5 wires followed; the trunk touches 3 of 7 wire tracks by mask. |

The console's **Meta models** panel shows requests, tokens, cost and the share of decisions made by each model, by
code, and by the agent or operator, for the run on screen.

### What deterministic code does

| Step | Where |
|---|---|
| Places each complaint on its service transformer (account, caller ID, address, landmark) | [customers.py](relight/customers.py) |
| Finds which device opened or which line broke: a likelihood search over every protective device, transformer fuse and line, using calls, neighbours' silence, probe answers, meters, SCADA and located damage. Each located device shows the evidence behind it, source by source. | [tracer.py](relight/tracer.py) |
| Asks a customer the question that best separates two explanations; dispatches crews by priority and travel; revises a diagnosis from a crew's report; finds hidden faults after a repair | [engine.py](relight/engine.py), [planner.py](relight/planner.py) |
| Proposes restoration switching (reclose, close a tie, isolate then restore, with several ties) and blocks any plan that would energise a known fault, an unconfirmed fault zone or a crew's work zone | [network.py](relight/network.py) |
| Fact-checks every agent line that Spark words: if a number, time, street or id was dropped or changed, the template is spoken instead | [callagent.py](relight/callagent.py) |
| Looks up a pole from its tag, tolerating look-alike characters (O/0, I/1, S/5, B/8) | [poles.py](relight/poles.py) |
| Texts customers again when their restoration estimate moves by 15 minutes or more, at most once every 30 minutes per event. The message is a fixed template, so a model can't reword the time. | [engine.py](relight/engine.py) |
| Reads `BD`, `OUT` and `PWR <account>` SMS codes | code only, no model call |

## Results

Six of the eight scenarios (Galle, Houston, Chennai, `house_fuse`, `tree_on_line` and `hospital_generator`) ran against
the live Meta Model API, and their responses are committed in `.cache/`, so replays are free. Repeat replays find
the same faults; small details, such as which neighbour is asked, can vary between runs.

| Scenario | Network | Customers | Messages | Faults found | Dark at the end |
|---|---|---|---|---|---|
| **Galle**, Sri Lanka | IEEE 34-bus feeder over Galle | 1,951 | ~69 | 6 of 6 | 0 |
| **Houston**, USA | OpenStreetMap, smart meters that fail mid-storm | 3,044 | ~221 | 7 of 7 | 0 |
| **Chennai**, India | OpenStreetMap, 2,400 messages in three languages | 24,559 | ~2,400 | 9 of 9 | 0 |
| One house dark | one caller; the agent asks a neighbour | 3,044 | ~4 | 1 of 1 | 0 |
| Tree on a line | one lateral, about 160 customers | 3,044 | ~58 | 1 of 1 | 0 |
| Hospital generator | the hospital's backup power fails and it calls | 24,559 | ~294 | 3 of 3 | 0 |
| **Pine Valley**, independent test | IEEE 123-node test feeder, faults from a separate script | 1,658 | 13 | **4 of 5** | **16** |
| Two-tie demo | invented feeder with two ties, one pole down | 229 | 21 | 1 of 1 | 0 |

### What the numbers show

- **Customer minutes.** Against a first-call-first-served schedule, Relight's priority schedule cuts customer-minutes
  interrupted by 30% in Galle (68,940 against 98,129) and 22% in Houston (107,336 against 137,647). A live wire is made
  safe after 2 minutes instead of 90 in Galle. Across nine settings (fewer or extra crews, delayed reports, faster or
  slower baseline patrols) the saving ranges from 12% to 45% in Galle and 18% to 38% in Houston; the report-delay and
  patrol settings change only the baseline.
- **A hospital's generator fails.** The call is read in any language by code and adds 1,500 to the outage's priority. On
  the scenario's labelled readings the hospital moves ahead of a larger outage in the tree crew's queue and is restored 64
  minutes sooner (01:44 against 02:48). On the cached live readings the crew goes to the hospital next with or without
  the call, so there the call changes nothing (01:44 both ways).
- **Independent test.** On the published IEEE 123-node feeder, with faults and complaints generated by a separate script
  (fixed seed, no tracer tuning), Relight found 4 of 5 faults and left 16 customers dark; it missed a tree on a lateral
  that never reached the 80% confidence threshold. We report this as measured, not as a pass mark. The network data is
  the IEEE PES test feeder, read from the annotated OpenDSS file in EPRI's OpenDSS distribution (BSD 3-clause, licence in
  [data/IEEE123Master.LICENSE.txt](data/IEEE123Master.LICENSE.txt)).
- **Switching around a fault.** The IEEE data has no sectionalising switches near its ties, so only one safe plan exists
  there. On the two-tie demo (an invented feeder), one pole down has three safe plans (east tie, north tie, both) and the
  planner recommends the one that restores most customers (186 of the 229).
- **Evidence ablation** (mock mode, each source removed in turn). Removing neighbour-probe questions loses 2 of 6 faults in
  Galle and 1 of 7 in Houston. With calls only, 0 of 6 and 2 of 7 faults are found; with SCADA only, 2 of 6 and 1 of 7.
  Removing silence, SCADA, damage photos or smart meters on their own did not change how many faults were found on these
  storms. Calls alone are not enough, and the neighbour question is the one source whose removal costs faults.

### Muse Spark extraction accuracy

Scored against the scenario's labels on the engine's own live readings. Results are in [eval/](eval/).

| Scenario | Scored | Street | House no. | Symptom | Hazard | Junk |
|---|---|---|---|---|---|---|
| Galle (3 languages) | 47 | 92% | 94% | 92% | 94% | 100% |
| Houston (2 languages) | 161 | 98% | 98% | 99% | 99% | 100% |
| Chennai (3 languages) | 1,692 | 93% | 98% | 97% | 100% | 100% |

Most misses are facts the caller gave only later, or that come from caller ID; the agent confirms each address with the
caller.

### The fact check

Of the agent lines Spark worded in the cached runs, none was rejected: Galle 59 lines, Houston 142 and Chennai 25, across
five languages. Median wait per line was 2.0 to 2.9 s.

## Cost

Usage charges are a small part of what Relight would cost a utility: on the estimate below, model calls and phone lines
come to about $600 to $1,000 for a major storm on a 100,000-customer network. Connecting it to the utility's systems and
running it would probably cost more, and we have not estimated that.

### Measured: the storms in this repository

What one run costs in model calls at [Meta's published prices](https://dev.meta.ai/docs/pricing-rate-limits), with each
unique request counted once. These runs included the storm clips, and the results are in [eval/cost.json](eval/cost.json).
`python scripts/cost_report.py` works from the cache without calling the API, and totals can move by a cent between
replays. It needs the original clips to reach these totals. In a fresh clone, without them, it gives $0.41 for Galle, $0.38
for Houston and $2.76 for Chennai, and overwrites `eval/cost.json` with those figures (see [Videos](#videos)).

| Scenario | Customers | Messages | Spark | Voice Transcribe | SAM 3.1 | **Total** | Per message |
|---|---|---|---|---|---|---|---|
| Galle | 1,951 | 72 | $0.33 | $0.01 | $0.44 | **$0.77** | 1.1¢ |
| Houston | 3,044 | 222 | $0.39 | under $0.01 | $0.55 | **$0.93** | 0.4¢ |
| Chennai | 24,559 | 2,378 | $2.73 | under $0.01 | $0.33 | **$3.06** | 0.13¢ |
| Hospital generator | 24,559 | 294 | $0.52 | none | none | **$0.52** | 0.18¢ |
| Tree on a line | 3,044 | 58 | $0.09 | none | none | **$0.09** | 0.16¢ |
| One house dark | 3,044 | 4 | $0.01 | none | none | **$0.01** | 0.3¢ |

- **Why it is cheap:** the tracer, the safety checks and the planner are code, so they make no model calls. SMS codes need
  no model either, and Spark runs at minimal reasoning effort.
- **Don't read Chennai's rate as a real-world rate.** Only 6 of its 560 calls have audio, and during the surge the agent
  uses templates for the others. Most of the SAM cost is video.
- **The console shows different figures.** Its Meta models panel counts a repeated request each time and shows no cost for
  SAM.

### Estimate: a utility with 100,000 customers

> [!NOTE]
> This is arithmetic on the assumptions below, not a measurement. No utility has run Relight, and real call lengths and
> reporting rates will differ.

**Assumptions for one major storm:** 20% of customers report once (20,000 reports; Chennai's scenario has about 10%), half
by phone and half by text; calls last 3 minutes; and the agent hands 10% of calls to a person. The per-request figures are
set above the highest channel averages we measured: 1.5¢ of Spark per call (the costliest call measured was 1.45¢) and
0.5¢ per text.

| Item | Cost |
|---|---|
| Model calls for one 3-minute call: Spark 1.5¢, Voice Transcribe 0.9¢ | 2.4¢ |
| The same call with its phone line ([$0.0085 local or $0.022 toll-free per minute](https://www.twilio.com/en-us/voice/pricing/us)) | 5¢ to 9¢ |
| 10,000 calls, 10,000 texts and $10 of damage photos and clips | **$555 to $960** |
| 1,000 hard calls answered by people, at $8.01 each | $8,010 |
| **Storm total** | **about $8,600 to $9,000** |

For comparison, the same storm with people answering every call:

| Item | Cost |
|---|---|
| All 10,000 calls answered by people, at $8.01 each | $80,100 |

How that compares with what a utility already pays for:

- **Answering calls.** [Gartner's 2019 poll](https://www.mactech.com/2019/10/18/gartner-only-9-of-customers-report-solving-issues-via-self-service/)
  put live channels at $8.01 per contact and self-service at about $0.10. These are figures across industries, not for
  utilities. At 5¢ to 9¢, an agent call costs about the same as self-service, yet the caller can speak freely in their own
  language. It only saves money if staffing changes. In a storm, the more likely gain is answering calls that would
  otherwise wait or get a busy tone.
- **Sending crews.** Published estimates for one truck roll run [from $150 to over $1,000](https://blitzz.co/blog/the-real-cost-of-a-truck-roll-and-how-to-avoid-it),
  though these come from a vendor and aren't specific to electric utilities. The $555 to $960 is about the price of one to
  six trips. We have not measured how many wasted trips Relight would prevent at a real utility.
- **Smart meters.** Projects in the US Department of Energy's grant program reported
  [$130 to $1,895 per meter](https://www.energy.gov/sites/prod/files/2016/12/f34/AMI%20Summary%20Report_09-26-16.pdf),
  or at least $13 million for 100,000 customers. At five major storms a year, Relight's calls and messages would cost about
  $2,800 to $4,800 a year. It doesn't replace meters, which also handle billing and report outages directly, but a utility
  without them could start from the phone lines it already has.
- **Outages themselves.** Oak Ridge National Laboratory puts the cost of major outages to US customers at
  [more than $67 billion a year on average for 2018 to 2024](https://www.eurekalert.org/news-releases/1118431). The US
  average was [11 hours without power per customer in 2024](https://www.eia.gov/todayinEnergy/detail.php?id=66744). Our
  simulated 22% to 30% cut in customer-minutes comes from synthetic storms, so we don't turn it into a dollar saving.

**Not included:** connecting to the utility's network model, customer records, SCADA and phone system; hosting; licensed
speech synthesis (edge-tts is a demo voice); SMS delivery; security and privacy review; training and support. Any price a
vendor would charge is also left out. A pilot with a utility is the way to measure these.

**Capacity:** [Meta's standard limits](https://dev.meta.ai/docs/pricing-rate-limits) allow 256 Voice Transcribe streams at
once per team, which is about 5,000 three-minute calls an hour. A larger utility would need a higher limit or a queue.

## Limits

- Customers, callers and voices are synthetic. The portal call was tested live with synthetic speech in all five
  languages, and the crew page in English, Hindi and Spanish. Crew reports in the other two languages ran live only as scripted crew calls in the storm scenarios.
- Samples are small. The Voice Transcribe keyword test used 13 clips; two of the language samples in Galle are a handful
  of calls each.
- Lean and wire sag are estimates from one camera view.
- Smart meters are optional and simulated: only Houston has them, and the meter messages are generated, not read from a
  meter data system.
- There is no power-flow model. Relight does not check voltage, current or line capacity, so a plan that uses several
  ties assumes the neighbouring feeder can carry the load.
- Priority weights (for example hospital 400, failed backup power 1,500) are our own choices, not a utility's rules.
- The independent IEEE 123-node test is one synthetic storm run in mock mode, with invented customers and a made-up
  location. It tests the tracer and switching logic on a network shape we did not design; it is not a validation on a
  real utility.
- The server has no sign-in. Anyone who can reach it can use the operator console and file reports as a crew. See
  [Security](#security).

## Configuration

Settings are read from the environment or from a `.env` file in the repository root. All of them are optional.

```bash
cp .env.example .env    # then add your key
```

| Variable | Default | Purpose |
|---|---|---|
| `MODEL_API_KEY` | empty | Meta Model API key. Get one at <https://dev.meta.ai> |
| `MODEL_MODE` | `live` with a key, otherwise `mock` | `mock` never calls the API |
| `META_API_BASE` | `https://api.meta.ai/v1` | API base URL |
| `SPARK_MODEL` | `muse-spark-1.3` | Muse Spark model |
| `TRANSCRIBE_MODEL` | `muse-voice-transcribe-1.0` | Voice Transcribe model |
| `SAM_MODEL` | `sam-3.1` | SAM model |
| `SPARK_EFFORT` | `minimal` | Spark reasoning effort; `off` sends no effort field |

**Without a key**, the app runs in mock mode: the committed model responses in `.cache/` are replayed (a few requests
differ slightly without a key and are not in the cache), and anything not cached falls back to the scenario's labelled
ground truth, tagged `mock` in the console.

> [!WARNING]
> **With a key**, any request that is not in the cache goes to the API and is billed, then it is cached so later replays
> are free. Changing a prompt changes the cache key, so it sends new requests. A full live run of the largest scenario,
> Chennai, cost about $3. Set `MODEL_MODE=mock` to rule out API calls.

## HTTP API

The server is a FastAPI app, so interactive docs for the REST endpoints are at <http://localhost:8000/docs>. The API has
no versioning and may change.

<details>
<summary>Main endpoints</summary>

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/grid` | Feeder GeoJSON, landmarks, crews, customers per transformer, scenario metadata |
| `GET` | `/api/state` | Full engine snapshot |
| `GET` / `POST` | `/api/scenarios`, `/api/scenario` | List scenarios; switch scenario |
| `POST` | `/api/control` | Start, pause, reset or change the replay speed |
| `POST` | `/api/plan` | Operator approves a switching plan |
| `GET` | `/api/customer?q=` | Supply status by account or phone |
| `POST` | `/api/customer/report` | File a customer report |
| `POST` | `/api/customer/call` | Start a call to the outage desk |
| `POST` | `/api/crew/report` | File a crew report; the agent reads it back before it counts |
| `WS` | `/ws` | Snapshot on connect, then live events for the console |

</details>

## Development

### Project layout

```text
relight/     Backend and all logic: engine, tracer, network, planner, call agent, model client, FastAPI server
web/         Console, customer portal and crew page (plain HTML, CSS and JavaScript; no build step)
scenarios/   Scenario definitions; calls/ holds the voiced calls
scripts/     Headless replay, checks, evaluations and generators
tests/       Regression and unit tests
eval/        Saved evaluation results
data/        OpenStreetMap extracts and the IEEE 123-node feeder (customer databases are generated on first use)
media/       Synthetic call audio, photos, overlays and credits
.cache/      Committed model responses, so a keyless clone replays the live runs
```

### Tests

No API key is needed for any of these.

```bash
python -m unittest discover -s tests    # 34 tests with full scenario replays; ~10 minutes on a fresh clone, ~3 after
python scripts/check_offline.py         # fact check, realtime replay, uploads, masks, pole tags; under a minute
```

### Regression baseline

After changing `relight/` or `scenarios/`, the main scenarios must still find every fault and end with everyone restored:

```bash
python scripts/run_headless.py galle_storm          # 6 of 6
python scripts/run_headless.py houston_hurricane    # 7 of 7
python scripts/run_headless.py chennai_cyclone      # 9 of 9
```

The last line of each must read `Still dark at the end: 0 customers (believed); world says 0`.

### Useful scripts

| Script | Purpose |
|---|---|
| `scripts/make_storm.py` | Regenerate storms on OpenStreetMap feeders (fixed seeds) |
| `scripts/make_calls.py` | Synthesise the voiced calls |
| `scripts/fetch_videos.py` | Download the third-party clips (see [Videos](#videos)) |
| `scripts/ablate.py` | Measure fault finding with each evidence source removed |
| `scripts/sensitivity.py` | Sweep crews, reporting delays and patrol times against the baseline |
| `scripts/eval_extraction.py` | Score Spark's extraction; `--replay` scores cached readings for free |
| `scripts/cost_report.py` | Measure model cost per storm and per channel from the cache, and work out the utility estimate; makes no API calls |
| `scripts/smoke_test.py` | One small live call per Meta model (needs a key) |
| `scripts/draw_architecture.py` | Redraw the "How it works" diagram from `docs/img/architecture.mmd` (needs Playwright) |

## Troubleshooting

| Problem | Fix |
|---|---|
| Calls show as text, with no audio | Put `ffmpeg` on the PATH. Agent speech also needs internet access for `edge-tts` |
| The microphone doesn't work on the portal or crew page | Browsers allow it only on `localhost` or HTTPS. Speech also needs a key; without one, type the message |
| Lines tagged `mock` in the console | That request is not in the cache and there is no key, so the scenario's labels were used |
| "video not added yet" in the event log, or "Attach a photo or a video." on a portal video sample | The storm clips are not in the repository. See [Videos](#videos) |
| Lookups don't match the map after changing a network or customer settings | Stop the server, delete the matching `data/*.db` file and restart. It is rebuilt on first use |
| `UnicodeEncodeError` printing non-Latin text on Windows | Set `PYTHONIOENCODING=utf-8` |
| Python changes have no effect | The commands above run without `--reload`, so restart the server |

## What's next

Relight runs on a simulated utility today. The next step is a real one: connect to the channels customers already use
(SMS gateway, WhatsApp, web and app messages, phone lines with hand-over to a human), read the utility's own network model
and customer records, test with real callers and photos, and replace our priority rules with the utility's. The
operator keeps approving every switching plan, and the agent never operates equipment. None of this is built; it needs a
utility partner and privacy and security review before any real customer data is used.

## Security

Relight is a demo and is not hardened for deployment. It has no sign-in, so run it only on `localhost` or a trusted
network, and never connect it to real customer data or real grid equipment. A real deployment must identify operators
and crews.

Keep your API key in `.env`, which is git-ignored. To report a security problem, open an
[issue](https://github.com/MalithaBandara/relight/issues) without including any secrets.

## Contributing

This is a solo hackathon entry. Bug reports are welcome through
[GitHub Issues](https://github.com/MalithaBandara/relight/issues). Before suggesting a change to the engine, run the
[tests and regression baseline](#development).

## Credits and data

- **Maps:** © OpenStreetMap contributors (ODbL). Feeders for Houston and Chennai run along real streets; real facilities
  appear only under generic names such as "Hospital on &lt;street&gt;".
- **IEEE 123-node test feeder:** IEEE PES Distribution System Analysis Subcommittee; file from EPRI's OpenDSS
  distribution, BSD 3-clause ([licence](data/IEEE123Master.LICENSE.txt)). Customers and street names on it are synthetic.
  The IEEE 34-bus feeder used for Galle is the same family of published test feeders.
- **Photos and clips:** third-party, credited in [media/photos/CREDITS.md](media/photos/CREDITS.md) and
  [media/videos/CREDITS.md](media/videos/CREDITS.md). Two images are AI-generated and labelled as such.
- **Voices:** Microsoft edge-tts, synthetic.
- **Models:** Muse Spark, Muse Voice Transcribe and SAM 3.1 through the Meta Model API; SAM masks decoded with Meta's
  `meta-sam-parser`.

## License

Relight's code is licensed under the [Apache License 2.0](LICENSE). Copyright 2026 Malitha Bandara.

The licence doesn't cover third-party material, which keeps its own terms: OpenStreetMap data (ODbL), the IEEE 123-node
feeder file (BSD 3-clause), photos and clips (see [Credits and data](#credits-and-data)), and Python dependencies,
including `meta-sam-parser` (SAM License). The synthetic voices and cached model responses were produced with third-party
services, whose terms also apply.
