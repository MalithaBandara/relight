# Video credits

Third-party clips of real storm damage, used as example customer videos and a drone patrol in the fictional
scenarios. They are not ours to redistribute, so the files are git-ignored; `scripts/fetch_videos.py` downloads
and trims them (needs `pip install yt-dlp` and ffmpeg). Credit the source on screen wherever a clip appears, e.g.
"Video: 11Alive (YouTube)", and caption it as an example: none was filmed in Galle, Houston or Chennai.

| File | Used for | Shows | Source |
|---|---|---|---|
| `media/drone/temple_road_span.mp4` | Galle: drone patrol D1 over the Temple Road spans | Drone following a line along a road; a broken branch lies across the wires (Hurricane Zeta, 2020). Trimmed to 0:30–1:02, 11Alive watermark kept | 11Alive, "Drone video shows tree on power line after Zeta", [YouTube](https://www.youtube.com/watch?v=ChaqvH8k02g) |
| `media/videos/tree_on_live_line.mp4` | Galle: WhatsApp C24 (Temple Road 100); portal sample "tree on fire (video)" | Branch burning on a high-voltage line, sparks | Jahangir Alam (Linemanbd15), [Facebook](https://www.facebook.com/watch/?v=1033433662993562) |
| `media/videos/indonesia_tree_explosion.mp4` | Chennai: WhatsApp C408, tree on the line, Velachery Bypass Road; portal sample | Arc flash in a tree by a concrete pole, filmed from a car in heavy rain (Padang Batung, Indonesia) | VBear media, [YouTube](https://www.youtube.com/shorts/T0CASmx3fkU) |
| `media/videos/limb_on_pole.mp4` | Houston: app message C41, Westview Drive tree; portal sample | Broken limb hanging on top of a pole, at night | Neil Sackman, [Facebook](https://www.facebook.com/watch/?v=2942484986199463) |
| `media/videos/salina_tree_on_pole.mp4` | Houston: app message C282, blown fuse on Voss Road | Bright flashes across a parking lot in a storm (the "bang and flash" customers report) | Megan Brandon via KOTV News On 6 / Tess Maune, [Facebook](https://www.facebook.com/watch/?v=1084130850192135) |

None of the pages states a licence. The owner decided to use them in this non-commercial hackathon demo
(2026-10-30) unless a source asks otherwise; if one does, delete the file and remove its entry from
`scenarios/calls/*.json` (the message then falls back to its text alone).
