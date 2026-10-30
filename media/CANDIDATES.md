# Media candidates: damage photos and a drone clip

Candidates for the photo path (Spark classifies the damage, SAM 3.1 outlines pole and wire, code estimates
wire clearance) and for drone damage assessment (SAM 3.1 video tracking).

**Status (2026-10-30):** nine photos are downloaded and wired into the scenarios; see `photos/CREDITS.md` for
which file is used where. #3 (Lockett, a transmission structure) and #5 (Bartow, wire barely visible) were dropped
after viewing. The drone clip is still open: the owner is finding one.

Licences were read from each file's source page on 2026-10-30. Re-check the page before downloading.
Credit every image in the README and on screen where it appears, e.g. "Photo: Liz Roll / FEMA, public domain".

Licence key, easiest first:
- **PD**: public domain, no conditions (credit anyway).
- **CC BY**: credit, link the licence, say if changed.
- **CC BY-SA**: as CC BY, and an image we change (a SAM overlay burned into the picture) must carry the
  same licence. Fine for a public repo; avoid if unsure.
- **CC BY-NC**: non-commercial only. Fine for the hackathon, not for a product.

## Damage photos (Wikimedia Commons)

No open dataset of storm damage to *distribution* lines turned up; these individual photos are the best
match. Mapped to Relight's damage kinds (`pole_down`, `tree_on_line`, `wire_down`, `live_wire`, `blown_fuse`).

### Recommended set (public domain or CC BY)

| # | Shows | Fits | Size | Licence | Author / source |
|---|---|---|---|---|---|
| 1 | Utility pole snapped after a tree brought the wires down, Hurricane Sandy, Kutztown PA (2012) | `pole_down` + `tree_on_line` | 3072×2304 | **PD** | Dough4872 · [file](https://commons.wikimedia.org/wiki/File:Hurricane_Sandy_snapped_utility_pole_Kutztown_PA.jpg) |
| 2 | Lineman inspects a wire taken out by Hurricane Ike, Port Arthur TX (2008) | `wire_down`, crew on site | 4438×2757 | **PD** (FEMA) | Liz Roll / FEMA · [file](https://commons.wikimedia.org/wiki/File:FEMA_-_38497_-_A_lineman_checks_downed_power_lines_in_Texas.jpg) |
| 3 | EF3 tornado damage to power lines near Lockett TX (2022), NWS damage survey photo | `pole_down` / `wire_down` | 4032×3024 | **PD** (NWS) | NWS Norman · [file](https://commons.wikimedia.org/wiki/File:EF3_damage_to_power_lines_near_Lockett,_Texas.jpg) |
| 4 | Downed power pole and lines across Hugh Street, Townsville, Cyclone Yasi (2011) | `pole_down`, wire across a road | 2703×1867 | CC BY 2.0 | Rob and Stephanie Levy · [file](https://commons.wikimedia.org/wiki/File:Downed_power_pole_and_lines_on_Hugh_Street_in_Townsville.jpg) |
| 5 | Downed trees and power lines, Hurricane Ian, Bartow FL (2022) | `tree_on_line` | 4032×2806 | CC BY 2.0 | State Farm · [file](https://commons.wikimedia.org/wiki/File:Downed_trees_and_power_lines_in_Bartow,_FL_following_Hurricane_Ian.jpg) |
| 6 | Downed power lines after Hurricane Beryl, New Caney TX (2024); fits the Houston scenario | `wire_down` | 5760×3840 | CC BY 2.0 | Jill Carlson · [file](https://commons.wikimedia.org/wiki/File:Downed_power_lines_near_New_Caney,_TX,_after_Hurricane_Beryl.jpg) |
| 7 | Severely damaged pole with power lines hanging, tornado, Winston-Salem NC (1989) | `pole_down` | 2960×2112 | CC BY 4.0 | Nicole Johnson · [file](https://commons.wikimedia.org/wiki/File:Severely_damaged_utility_pole_and_suspended_power_lines_-_May_5_1989_Winston-Salem_NC.jpg) |
| 8 | Transformer down after a tornado, Carrollton, New Orleans (2007) | `blown_fuse` stand-in (transformer damage) | 2816×2112 | CC BY 2.5 (or GFDL) | Infrogmation · [file](https://commons.wikimedia.org/wiki/File:Tornado13Feb07CarrolltonTransformerdown.jpg) |

### Also good, share-alike licence

| # | Shows | Fits | Size | Licence | Author / source |
|---|---|---|---|---|---|
| 9 | Fallen tree resting on utility wires, Ulster Avenue, Walden NY, derecho (2018) | `tree_on_line` (clearest tree-on-wire shot) | 7012×4396 | CC BY-SA 3.0 (or GFDL) | Daniel Case · [file](https://commons.wikimedia.org/wiki/File:Tree_on_wires_along_Ulster_Avenue,_Walden,_NY,_following_May_2018_derecho.jpg) |
| 10 | Power pole leaning over Lakeland Road, Hurricane Irma, Valdosta GA (2017) | `pole_down` (leaning; good for clearance) | 5184×3456 | CC BY-SA 4.0 | Michael Rivera · [file](https://commons.wikimedia.org/wiki/File:Power_pole_leaning_over_Lakeland_Road_after_Hurricane_Irma,_Valdosta,_Georgia.jpg) |
| 11 | Downed branch and damaged power lines, derecho, Hatboro PA (2020) | `tree_on_line` | 4032×3024 | CC BY-SA 4.0 | Dough4872 · [file](https://commons.wikimedia.org/wiki/File:Downed_tree_branch_and_damaged_power_lines_from_6-3-2020_derecho_Hatboro_PA.jpeg) |
| 12 | Downed power lines and trees, Storm Sandy, Arlington VA (2012) | `tree_on_line` | 3648×2736 | CC BY-SA 2.0 | Arlington County · [file](https://commons.wikimedia.org/wiki/File:Storm_Downed_power_lines_and_trees_from_Storm_Sandy_(8138919297).jpg) |

More to browse (107 files, licences vary per file):
[Category:Damaged utility poles](https://commons.wikimedia.org/wiki/Category:Damaged_utility_poles),
[Category:Downed power lines](https://commons.wikimedia.org/wiki/Category:Downed_power_lines).
The FEMA files there (names starting "FEMA - ") are public domain.

**Suggested pick:** #1 (pole + tree), #4 (wire across a road, the live-wire hazard shot), #5 or #9 (tree on line),
#2 (crew on site). Not checked by eye: the Commons thumbnails would not load in the agent's browser, so
look at each one before choosing. A live wire needs to be a clear, unbroken span for SAM to outline and for
code to measure its height above the road.

**Honesty note for the video:** these are real storms in real places. The demo scenarios are fictional, so
caption them as "example damage photo (Wikimedia Commons)" rather than presenting them as the customer's
own photo of Galle, Houston or Chennai.

## Drone clip

No openly licensed **drone** clip of storm-damaged *distribution* lines turned up. Options, best first:

| Option | What it is | Licence | Notes |
|---|---|---|---|
| A. DVIDS: [Coast Guard drone B-roll after Hurricane Ian](https://www.dvidshub.net/video/859865/coast-guard-drone-b-roll-post-hurricane-ian) | 59 s real drone footage, Pine Island FL, 4 Oct 2022 | **PD** | Must be watched to confirm lines or poles are in shot. High-res download needs a free DVIDS account (owner). Show the DVIDS disclaimer: "The appearance of U.S. Department of War (DoW) visual information does not imply or constitute DoW endorsement." |
| B. DVIDS: [DHS disaster B-roll](https://www.dvidshub.net/video/928734/disaster-b-roll) | 5 min 47 s: Arkansas tornadoes (0:00), Hurricane Ian (1:51) | **PD** | Aerial shots not confirmed; check the tornado and Ian segments. Same disclaimer as A. |
| C. Pexels: undamaged lines from a drone, e.g. [power lines and countryside](https://www.pexels.com/video/drone-aerial-view-of-power-lines-and-countryside-30750792/), [power lines at mountains](https://www.pexels.com/video/aerial-video-of-power-lines-at-mountains-5061305/) | Clean drone shots of lines and towers | Pexels licence (free use and editing; check the page) | No damage, so the honest demo is "SAM tracks every pole and span; no damage found" or a sag reading. Mostly transmission lines, not street poles. |
| D. Muse Wonder (Meta, allowed but unused) | Generate a short drone-style clip of a storm-damaged street line | Ours | Adds a fifth Meta model. Must be labelled "synthetic clip, generated with Muse Wonder" on screen. Needs the API key. |
| E. Wikimedia Commons: [NJ nor'easter drone flight](https://commons.wikimedia.org/wiki/File:NJ_Nor%27easter_Drone_Flight_Video_(DJI_Mavic_Pro).webm) | 4 min of 4K drone footage over Bergen County during a snowstorm | CC BY 3.0 (not yet reviewed on Commons) | No damage described; snow scenes. Weak fit. |

Not usable: news drone footage (ABC, WPXI, KBSI and others) and utility videos (Duke Energy) are copyrighted.

**Suggested pick:** check A and B first (real damage, public domain). If neither shows lines clearly, choose
between C (real but undamaged) and D (damaged but synthetic, and another Meta model in use).

## Open datasets (for testing SAM, not for the video)

| Dataset | What | Licence | Use |
|---|---|---|---|
| [TTPLA](https://github.com/R3ab/ttpla_dataset) | Aerial images of transmission towers and power lines, pixel-level COCO masks | Apache-2.0 | Score SAM's line masks against ground truth. Transmission, not street poles. |
| [InsPLAD](https://github.com/andreluizbvs/InsPLAD) | 10,607 drone images of line assets, 17 classes; defects: corrosion, broken parts, bird nests | CC BY-NC 3.0 | Asset detection with real defects; non-commercial only. |
| [Roboflow utility poles](https://universe.roboflow.com/yue-hung/utility-pole-5j6dp) | 511 street-level utility pole images | CC0 per search listing (page refused the agent; verify) | Pole detection at street level. |
