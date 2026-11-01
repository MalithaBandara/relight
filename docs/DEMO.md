# Demo video plan (2:45 target, 3:00 hard limit)

Record Nov 3. Screen capture of the console on **Galle** at 1920x1080, voice-over by the owner, no music needed.
Start the server, open `http://localhost:8000/?run=10` (it presses Run at 10x after the page connects) or press Run by
hand. Everything is replayed from the cache, so each take is identical and costs nothing. Check the header shows
**LIVE** (or says MOCK honestly if recorded without the key) and keep the footer line visible: it says customers are
fictional and voices synthetic.

Before recording: restart the server (no `--reload`), pick **Galle** in the header, press Reset, close other tabs, set
the browser zoom to 100%, and play the voiced calls once so edge-tts has cached the lines (first synthesis takes
6-16 s a line; the cache is `media/audio/tts/`).

## Shot list and voice-over

Times are the storm clock on screen (15:00 start) and a running length for the video. The storm replays at 10x, so
about 1 s of video is 10 s of storm; pause and speed up around the beats. Cut or time-lapse the quiet stretches
(the clock box shows "Time-lapse: crews working" by itself while crews repair).

| # | Video | On screen | Voice-over |
|---|---|---|---|
| 1 | 0:00-0:15 | Console, empty map of Galle, footer visible. Hit Run. Calls start appearing. | "When a storm takes the power out, the utility doesn't know where the fault is. It knows that phones are ringing: in English, Sinhala, Tamil. This is Relight, an outage agent built on Meta's models." |
| 2 | 0:15-0:45 | Click **Agent calls**. Open call C02 (Sinhala): play the caller's line, the agent's reply, the English gloss. | "A caller speaks Sinhala. Voice Transcribe has no Sinhala, so Muse Spark listens to the audio itself. Code places her from her caller ID. The agent answers in Sinhala; Spark words the reply, but code chooses every fact in it, and a fact check throws a line away if Spark changes a number or a street." |
| 3 | 0:45-1:15 | Map: I1 Hospital Road recloser appears with 95%. Click it; details show the reasons. Log shows `Code` locating, `Muse Spark` explaining. | "No model guesses where the fault is. Calls, silence from the neighbours, SCADA, all go into a probabilistic tracer. It finds a recloser lockout on Hospital Road: 95% confident, crew dispatched. Models read; code locates and decides." |
| 4 | 1:15-1:45 | The live-wire call C31. Hazard H2 appears; it ranks above every outage. Show the escalation alarm, then the copilot panel if time allows. Open the damage photo popup: SAM outline, lean angle. | "A caller reports a sparking wire in the market. The agent says the safety line, code ranks the hazard above every outage and escalates. Photos go to Spark and SAM 3.1, which outlines the pole and measures its lean from the mask." |
| 5 | 1:45-2:15 | Temple Road (I2). Open the drone popup: the SAM overlay video (poles blue, wires amber, the tree red) and the survey text. Then the **switching plan** card: show a blocked plan, press Approve on "isolate then restore". Power restored to 115 customers. | "A drone clip: SAM 3.1 tracks the poles, the wires and the fallen trunk, and the masks show which wires the tree really touches. Relight offers switching plans, blocks any that would energise a fault, and waits for the operator. I approve; 115 customers are back before the crews finish." |
| 6 | 2:15-2:35 | Lake Road I5: the log line "Mind changed". Then the late hidden-fuse incident (T-059) after the pole repair. | "Crews report by voice and the agent reads it back. A crew says the transformer is fine, the service wire is down: Relight changes its diagnosis. After the last repair, callers who are still dark reveal a second fault that was hidden behind the first." |
| 7 | 2:35-2:50 | Open **Meta models**. Read out requests and the split bar. Footer visible. | "Across the Galle storm Muse Spark did the reading, Voice Transcribe heard the calls, SAM 3.1 saw the damage. Code made every decision. All customers are fictional, the voices are synthetic. The models are measured in the README: Spark reads the street right 91% of the time, 97% in Houston." |
| 8 | 2:50-3:00 | Title card: Relight, repo URL. | "Relight. Meta models read. Code decides. Github dot com slash MalithaBandara slash relight." |

Words to keep out of the voice-over: anything that claims how a real utility operates, any real utility name, "replaces
the call centre". Say what was measured and that the sample is small.

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

## Retakes and risks

- If the Sinhala line mispronounces a street, use a different call (C01 English) for shot 2 and keep one Sinhala
  clip short. Voices were never checked by a native listener; ask the owner before using a Tamil or Hindi clip.
- Do not run live calls on camera unless the key and network have been tested the same day: handshake is 3-5 s.
- Keep the time-lapse short; judges rank the top five from the video alone, so every shot must show Meta models or the
  decision loop.
- The microphone copilot path needs real speech on camera and has not been tested live: skip it.
- Check the footer and header text are legible at 1080p before the final take.
