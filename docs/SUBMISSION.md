# Submission form answers and final checklist

One answer per form field, in the form's order. Each paragraph is one long line, so it pastes without stray line breaks.
Copy what is inside each block.

## Team Name

Relight

## Team Members

Only the owner. Do not add anyone.

## Track

Indie Developer Track

## Problem statement

Push the Frontier

## Most Viral Track (X post link, optional)

Leave empty unless an X post about Relight exists.

## Project Description

```text
When a storm cuts power, a utility without smart meters learns where the fault is mostly from phone calls, in several languages, while crews wait for a location. Relight is an AI outage agent that turns that flood of reports into located faults, safe switching plans, crew dispatch and customer updates.

It answers every call in the caller's language (English, Sinhala, Tamil, Hindi or Spanish) and reads text messages, damage photos, drone clips and crew voice reports. Meta's models read; deterministic code decides. A probabilistic tracer finds the device that explains who is dark and who is not, asks a neighbour when two explanations compete, and changes its diagnosis when a crew reports something different. Restoration switching is simulated step by step and blocked if it would energise a known fault or a crew's work zone. An operator approves every plan, and hard calls such as a live wire go to a person.

Results on simulated storms: Galle found 6 of 6 faults, Houston with failing smart meters 7 of 7, and Chennai with about 2,400 messages 9 of 9, with nobody left dark. On an independent IEEE 123-node test it found 4 of 5 and left 16 customers dark. Model calls for the largest storm cost about $3. For a 100,000-customer utility we estimate 5 to 9 cents per agent-answered call, phone line included. That estimate leaves out integration and hosting.

Relight is a prototype and no utility has tested it. All customers, voices and meter messages are synthetic, and maps are OpenStreetMap. Third-party photos and clips are credited in the repository, and two images are AI-generated and labelled. All code was written during the event, from Oct 29, 2026. The idea was first explored in GridMedic, an earlier team project (Jaseci Labs hackathon, Oct 17, 2026); no code was reused.
```

## Public GitHub Repository

```text
https://github.com/MalithaBandara/relight
```

## 3-Minute Demo Video

The public or unlisted YouTube link, opened once while logged out to check it plays.

## Describe your use of Meta products to build the submitted project

```text
Relight uses three Meta models through the Meta Model API in Standard mode, each for a different job.

Muse Spark reads every complaint and crew report into a JSON schema: street, house number, symptom, hazard, junk. Scored against scenario labels in five languages, street accuracy is 92 to 98% and hazard accuracy 94 to 100%. It listens to Sinhala calls directly from the audio, because Sinhala goes to Spark rather than Voice Transcribe. It words the call agent's replies in the caller's language, and code rejects any line that drops or changes a number, time, street or ID; none of the 226 lines it worded in the cached runs was rejected. Spark also explains each located fault to the dispatcher, suggests the next line to a human call-taker, classifies damage photos, watches clips and reads pole-number plates. Setting reasoning_effort to minimal cut extraction latency from 4.4 to 2.4 seconds.

Muse Voice Transcribe hears calls and crew reports in Tamil, Hindi, Spanish and English, through the file endpoint and a realtime WebSocket line with speaker diarization, so words appear while the caller speaks. The feeder's street and landmark names go in as keywords: the street was heard right in 11 of 13 clips with them and 6 of 13 without (a small sample).

SAM 3.1 outlines and tracks poles, wires and fallen trees in photos and drone clips, and finds the pole-number plate for Spark to read, so the pole can be named from a register. Its masks, decoded with Meta's meta-sam-parser, give pole lean, wire sag and where a tree actually touches a wire: in the Temple Road clip the trunk touches 6 of 10 wire tracks.

The three main storms used about 1,900 model requests. The responses are committed to the repository, so anyone can replay the live runs without a key, and the console's Meta models panel shows the requests made in each run.
```

## Why are Meta's models important to your solution?

```text
Relight's main sensor is people. A utility without smart meters learns about a fault from calls, messages, photos and crew reports, in whatever language and words people use. Keyword rules cannot turn that into evidence across five languages and free speech. Meta's models can, and without them Relight could read only SMS codes, SCADA alarms and smart meters.

One family of models covers every way people report a fault. Voice Transcribe hears speech as it happens, Spark reads text and also listens to Sinhala audio directly, and SAM 3.1 sees damage down to the pixel. Features of the models solve problems specific to this domain: the grid's street names become Voice Transcribe keywords, Spark's JSON schemas give the tracer facts it can use, and SAM's masks show where a tree touches a wire.

They also make the system safe to build on, because their output can be checked. A model never chooses the fault or approves a switch. Models produce structured evidence, deterministic code locates the fault and plans the switching, and an operator approves. Code rejects any Spark-worded line that changes a number, time, street or ID.

The price makes this practical for a utility. Model calls for our largest storm, with 2,378 messages and 24,559 customers, cost about $3. A utility that cannot yet afford smart meters could start from the phone lines it already has.
```

## Provide feedback from your experience using partner technologies (optional)

```text
I did not use the partner platforms. Relight runs directly on the Meta Model API and uses no self-hosted open-weights models.
```

## Final checklist (owner)

Before submitting
- [ ] Open the repo link while logged out to confirm it is public and shows the Cost section
- [ ] Upload the final video and open its link while logged out
- [ ] After pasting each long answer, check that its last sentence is still there (the boxes show no limit, but one may be hidden)

Submission (by Nov 4, 10 PM Sri Lanka time; hard limit Nov 5, 7:30 AM)
- [ ] Press Submit on Cerebral Valley and save the confirmation
