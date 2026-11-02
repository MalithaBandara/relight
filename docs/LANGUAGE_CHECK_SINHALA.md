# Sinhala language check

For a native Sinhala speaker. Each row is something the agent, a customer or a crew says or writes in the demo. Tell us whether it is correct and natural; if not, write the version you would say. Words in `{curly braces}` are filled in by the program (a street, a time, a number, a kind of fault) and stay as they are. The English column is only the intended meaning. Fictional people and places; the demo voices are synthetic.

Most important first: the safety lines (`safety_live`, `safety_down`, `safety_fire`, `known_hazard`) and the greeting.


## 1. What the agent says on a call

| Key | Sinhala | English meaning | OK? / correction |
|---|---|---|---|
| `greet` | විදුලි බිඳවැටීම් අංශයයි. ඔබ කතා කරන්නේ ස්වයංක්‍රීය සහායකයෙකු සමඟයි. කරුණාකර ඔබේ ලිපිනය හෝ ගිණුම් අංකය, සහ සිදු වූ දේ කියන්න. | Outage desk. You are speaking with an automated assistant. Please tell me your address or account number, and what is happening. | |
| `confirm_address` | මා සතුව ඇති ඔබේ ලිපිනය {address}. විදුලිය නැත්තේ එතැනද? | I have your address as {address}. Is that where the power is out? | |
| `ask_address` | ඔබේ ලිපිනය සොයාගත නොහැකි විය. කරුණාකර නිවසේ අංකය සහ පාර, නැත්නම් ගිණුම් අංකය කියන්න. | I could not find your address. Please tell me your house number and street, or your account number. | |
| `ask_hazard` | ඔබ අසල කැඩුණු කණු, වැටුණු වයර් හෝ ගස් පේනවාද? කරුණාකර ඒවා අසලට යන්න එපා. | Can you see any fallen poles, wires or trees near you? Please do not go near them. | |
| `known_hazard` | ඔබ අසල {what} ගැන අපට දැනටමත් වාර්තාවක් ලැබී ඇත. කරුණාකර ඒ අසලට යන්න එපා, වයර්වල විදුලිය ඇති බව සලකන්න. | We already have a report of {what} near you. Please keep away from it and treat any wires as live. | |
| `ask_neighbour` | දෝෂය සොයා ගැනීමට එක ප්‍රශ්නයක්: {address} නිවෙස්වල දැන් විදුලිය තිබේද? | One quick question to help us find the fault: do the houses at {address} have power right now? | |
| `safety_live` | කරුණාකර වයරයෙන් අවම වශයෙන් මීටර් දහයක් ඈතින් සිටින්න, අනෙක් අයවත් ඈත් කරන්න. එහි විදුලිය ඇති බව සලකන්න. එය ආරක්ෂිත කිරීමට කණ්ඩායමක් එවනවා. | Please stay at least ten metres away from the wire and keep others away. Treat it as live. We are sending a crew to make it safe. | |
| `safety_down` | කරුණාකර වැටුණු කණුව සහ වයර් අසලට යන්න එපා. ඒවායේ විදුලිය ඇති බව සලකන්න. | Please keep away from the fallen pole and wires, and treat them as live. | |
| `safety_fire` | ගින්නක් තිබේ නම්, වහාම ගිනි නිවන සේවයට අමතන්න. | If anything is on fire, call the fire service now. | |
| `escalate` | මෙය හදිසි ලෙස අපේ පාලන මැදිරියට දැනුම් දුන්නා. | I have flagged this to our control room as urgent. | |
| `status_enroute` | මෙම විදුලි බිඳවැටීම ගැන අපි දන්නවා ({kind}). කණ්ඩායමක් එමින් සිටිනවා. විදුලිය නැවත ලැබීමට ආසන්න වේලාව {eta}. | We know about this outage ({kind}). A crew is on the way. Estimated restoration around {eta}. | |
| `status_onsite` | මෙම විදුලි බිඳවැටීම ගැන අපි දන්නවා ({kind}). කණ්ඩායමක් දැන් එහි වැඩ කරනවා. විදුලිය නැවත ලැබීමට ආසන්න වේලාව {eta}. | We know about this outage ({kind}). A crew is working on it now. Estimated restoration around {eta}. | |
| `status_waiting` | මෙම විදුලි බිඳවැටීම ගැන අපි දන්නවා ({kind}). ඉක්මනින් කණ්ඩායමක් යොදවනවා. විදුලිය නැවත ලැබීමට ආසන්න වේලාව {eta}. | We know about this outage ({kind}). A crew will be assigned shortly. Estimated restoration around {eta}. | |
| `status_locating` | ස්තූතියි, ඔබේ පැමිණිල්ල සටහන් කළා. අපි දෝෂය සොයමින් සිටිනවා, විදුලිය ලැබෙන වේලාව කෙටි පණිවිඩයකින් දන්වනවා. | Thank you, your report is recorded. We are locating the fault and will send you a text with the restoration time. | |
| `status_restored_dark` | අපේ වාර්තා අනුව ඔබේ ප්‍රදේශයට {at} ට විදුලිය ලබා දුන්නා. ඔබේ නිවසට තවමත් විදුලිය නැති බව සටහන් කළා; අපි තවත් දෝෂයක් සොයනවා. | Our records show power was restored in your area at {at}. I have recorded that your house is still without power; we are checking for a second fault. | |
| `repeat` | ඔබ මෙය {at} ට දැනටමත් දැනුම් දුන්නා, ස්තූතියි. | You already reported this at {at}, thank you. | |
| `junk` | මෙම ඇමතුම් අංකය විදුලි බිඳවැටීම් සඳහා පමණයි. වෙනත් කරුණු සඳහා කාර්යාල වේලාවේ අමතන්න. | This line is for power outages only. For anything else, please call during office hours. | |
| `sms_fallback` | සමාවන්න, ඇමතුම තේරුම් ගත නොහැකි විය. කරුණාකර {code} සහ ඔබේ ගිණුම් අංකය කෙටි පණිවිඩයක් ලෙස එවන්න. | Sorry, I could not understand the call. Please send a text message: {code} and your account number. | |
| `close` | ඇමතුවාට ස්තූතියි. | Thank you for calling. | |
| `readback` | පාලන මැදිරියෙන්. නැවත කියවන්නම්: {summary}. හරිද? | Control here. Reading back: {summary}. Correct? | |
| `crew_changed` | හරි. දෝෂය {kind} ලෙස වෙනස් කර වැඩ නැවත සැලසුම් කළා. | Copy. I have changed the diagnosis to {kind} and replanned the work. | |
| `crew_logged` | හරි, {incident} යටතේ සටහන් කළා. | Copy, logged against {incident}. | |
| `crew_unmatched` | හරි, සටහන් කළා. ඒ ස්ථානයට ගැළපෙන විදුලි බිඳවැටීමක් තවම නැහැ. | Copy, logged. No open outage matches that location yet. | |
| `crew_text` | සමාවන්න, ලයින් එක පැහැදිලි නැහැ. කරුණාකර වාර්තාව කෙටි පණිවිඩයකින් එවන්න. | Sorry, the line is bad. Please send the report as a text message. | |
| `transfer` | මම දැන් ඔබව පාලන මැදිරියේ නිලධාරියෙකුට සම්බන්ධ කරනවා. කරුණාකර රැඳී සිටින්න. | I am putting you through to a control-room operator now. Please stay on the line. | |
| `ask_medical` | ඔබේ නිවසේ කවුරුහරි විදුලියෙන් ක්‍රියා කරන වෛද්‍ය උපකරණයක් භාවිතා කරනවාද? | Is anyone at the address using medical equipment that needs power? | |

## 2. What a caller answers the agent (simulated)

| Key | Sinhala | English meaning | OK? / correction |
|---|---|---|---|
| `address` | අංක {house}, {street}. | Number {house}, {street}. | |
| `account` | මගේ ගිණුම් අංකය {account}. | My account number is {account}. | |
| `yes` | ඔව්. | Yes. | |
| `no` | නැහැ. | No. | |
| `pole_down` | ඔව්, අංක {house} ළඟ කණුවක් වැටිලා. | Yes, a pole has fallen near number {house}. | |
| `live_wire` | ඔව්, වයරයක් බිම වැටිලා ගිනි පුපුරනවා. | Yes, there's a wire down and it's sparking. | |
| `wire_down` | ඔව්, වයරයක් බිම වැටිලා තියෙනවා. | Yes, there's a wire on the ground. | |
| `tree_on_line` | ඔව්, ගහක් වයර් උඩට වැටිලා. | Yes, a tree has come down on the wires. | |
| `fire` | ඔව්, කණුව ළඟ මොකක්දෝ පිච්චෙනවා. | Yes, something is burning near the pole. | |
| `hazard_no` | නැහැ, එහෙම දෙයක් පේන්නේ නැහැ. | No, I can't see anything like that. | |
| `neighbour_on` | ඔව්, එයාලට විදුලිය තියෙනවා. | Yes, they have power. | |
| `neighbour_off` | නැහැ, එයාලටත් නැහැ. | No, they're dark too. | |
| `readback_ok` | හරි. | Correct. | |
| `readback_wrong` | නැහැ. ආයෙත් කියන්නම්: {report} | Negative. Again: {report} | |
| `medical_yes` | ඔව්, මෙහෙ කෙනෙක් ඔක්සිජන් යන්ත්‍රයක් පාවිච්චි කරනවා. | Yes, someone here is on an oxygen machine. | |
| `medical_no` | නැහැ, එහෙම කවුරුත් නැහැ. | No, nobody here needs that. | |

## 3. Text messages the desk sends

`kind` is the kind of fault, `eta` the restoration time.

| Key | Sinhala | English meaning | OK? / correction |
|---|---|---|---|
| `question` | විදුලි දෝෂ අංශය: ඔබේ ප්‍රදේශයේ දෝෂයක් සොයමින් සිටිමු. දැන් ඔබේ නිවසේ විදුලිය තිබේද? ඔව් හෝ නැත ලෙස පිළිතුරු දෙන්න. | Outage desk: we are locating a fault near you. Is the power on at your home right now? Reply YES or NO. | |
| `notice` | විදුලි දෝෂ අංශය: ඔබේ සැපයුමට බලපාන දෝෂය සොයාගෙන ඇත ({kind}). කණ්ඩායමක් යොදවා ඇත. විදුලිය නැවත ලැබීමට ආසන්න වේලාව {eta}. | Outage desk: we have found the fault affecting your supply ({kind}). A crew is assigned. Estimated restoration around {eta}. | |
| `restored` | විදුලි දෝෂ අංශය: ඔබේ ප්‍රදේශයට විදුලිය නැවත ලබා දී ඇත. තවමත් විදුලිය නැත්නම් මෙම පණිවිඩයට පිළිතුරු දෙන්න. | Outage desk: power has been restored in your area. If you are still without power, reply to this message. | |
| `followup` | අසල්වැසියන්ට විදුලිය ආවා, අපිට තවම නැහැ. {street} {house}. | The neighbours have power again but our house is still dark. {street} {house}. | |

## 4. A customer's reply to the desk's question (yes/no)

| Key | Sinhala | English meaning | OK? / correction |
|---|---|---|---|
| `power on` | ඔව්, අපේ ගෙදර විදුලිය තියෙනවා. | Yes, our power is on. | |
| `power off` | නැහැ, අපිටත් විදුලිය නැහැ. | No, we have no power here either. | |

## 5. Hazard names the agent uses

| Key | Sinhala | English meaning | OK? / correction |
|---|---|---|---|
| `pole_down` | වැටුණු කණුවක් | a fallen pole | |
| `live_wire` | විදුලිය සහිත වයරයක් | a live wire | |
| `wire_down` | වැටුණු වයරයක් | a fallen wire | |
| `tree_on_line` | වයර් මත වැටුණු ගසක් | a tree on the lines | |
| `fire` | ගින්නක් | a fire | |

## 6. The crew report the agent reads back

The agent builds a sentence from these pieces and says it to the crew to confirm.

| Key | Sinhala | English meaning | OK? / correction |
|---|---|---|---|
| `damage.pole_down` | කණුවක් වැටිලා | pole down | |
| `damage.tree_on_line` | ගසක් වයර් මත | tree on the line | |
| `damage.live_wire` | විදුලිය සහිත වයරයක් බිම | live conductor down | |
| `damage.wire_down` | වයරයක් බිම | wire down | |
| `damage.blown_fuse` | ට්‍රාන්ස්ෆෝමර් ෆියුස් එක පිච්චිලා | blown transformer fuse | |
| `damage.transformer_failure` | ට්‍රාන්ස්ෆෝමරය අක්‍රියයි | failed transformer | |
| `damage.service_wire` | සර්විස් වයරය කැඩිලා | service wire down | |
| `damage.none` | හානියක් නැහැ | no damage found | |
| `damage.other` | හානියක් | damage | |
| `at` | {where}: {what} | {what} at {where} | |
| `near` | {street} අංක {house} අසල | {street} near number {house} | |
| `here` | ඔබ සිටින තැන | your location | |
| `live` | ලයින් එකේ විදුලිය තියෙනවා | the line is live | |
| `device_ok` | අපි ඔබව යැවූ උපකරණය හොඳ තත්ත්වයේ | the device we sent you to is healthy | |
| `houses` | නිවාස {a} සිට {b} දක්වා විදුලිය නැහැ | houses {a} to {b} without supply | |
| `needs` | ඔබට {list} අවශ්‍යයි | you need {list} | |
| `and` |  සහ  |  and  | |
| `sep` | ;  | ;  | |
| `crews.line` | ලයින් කණ්ඩායමක් | a line crew | |
| `crews.bucket_truck` | බකට් ට්‍රක් එකක් | a bucket truck | |
| `crews.vegetation` | ගස් කපන කණ්ඩායම | the vegetation crew | |
| `crews.troubleshooter` | තාක්ෂණ නිලධාරියෙක් | a troubleshooter | |

## 7. What a crew says on arrival at a site

| Key | Sinhala | English meaning | OK? / correction |
|---|---|---|---|
| `pole_down` | {street} අංක {house} අසල ඉන්නවා. කොන්ක්‍රීට් කණුව කැඩිලා, වයර් පාර හරහා වැටිලා. කණුව මාරු කරන්න පටන් ගන්නවා. | On site at {street} near number {house}. Concrete pole snapped, conductors down across the road. Starting pole replacement. | |
| `tree_on_line` | {street} අංක {house} අසල ඉන්නවා. ලොකු ගහක් වයර් උඩට වැටිලා. ලයින් වැඩට කලින් ඒක අයින් කරනවා. | On site at {street} near number {house}. A tree is lying across the conductors. Clearing it before the line work. | |
| `live_wire` | {street} අංක {house} අසල ඉන්නවා. පාරේ තියෙන වයරයේ විදුලිය තියෙනවා. ප්‍රදේශය වට කළා, දැන් ආරක්ෂිත කරනවා. | On site at {street} near number {house}. The conductor on the road is live. Area cordoned off, making it safe now. | |
| `blown_fuse` | {street} අංක {house} අසල ට්‍රාන්ස්ෆෝමර් {xf} ළඟ ඉන්නවා. ඩ්‍රොප්-අවුට් ෆියුස් එක පිච්චිලා. දැන් මාරු කරනවා. | On site at transformer {xf} on {street} near number {house}. The drop-out fuse is blown. Replacing it now. | |
| `service_wire` | {street} අංක {house} අසල ඉන්නවා. | On site at {street} near number {house}. | |
| `contradict_service_wire` | {street} ට්‍රාන්ස්ෆෝමර් {xf} හොඳින්, ෆියුස් හරි. අංක {house} ළඟ අත්තක් වැටිලා සර්විස් වයරය කැඩිලා, ඒ නිසා නිවාස {a} සිට {b} දක්වා විතරයි විදුලිය නැත්තේ. සර්විස් වයරයට ලයින් කණ්ඩායමක් ඕනේ. | Transformer {xf} on {street} is fine, its fuses are intact. The service wire is down at number {house} after a branch fell, so only houses {a} to {b} have no supply. Need a line crew for the service wire. | |
| `contradict_blown_fuse` | මෙතන ලයින් එක හොඳින්. {street} අංක {house} ළඟ ට්‍රාන්ස්ෆෝමර් {xf} එකේ ඩ්‍රොප්-අවුට් ෆියුස් එක තමයි පිච්චිලා තියෙන්නේ. | The line is fine here. It is the drop-out fuse on transformer {xf} near {street} number {house} that has blown. | |
| `nothing` | {label} ළඟ ඉන්නවා. මෙතන හානියක් නැහැ, ලයින් එක හොඳින්. | On site at {label}. No damage found here; the line looks healthy. | |

## 8. Sinhala messages and calls in the Galle scenario

What the fictional Galle customers and crews say or send. Voiced calls are read by the synthetic Sinhala voices.

English meanings below are the developer's own reading, so please correct them too.

| Id | How | Sinhala | English meaning | OK? / correction |
|---|---|---|---|---|
| C02 | whatsapp (voiced) | හලෝ, මම කතා කරන්නේ රෝහල පාරේ අංක 47 ඉඳන්. කරන්ට් නැහැ. ලොකු සද්දයක් ආවා, කණුවක් වැටිලා වගේ. | Hello, I am calling from number 47, Hospital Road. No power. There was a big noise; it seems a pole has fallen. | |
| C08 | whatsapp | තවමත් කරන්ට් නැහැ. අංක 47. | Still no power. Number 47. | |
| C20 | whatsapp | පන්සල ළඟ ලොකු ගහක් වයර් උඩට වැටිලා. අපේ ගෙදර විදුලිය නැහැ, ටෙම්පල් පාර 70. | A big tree has fallen onto the wires near the temple. No power at our house, Temple Road 70. | |
| C09 | sms | Hospital rd 30 current na. kawadda enne? | Hospital Road 30, no power. When will it come? | |
| C38 | whatsapp | පන්සල අසල විදුලිය නැහැ | No power near the temple. | |
| C32 | whatsapp | පොළ ළඟ පාරේ වයර් එකක් වැටිලා ගිනි පුපුරු එනවා. මාර්කට් වීදිය 10. | A wire has fallen on the road near the market and is giving off sparks. Market Street 10. | |
| C24 | whatsapp | temple road 100 light na | Temple Road 100, no power. | |
| C15 | sms | Hospital rd 30 thama current na | Hospital Road 30, still no power. | |
| C51 | whatsapp | ලේක් පාර අංක 12 විදුලිය නැහැ | Lake Road number 12, no power. | |
| C29 | whatsapp | සිනමන් ගාඩන්ස් පටුමග අංක 60 විදුලිය නැහැ | Cinnamon Gardens Lane number 60, no power. | |
| C41 | whatsapp | ඔයාලා හරියට වැඩ කරන්නේ නැහැ!!! | You people are not working properly!!! (an angry message, not about an outage) | |
| CREW-V1 | crew language | (their reports use the sentences in section 7) | | |
| CREW-T1 | crew language | (their reports use the sentences in section 7) | | |
