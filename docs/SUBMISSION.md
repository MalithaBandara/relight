# Submission text and final checklist

## Title

Relight: an AI outage agent for electric utilities

## One line

Meta's models read calls, photos and drone clips in five languages; deterministic code finds the failed device and plans
safe restoration; the operator approves.

## Description (paste into the form; about 250 words)

When a storm cuts power, a utility without smart meters learns where the fault is mostly from phone calls, in several
languages, while crews wait for a location. Relight turns that flood into located faults, safe switching plans, crew
dispatch and customer updates.

Meta models do the reading. Muse Voice Transcribe hears calls in Tamil, Hindi, Spanish and English, with the feeder's
street names as keywords (street heard right in 11 of 13 clips against 6 of 13 without). Voice Transcribe has no
Sinhala, so Muse Spark listens to those calls itself. Spark turns every message into a structured report (street, house
number, symptom, hazard; 91-97% street accuracy against labelled scenarios), words the call agent's replies and checks
them against the facts code chose, and classifies damage photos. SAM 3.1 outlines poles, wires and fallen trees in
photos and drone clips, finds pole-number plates, and its masks give pole lean, wire sag and where a tree actually
touches a wire.

Code decides. A probabilistic tracer searches the feeder for the device that explains who is dark and who is not,
asks a customer the question that best separates two explanations, and revises its diagnosis when a crew reports
differently. Restoration switching is simulated step by step and blocked if it would energise a fault or a crew's
work zone; the operator approves every plan.

Three scenarios run end to end: Galle (6 of 6 faults found), Houston with failing smart meters (7 of 7), and Chennai at
about 2,400 messages (9 of 9), with nobody left dark. All customers and voices are synthetic; maps are OpenStreetMap.
Limits are stated in the README.

## Built with

Muse Spark, Muse Voice Transcribe, SAM 3.1 (Meta Model API); Python, FastAPI, Leaflet, OpenStreetMap, edge-tts for the
synthetic voices.

## Links

- Code: https://github.com/MalithaBandara/relight
- Video: (add after upload)

## Disclosures to keep in the form and the video

- Idea first explored in the earlier GridMedic project (Jaseci Labs hackathon, 17 Oct 2026); Relight is new code written
  from Oct 29 with no reuse.
- Synthetic voices are Microsoft edge-tts; Meta has no text-to-speech model.
- Third-party damage photos and clips are credited in `media/`.
- Meta Model API in Standard mode, synthetic or public data only.

## Final checklist (owner)

Before the video
- [ ] Listen to a few voiced calls; tell the agent which sound wrong
- [ ] Send the pole-tag photo (with street and house number) and the blown-fuse photo, if still wanted
- [ ] Sinhala native-speaker check of the lines you will show on screen
- [ ] Decide: adopt keywords and/or minimal reasoning effort in the engine (re-runs Galle ~$1.1, Houston ~$1.5), or leave
- [ ] `git status` clean, `git push`, repo public, README renders (Mermaid diagram shows)

Recording (Nov 3)
- [ ] Follow `docs/DEMO.md`; footer text visible in every shot
- [ ] Voice-over under 3:00 total; export 1080p MP4
- [ ] Check the video shows: Spark, Voice Transcribe, SAM 3.1 each at work, the operator approving a plan, the Meta models panel

Submission (by Nov 4, 10 PM Sri Lanka time; hard limit Nov 5, 7:30 AM)
- [ ] Upload video; add its link above
- [ ] Track: Indie; theme: Push the Frontier
- [ ] Paste title, one line, description, links, disclosures
- [ ] Open the repo link while logged out to confirm it is public and `.env` is not in it
- [ ] Submit on Cerebral Valley and save the confirmation
