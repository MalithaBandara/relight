# Voice-over for Google AI Studio (Gemini TTS)

A rewrite of `docs/VOICEOVER.md`, cut to the finished video: one block per picture, so each line lands on what it describes.
The current video still uses the older narration until these clips are generated and placed.

## How to generate it

- **Model:** `gemini-3.8-flash-tts`.
- **Voice:** one prebuilt voice for every clip. Audition **Charon** (Informative) first, then **Sadaltager** (Knowledgeable) and
  **Gacrux** (Mature). Google gives these descriptors only, so choose by ear.
- **Style field:** paste this same text for every clip, and change nothing between clips:

```text
calm, warm documentary narration, confident and unhurried, with quiet intensity
```

- **Text field:** paste one block below, exactly as written. This model reads the text as a verbatim transcript, so never put
  directions in it. Everything in angle brackets is an audio tag, and words in capitals are stressed.
- **One clip per block.** Name each file by its block ID. Listen to the first clip before generating the rest.
- **If a clip runs over its slot:** regenerate it first. If it still runs over, add "speaking a little faster" to the style for
  that clip only.
- **If you use the older `gemini-3.1-flash-tts-preview`:** its tags use square brackets, so change `<short pause>` to `[short pause]`.

## The script

### B01 | 0:10 to 0:15 | 5.0 s | the town's phones, all busy

```text
She isn't alone. Thousands call at once. The fire waits on hold.
```

### B02 | 0:15 to 0:22 | 7.0 s | reports rise over the houses

```text
This is Relight. Calls, texts, photos, drone clips, smart meters: each one is a clue.
```

### B03 | 0:22 to 0:28 | 6.0 s | model badges flick on

```text
Voice Transcribe hears them. Muse Spark reads them. SAM three point one sees the damage.
```

### B04 | 0:28 to 0:38 | 10.0 s | pulses climb the wires, faults lock in

```text
Then code traces every report up the wires, and pinpoints exactly what failed, even down to one fuse.
```

### B05 | 0:38 to 0:46 | 8.0 s | crews drive out

```text
Relight sends the right crew to each fault, the most critical first.
```

### B06 | 0:48 to 0:54 | 6.0 s | the agent's call in the console

```text
Every caller reaches an agent that knows the outage, the crew and the hazards.
```

### B07 | 0:54 to 0:58 | 4.0 s | the robot at the whiteboard

```text
Spark words the reply. Code checks every number and name.
```

### B08 | 0:58 to 1:01.8 | 3.8 s | the Spanish call opens; its audio follows

```text
The agent replies in the caller's language. Here, Spanish.
```

### B09 | 1:09 to 1:13 | 4.0 s | dots along the line, counting to 95%

```text
Now the hard part: where did it break?
```

### B10 | 1:13 to 1:24 | 11.0 s | the evidence bars

```text
Code compares who called, who didn't, and what the grid's own alarm says. It names the failed device, and Spark explains why. Here, it's ninety-five percent sure.
```

### B11 | 1:22.8 to 1:25.8 | 3.0 s | the phone rings, and is picked up

```text
Remember her call? This time, someone answers.
```

### B12 | 1:25.8 to 1:29.3 | 3.5 s | words appear as the caller speaks

```text
Voice Transcribe writes the words as they're spoken.
```

### B13 | 1:29.3 to 1:37.8 | 8.5 s | hand-over, Spark's suggestion, report filed

```text
A live wire is no job for a bot. A person takes over, and Spark suggests the next line.
```

### B14 | 1:37.8 to 1:44.8 | 7.0 s | the snapped pole and its plate

```text
SAM three point one finds the plate. Spark reads it. Now we know which pole.
```

### B15 | 1:44.8 to 1:50.8 | 6.0 s | the drone overlay

```text
In a crew's drone clip, SAM three point one shows the tree on the wires.
```

### B16 | 1:50.8 to 1:56.6 | 5.8 s | two plans marked BLOCKED

```text
Relight tests each way to reroute the power, and blocks the unsafe ones.
```

### B17 | 1:56.6 to 1:59.8 | 3.2 s | Approve is clicked

```text
An operator approves the final one.
```

### B18 | 1:59.8 to 2:05.8 | 6.0 s | light runs around the fault, counter to 115

```text
A hundred and fifteen customers get power back, while the tree is still down.
```

### B19 | 2:05.8 to 2:12.7 | 6.9 s | "Mind changed" in the log

```text
Spark hears a crew in their own language: the transformer's fine, a service wire is down. Relight changes its diagnosis.
```

### B20 | 2:12.7 to 2:16.7 | 4.0 s | power returns, one pole stays red

```text
The lights come back. <long pause> Except here.
```

### B21 | 2:16.7 to 2:19.7 | 3.0 s | the new incident appears

```text
Their calls reveal a hidden fault.
```

### B22 | 2:19.7 to 2:25.5 | 5.8 s | the progress card, then the report options

```text
Customers track repairs live, and report by call, text, photo or video.
```

### B23 | 2:25.5 to 2:27.8 | 2.3 s | the crew page's read-back

```text
Crews get their jobs, and report from the field.
```

### B24 | 2:27.8 to 2:31.2 | 3.4 s | the hospital's call, then the top of the agenda

```text
A hospital calls. Its backup generator has failed.
```

### B25 | 2:31.2 to 2:36 | 4.8 s | the queue jump, ending on 64

```text
Relight puts the hospital first: power back sixty-four minutes sooner.
```

### B26 | 2:36 to 2:42 | 6.0 s | the Meta models panel

```text
Three Meta models did the reading: Spark, Voice Transcribe and SAM three point one.
```

### B27 | 2:42 to 2:46.8 | 4.8 s | the counts, "Meta models read. Code decides."

```text
Meta's models read. Code decides. A person approves.
```

### B28 | 2:53 to 2:58.8 | 5.8 s | her lights come on, then the title

```text
Relight. <short pause> Hears the call. Finds the fault. Brings the light back.
```

## Other voice in the story

The busy message at 0:08 stays as it is in the video (`output/busy.mp3`). The woman does not speak.
