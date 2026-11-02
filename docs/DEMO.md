# Demo video plan (3:00 hard limit)

Record Nov 3. Motion graphics are added on top afterwards (see "Motion graphics"). Screen capture of the console on **Galle** at 1920x1080, voice-over by the owner, no music needed.
Start the server, open `http://localhost:8000/?run=10` (it presses Run at 10x after the page connects) or press Run by
hand. Everything is replayed from the cache, so each take is identical and costs nothing. Check the header shows
**LIVE** (or says MOCK honestly if recorded without the key) and keep the footer line visible: it says customers are
fictional and voices synthetic.

Before recording: restart the server (no `--reload`), pick **Galle** in the header, press Reset, close other tabs, set
the browser zoom to 100%, and play the voiced calls once so edge-tts has cached the lines (first synthesis takes
6-16 s a line; the cache is `media/audio/tts/`).

## Shot list and voice-over

Times are the scenario clock on screen (15:00 start) and a running length for the video. The storm replays at 10x, so
about 1 s of video is 10 s of storm; pause and speed up around the beats. Cut or time-lapse the quiet stretches
(the clock box shows "Time-lapse: crews working" by itself while crews repair).

| # | Video | On screen | Voice-over |
|---|---|---|---|
| 1 | 0:00-0:12 | Console, empty map of Galle, footer visible. Hit Run. Calls start appearing. | "When a storm takes the power out, the utility doesn't know where the fault is. It knows that phones are ringing: in English, Sinhala, Tamil. This is Relight, an outage agent built on Meta's models." |
| 2 | 0:12-0:35 | Click **Agent calls**. Open call C02 (Sinhala): play the caller's line, the agent's reply, the English gloss. | "A caller speaks Sinhala. Voice Transcribe has no Sinhala, so Muse Spark listens to the audio itself. The agent answers in Sinhala; Spark words the reply, but code chooses every fact in it, and a fact check throws a line away if Spark changes a number or a street." |
| 3 | 0:35-1:00 | Map: I1 Hospital Road recloser appears with 95%. Click it; details show the reasons. Log shows `Code` locating, `Muse Spark` explaining. | "No model guesses where the fault is. Calls, silence from the neighbours, SCADA, all go into a probabilistic tracer. It finds a recloser lockout on Hospital Road: 95% confident, crew dispatched. Models read; code locates and decides." |
| 4 | 1:00-1:20 | The live-wire call C31. Hazard H2 appears; it ranks above every outage. Open the damage photo popup (the tagged pole, C61: SAM finds the plate, Spark reads GL-0417, the register names the pole). | "A sparking wire is ranked above every outage and escalated. A photo of a snapped pole goes to SAM 3.1, which finds the number plate, and Spark reads it: the pole is named, not guessed." |
| 5 | 1:20-1:50 | Temple Road (I2). Open the drone popup: the SAM overlay video (poles blue, wires amber, the tree red) and the survey text. Then the **switching plan** card: show a blocked plan, press Approve on "isolate then restore". Power restored to 115 customers. | "A drone clip: SAM 3.1 tracks the poles, the wires and the fallen trunk. Relight offers switching plans, blocks any that would energise a fault, and waits for the operator. I approve; 115 customers are back before the crews finish." |
| 6 | 1:50-2:10 | Lake Road I5: the log line "Mind changed". Then the late hidden-fuse incident (T-059) after the pole repair. | "Crews report by voice and the agent reads it back. A crew says the transformer is fine, the service wire is down: Relight changes its diagnosis. After the last repair, callers who are still dark reveal a second fault hidden behind the first." |
| 7 | 2:10-2:30 | Open `/customer`: the **Check my supply** card, then **Talk to the outage desk** (use the typed path unless the microphone has been tested, see risks). Then `/crew`: pick a crew, send a report, the agent reads it back, tap **Correct**. | "Customers and crews are not only in the replay. A customer can check their supply or ring the desk; a crew can send a report by voice, and the agent reads it back. Nothing changes until the crew says it is correct." |
| 8 | 2:30-2:45 | Header: pick **hospital_generator**, Run at 20x. Show the call where the hospital says its generator has failed; the log shows its outage jumping the queue (restored 64 minutes sooner than without the call). | "Here a hospital's generator fails. The call is read by code in any language, the outage jumps the queue, and the hospital is back 64 minutes sooner. The operator can see why." |
| 9 | 2:45-2:55 | Open **Meta models**. Read out requests and the split bar. Footer visible. | "Muse Spark did the reading, Voice Transcribe heard the calls, SAM 3.1 saw the damage. Code made every decision. Customers are fictional, voices are synthetic. Spark reads the street right 91% of the time in Galle, 97% in Houston." |
| 10 | 2:55-3:00 | Title card: Relight, repo URL. | "Relight. Meta models read. Code decides. github.com/MalithaBandara/relight." |

This cut runs to the 3:00 limit. If the first edit comes out long, cut in this order: shot 8, then the portal half of
shot 7, then the photo half of shot 4. Each cut still leaves the decision loop and the Meta models on screen.

Words to keep out of the voice-over: anything that claims how a real utility operates, any real utility name, "replaces
the call centre". Say what was measured and that the sample is small.

## Motion graphics (Remotion)

Built as a small Remotion project in `video/` (React compositions, previewed in Remotion Studio; rendered only when the
owner asks for the MP4). The screen recording is the base layer; graphics are overlays on top of it, so every shot still
shows the real console. Rule: a graphic only shows a number or a flow that the product really produced, and nothing is
animated that implies a capability Relight does not have.

| Graphic | Where | What it shows | Source of truth |
|---|---|---|---|
| Opening title | Shot 1, 0:00-0:04 | "Relight" wipes in over the dark map; one line: "Meta models read. Code locates and decides." | text only |
| "Read / Decide" flow | Shot 3, 0:40-0:55 | Calls, SMS, SCADA, photos fly into the tracer box and out comes "Hospital Road recloser, 95%"; the Meta models are lit blue, code is grey. | README architecture diagram |
| Lower thirds | Shots 2-8 | One-line captions (list below) slide in and out, with the model's name in its colour (Spark purple, Voice Transcribe blue, SAM green, as on the console). | captions list |
| Callout rings | Shots 3, 4, 5 | A ring pulses on the recloser, the pole-tag plate and the blocked switching plan, with a short label ("95%", "GL-0417", "blocked: would energise a fault"). | console state at that time |
| Counters | Shots 5, 9 | "115 customers restored" counts up; the Meta models split bar fills to the real request counts from the panel. | Meta models panel |
| Before/after bar | Shot 8 | Two bars, "without the call 02:48" and "with the call 01:44", the gap labelled "64 minutes". | `hospital_generator` run (`run_headless.py`) |
| Accuracy bars | Shot 9 | Spark street accuracy: Galle 91%, Houston 97%, with "small sample" under them. | README Results |
| End card | Shot 10, 2:55-3:00 | Relight, the repo URL, "Customers are fictional; voices are synthetic." | text only |

Timing and style: 30 fps, 1920x1080, each graphic 0.4 s in and 0.4 s out with an ease-out curve, nothing on screen longer
than the voice-over line it supports, no sound effects. Use the console's own type and colours so the overlays look like
part of the product, not a template. Keep a 60 px safe margin and never cover the footer line that says the data is
fictional.

Build order (so the video is never blocked): 1) title and end cards, 2) lower thirds, 3) the numbers (counters, bars)
with the real values read from the repo, 4) the read/decide flow, 5) callout rings once the screen recording exists and the
positions are known. If time runs short, stop after step 3: the recording alone is already a complete demo.

## On-screen captions (burn in, one line each)

1. `Demo data: customers are fictional, voices are synthetic`
2. `Voice Transcribe has no Sinhala, so Muse Spark listens to the audio`
3. `Muse Spark reads. Code locates and decides.`
4. `Fact check: a Spark line that changes a number or street is discarded`
5. `SAM 3.1 masks: pole lean, wire sag, where the tree touches`
6. `The operator approves every switching plan`
7. `Diagnosis changed from the crew's voice report`
8. `Hidden second fault found from calls after restoration`
9. `Meta models panel: requests, tokens, cost`
10. `Customer and crew pages: the agent reads back, the crew confirms`
11. `Hospital generator failed: its outage jumps the queue`

## Retakes and risks

- If the Sinhala line mispronounces a street, use a different call (C01 English) for shot 2 and keep one Sinhala
  clip short. Voices were never checked by a native listener; ask the owner before using a Tamil or Hindi clip.
- Do not run live calls on camera unless the key and network have been tested the same day: handshake is 3-5 s.
- Keep the time-lapse short; judges rank the top five from the video alone, so every shot must show Meta models or the
  decision loop.
- The portal call and crew page microphones have not been tested with the live API: on camera use the typed path, or ask
  for a GO test first. Both pages must be opened on `localhost` (the microphone needs it).
- Shot 8 switches scenario: do it on a cut, and press Reset first. It is cached in mock mode only if the owner has not
  asked for a live run; its call lines are scenario labels (`mock (ground truth)`), so say so if shown.
- The microphone copilot path needs real speech on camera and has not been tested live: skip it.
- Check the footer and header text are legible at 1080p before the final take.
