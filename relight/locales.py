"""Per-country details: names, number formats, languages and the messages Relight sends.

The engine is the same everywhere; only these words and formats change. Customer names
and numbers are synthetic. Non-English texts should be checked by a native speaker.
"""

from __future__ import annotations


# ---- the call agent's lines and the simulated callers' answers -------------------------------------
# The agent chooses what to say in code (act); these are its fixed words per act. Safety lines are never
# rewritten by a model. {kind} stays in English inside non-English lines, as in the SMS notices.

def _agent_en(desk: str, fire: str) -> dict:
    return {
        "greet": f"{desk}. You are speaking with an automated assistant. Please tell me your address or account "
                 "number, and what is happening.",
        "confirm_address": "I have your address as {address}. Is that where the power is out?",
        "ask_address": "I could not find your address. Please tell me your house number and street, or your "
                       "account number.",
        "ask_hazard": "Can you see any fallen poles, wires or trees near you? Please do not go near them.",
        "known_hazard": "We already have a report of {what} near you. Please keep away from it and treat any wires "
                        "as live.",
        "ask_neighbour": "One quick question to help us find the fault: do the houses at {address} have power "
                         "right now?",
        "safety_live": "Please stay at least ten metres away from the wire and keep others away. Treat it as live. "
                       "We are sending a crew to make it safe.",
        "safety_down": "Please keep away from the fallen pole and wires, and treat them as live.",
        "safety_fire": fire,
        "escalate": "I have flagged this to our control room as urgent.",
        "status_enroute": "We know about this outage ({kind}). A crew is on the way. Estimated restoration around "
                          "{eta}.",
        "status_onsite": "We know about this outage ({kind}). A crew is working on it now. Estimated restoration "
                         "around {eta}.",
        "status_waiting": "We know about this outage ({kind}). A crew will be assigned shortly. Estimated "
                          "restoration around {eta}.",
        "status_locating": "Thank you, your report is recorded. We are locating the fault and will send you a text "
                           "with the restoration time.",
        "status_restored_dark": "Our records show power was restored in your area at {at}. I have recorded that "
                                "your house is still without power; we are checking for a second fault.",
        "repeat": "You already reported this at {at}, thank you.",
        "junk": "This line is for power outages only. For anything else, please call during office hours.",
        "sms_fallback": "Sorry, I could not understand the call. Please send a text message: {code} and your "
                        "account number.",
        "close": "Thank you for calling.",
        # Crew reports by phone or radio, in the crew's language.
        "readback": "Control here. Reading back: {summary}. Correct?",
        "crew_changed": "Copy. I have changed the diagnosis to {kind} and replanned the work.",
        "crew_logged": "Copy, logged against {incident}.",
        "crew_unmatched": "Copy, logged. No open outage matches that location yet.",
        "crew_text": "Sorry, the line is bad. Please send the report as a text message.",
    }


_CREW_SI = {
    "readback": "පාලන මැදිරියෙන්. නැවත කියවන්නම්: {summary}. හරිද?",
    "crew_changed": "හරි. දෝෂය {kind} ලෙස වෙනස් කර වැඩ නැවත සැලසුම් කළා.",
    "crew_logged": "හරි, {incident} යටතේ සටහන් කළා.",
    "crew_unmatched": "හරි, සටහන් කළා. ඒ ස්ථානයට ගැළපෙන විදුලි බිඳවැටීමක් තවම නැහැ.",
    "crew_text": "සමාවන්න, ලයින් එක පැහැදිලි නැහැ. කරුණාකර වාර්තාව කෙටි පණිවිඩයකින් එවන්න.",
}
_CREW_TA = {
    "readback": "கட்டுப்பாட்டு அறை. திரும்பச் சொல்கிறேன்: {summary}. சரியா?",
    "crew_changed": "சரி. கோளாறை {kind} என்று மாற்றி, வேலையை மீண்டும் திட்டமிட்டுள்ளேன்.",
    "crew_logged": "சரி, {incident} இல் பதிவு செய்தேன்.",
    "crew_unmatched": "சரி, பதிவு செய்தேன். அந்த இடத்துக்குப் பொருந்தும் மின் தடை இன்னும் இல்லை.",
    "crew_text": "மன்னிக்கவும், லைன் தெளிவாக இல்லை. அறிக்கையை குறுஞ்செய்தியாக அனுப்புங்கள்.",
}
_CREW_ES = {
    "readback": "Aquí control. Repito: {summary}. ¿Correcto?",
    "crew_changed": "Entendido. Cambié el diagnóstico a {kind} y replanifiqué el trabajo.",
    "crew_logged": "Entendido, registrado en {incident}.",
    "crew_unmatched": "Entendido, registrado. Todavía no hay un apagón que coincida con ese lugar.",
    "crew_text": "Disculpe, la línea está mala. Por favor envíe el reporte por mensaje de texto.",
}
_CREW_HI = {
    "readback": "कंट्रोल रूम से। दोहरा रहा हूँ: {summary}। सही है?",
    "crew_changed": "ठीक है। मैंने खराबी को {kind} में बदल दिया है और काम दोबारा तय किया है।",
    "crew_logged": "ठीक है, {incident} में दर्ज कर लिया।",
    "crew_unmatched": "ठीक है, दर्ज कर लिया। उस जगह से मिलती कोई बिजली कटौती अभी नहीं है।",
    "crew_text": "माफ़ कीजिए, आवाज़ साफ़ नहीं है। कृपया रिपोर्ट SMS से भेजिए।",
}

# Words for the read-back of a crew report, built from Spark's structured reading.
READBACK = {
    "en": {"damage": {"pole_down": "pole down", "tree_on_line": "tree on the line", "live_wire": "live conductor down",
                      "wire_down": "wire down", "blown_fuse": "blown transformer fuse",
                      "transformer_failure": "failed transformer", "service_wire": "service wire down",
                      "none": "no damage found", "other": "damage"},
           "at": "{what} at {where}", "near": "{street} near number {house}", "here": "your location",
           "live": "the line is live", "device_ok": "the device we sent you to is healthy",
           "houses": "houses {a} to {b} without supply", "needs": "you need {list}", "and": " and ", "sep": "; ",
           "crews": {"line": "a line crew", "bucket_truck": "a bucket truck", "vegetation": "the vegetation crew",
                     "troubleshooter": "a troubleshooter"}},
    "si": {"damage": {"pole_down": "කණුවක් වැටිලා", "tree_on_line": "ගසක් වයර් මත", "live_wire": "විදුලිය සහිත වයරයක් බිම",
                      "wire_down": "වයරයක් බිම", "blown_fuse": "ට්‍රාන්ස්ෆෝමර් ෆියුස් එක පිච්චිලා",
                      "transformer_failure": "ට්‍රාන්ස්ෆෝමරය අක්‍රියයි", "service_wire": "සර්විස් වයරය කැඩිලා",
                      "none": "හානියක් නැහැ", "other": "හානියක්"},
           "at": "{where}: {what}", "near": "{street} අංක {house} අසල", "here": "ඔබ සිටින තැන",
           "live": "ලයින් එකේ විදුලිය තියෙනවා", "device_ok": "අපි ඔබව යැවූ උපකරණය හොඳ තත්ත්වයේ",
           "houses": "නිවාස {a} සිට {b} දක්වා විදුලිය නැහැ", "needs": "ඔබට {list} අවශ්‍යයි", "and": " සහ ", "sep": "; ",
           "crews": {"line": "ලයින් කණ්ඩායමක්", "bucket_truck": "බකට් ට්‍රක් එකක්", "vegetation": "ගස් කපන කණ්ඩායම",
                     "troubleshooter": "තාක්ෂණ නිලධාරියෙක්"}},
    "ta": {"damage": {"pole_down": "மின்கம்பம் விழுந்துள்ளது", "tree_on_line": "மரம் கம்பிகள் மேல் விழுந்துள்ளது",
                      "live_wire": "மின்சாரம் உள்ள கம்பி கீழே கிடக்கிறது", "wire_down": "கம்பி கீழே கிடக்கிறது",
                      "blown_fuse": "டிரான்ஸ்ஃபார்மர் ஃபியூஸ் போயிருக்கிறது",
                      "transformer_failure": "டிரான்ஸ்ஃபார்மர் பழுதாகியுள்ளது",
                      "service_wire": "சர்வீஸ் கம்பி அறுந்துள்ளது", "none": "சேதம் எதுவும் இல்லை", "other": "சேதம்"},
           "at": "{where}: {what}", "near": "{street} {house} எண் அருகில்", "here": "நீங்கள் இருக்கும் இடம்",
           "live": "லைனில் மின்சாரம் உள்ளது", "device_ok": "நாங்கள் அனுப்பிய சாதனம் சரியாக உள்ளது",
           "houses": "{a} முதல் {b} வரையிலான வீடுகளுக்கு மின்சாரம் இல்லை", "needs": "உங்களுக்கு {list} தேவை",
           "and": " மற்றும் ", "sep": "; ",
           "crews": {"line": "லைன் குழு", "bucket_truck": "பக்கெட் லாரி", "vegetation": "மரம் வெட்டும் குழு",
                     "troubleshooter": "தொழில்நுட்பர்"}},
    "es": {"damage": {"pole_down": "poste caído", "tree_on_line": "árbol sobre la línea",
                      "live_wire": "conductor energizado en el suelo", "wire_down": "cable caído",
                      "blown_fuse": "fusible del transformador quemado", "transformer_failure": "transformador dañado",
                      "service_wire": "acometida caída", "none": "sin daños", "other": "daños"},
           "at": "{what} en {where}", "near": "{street}, cerca del número {house}", "here": "su ubicación",
           "live": "la línea está energizada", "device_ok": "el equipo al que lo enviamos está bien",
           "houses": "las casas del {a} al {b} sin servicio", "needs": "necesita {list}", "and": " y ", "sep": "; ",
           "crews": {"line": "una cuadrilla de línea", "bucket_truck": "un camión canasta",
                     "vegetation": "la cuadrilla de árboles", "troubleshooter": "un técnico"}},
    "hi": {"damage": {"pole_down": "खंभा गिरा है", "tree_on_line": "पेड़ लाइन पर गिरा है",
                      "live_wire": "करंट वाला तार नीचे गिरा है", "wire_down": "तार नीचे गिरा है",
                      "blown_fuse": "ट्रांसफ़ॉर्मर का फ़्यूज़ उड़ गया है", "transformer_failure": "ट्रांसफ़ॉर्मर खराब है",
                      "service_wire": "सर्विस तार टूटा है", "none": "कोई नुकसान नहीं", "other": "नुकसान"},
           "at": "{where}: {what}", "near": "{street}, मकान नंबर {house} के पास", "here": "आपकी जगह",
           "live": "लाइन में करंट है", "device_ok": "जिस उपकरण पर हमने भेजा था वह ठीक है",
           "houses": "मकान {a} से {b} तक बिजली नहीं है", "needs": "आपको {list} चाहिए", "and": " और ", "sep": "; ",
           "crews": {"line": "लाइन टीम", "bucket_truck": "बकेट ट्रक", "vegetation": "पेड़ काटने वाली टीम",
                     "troubleshooter": "लाइनमैन"}},
}

# What a crew says on arrival (the World picks the template from the real fault), per language.
SITE_REPORTS = {
    "en": {
        "pole_down": "On site at {street} near number {house}. Concrete pole snapped, conductors down across the road. "
                     "Starting pole replacement.",
        "tree_on_line": "On site at {street} near number {house}. A tree is lying across the conductors. "
                        "Clearing it before the line work.",
        "live_wire": "On site at {street} near number {house}. The conductor on the road is live. Area cordoned off, "
                     "making it safe now.",
        "blown_fuse": "On site at transformer {xf} on {street} near number {house}. The drop-out fuse is blown. "
                      "Replacing it now.",
        "service_wire": "On site at {street} near number {house}.",
        "contradict_service_wire": "Transformer {xf} on {street} is fine, its fuses are intact. The service wire is "
                                   "down at number {house} after a branch fell, so only houses {a} to {b} have no "
                                   "supply. Need a line crew for the service wire.",
        "contradict_blown_fuse": "The line is fine here. It is the drop-out fuse on transformer {xf} near {street} "
                                 "number {house} that has blown.",
        "nothing": "On site at {label}. No damage found here; the line looks healthy.",
    },
    "si": {
        "pole_down": "{street} අංක {house} අසල ඉන්නවා. කොන්ක්‍රීට් කණුව කැඩිලා, වයර් පාර හරහා වැටිලා. කණුව මාරු කරන්න පටන් "
                     "ගන්නවා.",
        "tree_on_line": "{street} අංක {house} අසල ඉන්නවා. ලොකු ගහක් වයර් උඩට වැටිලා. ලයින් වැඩට කලින් ඒක අයින් කරනවා.",
        "live_wire": "{street} අංක {house} අසල ඉන්නවා. පාරේ තියෙන වයරයේ විදුලිය තියෙනවා. ප්‍රදේශය වට කළා, දැන් ආරක්ෂිත කරනවා.",
        "blown_fuse": "{street} අංක {house} අසල ට්‍රාන්ස්ෆෝමර් {xf} ළඟ ඉන්නවා. ඩ්‍රොප්-අවුට් ෆියුස් එක පිච්චිලා. දැන් මාරු "
                      "කරනවා.",
        "service_wire": "{street} අංක {house} අසල ඉන්නවා.",
        "contradict_service_wire": "{street} ට්‍රාන්ස්ෆෝමර් {xf} හොඳින්, ෆියුස් හරි. අංක {house} ළඟ අත්තක් වැටිලා සර්විස් "
                                   "වයරය කැඩිලා, ඒ නිසා නිවාස {a} සිට {b} දක්වා විතරයි විදුලිය නැත්තේ. සර්විස් වයරයට "
                                   "ලයින් කණ්ඩායමක් ඕනේ.",
        "contradict_blown_fuse": "මෙතන ලයින් එක හොඳින්. {street} අංක {house} ළඟ ට්‍රාන්ස්ෆෝමර් {xf} එකේ ඩ්‍රොප්-අවුට් ෆියුස් "
                                 "එක තමයි පිච්චිලා තියෙන්නේ.",
        "nothing": "{label} ළඟ ඉන්නවා. මෙතන හානියක් නැහැ, ලයින් එක හොඳින්.",
    },
    "ta": {
        "pole_down": "{street} {house} எண் அருகில் இருக்கிறோம். கான்கிரீட் கம்பம் உடைந்து, கம்பிகள் சாலையின் குறுக்கே "
                     "விழுந்துள்ளன. கம்பத்தை மாற்றத் தொடங்குகிறோம்.",
        "tree_on_line": "{street} {house} எண் அருகில் இருக்கிறோம். ஒரு மரம் கம்பிகள் மேல் விழுந்துள்ளது. லைன் வேலைக்கு "
                        "முன் அதை அகற்றுகிறோம்.",
        "live_wire": "{street} {house} எண் அருகில் இருக்கிறோம். சாலையில் உள்ள கம்பியில் மின்சாரம் உள்ளது. பகுதியை "
                     "மூடிவிட்டோம், இப்போது பாதுகாப்பாக்குகிறோம்.",
        "blown_fuse": "{street} {house} எண் அருகில் டிரான்ஸ்ஃபார்மர் {xf} இல் இருக்கிறோம். டிராப்-அவுட் ஃபியூஸ் "
                      "போயிருக்கிறது. இப்போது மாற்றுகிறோம்.",
        "service_wire": "{street} {house} எண் அருகில் இருக்கிறோம்.",
        "contradict_service_wire": "{street} இல் டிரான்ஸ்ஃபார்மர் {xf} சரியாக உள்ளது, ஃபியூஸ்கள் நன்றாக உள்ளன. {house} "
                                   "எண் அருகில் கிளை விழுந்து சர்வீஸ் கம்பி அறுந்துள்ளது, அதனால் {a} முதல் {b} வரையிலான "
                                   "வீடுகளுக்கு மட்டும் மின்சாரம் இல்லை. சர்வீஸ் கம்பிக்கு லைன் குழு வேண்டும்.",
        "contradict_blown_fuse": "இங்கே லைன் சரியாக உள்ளது. {street} {house} எண் அருகில் உள்ள டிரான்ஸ்ஃபார்மர் {xf} இன் "
                                 "டிராப்-அவுட் ஃபியூஸ்தான் போயிருக்கிறது.",
        "nothing": "{label} இல் இருக்கிறோம். இங்கே சேதம் எதுவும் இல்லை; லைன் நன்றாக உள்ளது.",
    },
    "es": {
        "pole_down": "En sitio en {street}, cerca del número {house}. El poste de concreto está quebrado y los "
                     "conductores cruzan la calle. Empezamos a cambiar el poste.",
        "tree_on_line": "En sitio en {street}, cerca del número {house}. Hay un árbol sobre los conductores. Lo "
                        "quitamos antes del trabajo de línea.",
        "live_wire": "En sitio en {street}, cerca del número {house}. El conductor en el suelo está energizado. "
                     "Acordonamos el área y lo estamos asegurando.",
        "blown_fuse": "En sitio en el transformador {xf} de {street}, cerca del número {house}. El fusible está "
                      "quemado. Lo cambiamos ahora.",
        "service_wire": "En sitio en {street}, cerca del número {house}.",
        "contradict_service_wire": "El transformador {xf} de {street} está bien, los fusibles están intactos. La "
                                   "acometida se cayó en el número {house} por una rama, así que solo las casas del {a} "
                                   "al {b} están sin servicio. Necesitamos una cuadrilla de línea para la acometida.",
        "contradict_blown_fuse": "La línea está bien aquí. El que se quemó es el fusible del transformador {xf}, "
                                 "cerca del número {house} de {street}.",
        "nothing": "En sitio en {label}. No encontramos daños; la línea se ve bien.",
    },
    "hi": {
        "pole_down": "{street}, मकान नंबर {house} के पास पहुँच गए हैं। कंक्रीट का खंभा टूटा है, तार सड़क पर गिरे हैं। खंभा "
                     "बदलना शुरू कर रहे हैं।",
        "tree_on_line": "{street}, मकान नंबर {house} के पास पहुँच गए हैं। एक पेड़ तारों पर गिरा है। लाइन के काम से पहले उसे "
                        "हटा रहे हैं।",
        "live_wire": "{street}, मकान नंबर {house} के पास पहुँच गए हैं। सड़क पर पड़े तार में करंट है। इलाका घेर दिया है, अब "
                     "सुरक्षित कर रहे हैं।",
        "blown_fuse": "{street}, मकान नंबर {house} के पास ट्रांसफ़ॉर्मर {xf} पर हैं। ड्रॉप-आउट फ़्यूज़ उड़ गया है। अभी बदल "
                      "रहे हैं।",
        "service_wire": "{street}, मकान नंबर {house} के पास पहुँच गए हैं।",
        "contradict_service_wire": "{street} पर ट्रांसफ़ॉर्मर {xf} ठीक है, फ़्यूज़ सही हैं। मकान नंबर {house} के पास टहनी "
                                   "गिरने से सर्विस तार टूटा है, इसलिए सिर्फ़ मकान {a} से {b} तक बिजली नहीं है। सर्विस तार "
                                   "के लिए लाइन टीम चाहिए।",
        "contradict_blown_fuse": "यहाँ लाइन ठीक है। {street}, मकान नंबर {house} के पास ट्रांसफ़ॉर्मर {xf} का ड्रॉप-आउट "
                                 "फ़्यूज़ उड़ा है।",
        "nothing": "{label} पर पहुँच गए हैं। यहाँ कोई नुकसान नहीं मिला; लाइन ठीक है।",
    },
}


AGENT_SI = {
    "greet": "විදුලි බිඳවැටීම් අංශයයි. ඔබ කතා කරන්නේ ස්වයංක්‍රීය සහායකයෙකු සමඟයි. කරුණාකර ඔබේ ලිපිනය හෝ ගිණුම් අංකය, "
             "සහ සිදු වූ දේ කියන්න.",
    "confirm_address": "මා සතුව ඇති ඔබේ ලිපිනය {address}. විදුලිය නැත්තේ එතැනද?",
    "ask_address": "ඔබේ ලිපිනය සොයාගත නොහැකි විය. කරුණාකර නිවසේ අංකය සහ පාර, නැත්නම් ගිණුම් අංකය කියන්න.",
    "ask_hazard": "ඔබ අසල කැඩුණු කණු, වැටුණු වයර් හෝ ගස් පේනවාද? කරුණාකර ඒවා අසලට යන්න එපා.",
    "known_hazard": "ඔබ අසල {what} ගැන අපට දැනටමත් වාර්තාවක් ලැබී ඇත. කරුණාකර ඒ අසලට යන්න එපා, වයර්වල විදුලිය ඇති බව "
                    "සලකන්න.",
    "ask_neighbour": "දෝෂය සොයා ගැනීමට එක ප්‍රශ්නයක්: {address} නිවෙස්වල දැන් විදුලිය තිබේද?",
    "safety_live": "කරුණාකර වයරයෙන් අවම වශයෙන් මීටර් දහයක් ඈතින් සිටින්න, අනෙක් අයවත් ඈත් කරන්න. එහි විදුලිය ඇති බව "
                   "සලකන්න. එය ආරක්ෂිත කිරීමට කණ්ඩායමක් එවනවා.",
    "safety_down": "කරුණාකර වැටුණු කණුව සහ වයර් අසලට යන්න එපා. ඒවායේ විදුලිය ඇති බව සලකන්න.",
    "safety_fire": "ගින්නක් තිබේ නම්, වහාම ගිනි නිවන සේවයට අමතන්න.",
    "escalate": "මෙය හදිසි ලෙස අපේ පාලන මැදිරියට දැනුම් දුන්නා.",
    "status_enroute": "මෙම විදුලි බිඳවැටීම ගැන අපි දන්නවා ({kind}). කණ්ඩායමක් එමින් සිටිනවා. විදුලිය නැවත ලැබීමට ආසන්න "
                      "වේලාව {eta}.",
    "status_onsite": "මෙම විදුලි බිඳවැටීම ගැන අපි දන්නවා ({kind}). කණ්ඩායමක් දැන් එහි වැඩ කරනවා. විදුලිය නැවත ලැබීමට "
                     "ආසන්න වේලාව {eta}.",
    "status_waiting": "මෙම විදුලි බිඳවැටීම ගැන අපි දන්නවා ({kind}). ඉක්මනින් කණ්ඩායමක් යොදවනවා. විදුලිය නැවත ලැබීමට "
                      "ආසන්න වේලාව {eta}.",
    "status_locating": "ස්තූතියි, ඔබේ පැමිණිල්ල සටහන් කළා. අපි දෝෂය සොයමින් සිටිනවා, විදුලිය ලැබෙන වේලාව කෙටි "
                       "පණිවිඩයකින් දන්වනවා.",
    "status_restored_dark": "අපේ වාර්තා අනුව ඔබේ ප්‍රදේශයට {at} ට විදුලිය ලබා දුන්නා. ඔබේ නිවසට තවමත් විදුලිය නැති බව "
                            "සටහන් කළා; අපි තවත් දෝෂයක් සොයනවා.",
    "repeat": "ඔබ මෙය {at} ට දැනටමත් දැනුම් දුන්නා, ස්තූතියි.",
    "junk": "මෙම ඇමතුම් අංකය විදුලි බිඳවැටීම් සඳහා පමණයි. වෙනත් කරුණු සඳහා කාර්යාල වේලාවේ අමතන්න.",
    "sms_fallback": "සමාවන්න, ඇමතුම තේරුම් ගත නොහැකි විය. කරුණාකර {code} සහ ඔබේ ගිණුම් අංකය කෙටි පණිවිඩයක් ලෙස එවන්න.",
    "close": "ඇමතුවාට ස්තූතියි.",
}

AGENT_TA = {
    "greet": "மின் தடை பிரிவு. நீங்கள் ஒரு தானியங்கி உதவியாளருடன் பேசுகிறீர்கள். உங்கள் முகவரி அல்லது கணக்கு எண்ணையும், "
             "என்ன நடந்தது என்பதையும் சொல்லுங்கள்.",
    "confirm_address": "உங்கள் முகவரி {address} என்று எங்களிடம் உள்ளது. அங்கேதான் மின்சாரம் இல்லையா?",
    "ask_address": "உங்கள் முகவரியைக் கண்டுபிடிக்க முடியவில்லை. வீட்டு எண்ணும் தெருவும், அல்லது கணக்கு எண்ணைச் சொல்லுங்கள்.",
    "ask_hazard": "உங்கள் அருகில் விழுந்த மின்கம்பம், கம்பிகள் அல்லது மரங்கள் ஏதாவது தெரிகிறதா? தயவுசெய்து அவற்றின் அருகில் "
                  "போகாதீர்கள்.",
    "known_hazard": "உங்கள் அருகில் {what} பற்றி ஏற்கனவே தகவல் வந்துள்ளது. தயவுசெய்து அதன் அருகில் போகாதீர்கள்; கம்பிகளில் "
                    "மின்சாரம் இருப்பதாகவே கருதுங்கள்.",
    "ask_neighbour": "கோளாறைக் கண்டுபிடிக்க ஒரு கேள்வி: {address} வீடுகளில் இப்போது மின்சாரம் இருக்கிறதா?",
    "safety_live": "தயவுசெய்து அந்தக் கம்பியிலிருந்து குறைந்தது பத்து மீட்டர் தள்ளி இருங்கள், மற்றவர்களையும் தள்ளி வையுங்கள். "
                   "அதில் மின்சாரம் இருப்பதாகவே கருதுங்கள். அதைப் பாதுகாப்பாக்க குழுவை அனுப்புகிறோம்.",
    "safety_down": "தயவுசெய்து விழுந்த கம்பம் மற்றும் கம்பிகளின் அருகில் போகாதீர்கள். அவற்றில் மின்சாரம் இருப்பதாகவே "
                   "கருதுங்கள்.",
    "safety_fire": "தீ இருந்தால், உடனே தீயணைப்புத் துறையை அழையுங்கள்.",
    "escalate": "இதை அவசரமாக எங்கள் கட்டுப்பாட்டு அறைக்குத் தெரிவித்துள்ளேன்.",
    "status_enroute": "இந்த மின் தடை எங்களுக்குத் தெரியும் ({kind}). குழு வந்துகொண்டிருக்கிறது. மின்சாரம் மீண்டும் வர "
                      "சுமார் {eta}.",
    "status_onsite": "இந்த மின் தடை எங்களுக்குத் தெரியும் ({kind}). குழு இப்போது அங்கே வேலை செய்கிறது. மின்சாரம் மீண்டும் "
                     "வர சுமார் {eta}.",
    "status_waiting": "இந்த மின் தடை எங்களுக்குத் தெரியும் ({kind}). விரைவில் ஒரு குழு அனுப்பப்படும். மின்சாரம் மீண்டும் "
                      "வர சுமார் {eta}.",
    "status_locating": "நன்றி, உங்கள் புகார் பதிவு செய்யப்பட்டது. கோளாறைக் கண்டறிந்து வருகிறோம்; மின்சாரம் வரும் நேரத்தை "
                       "குறுஞ்செய்தியில் அனுப்புவோம்.",
    "status_restored_dark": "எங்கள் பதிவுகளின்படி உங்கள் பகுதிக்கு {at} மணிக்கு மின்சாரம் வழங்கப்பட்டது. உங்கள் வீட்டில் "
                            "இன்னும் மின்சாரம் இல்லை என்று பதிவு செய்துள்ளேன்; வேறு கோளாறு உள்ளதா என்று பார்க்கிறோம்.",
    "repeat": "நீங்கள் இதை ஏற்கனவே {at} மணிக்குத் தெரிவித்துள்ளீர்கள், நன்றி.",
    "junk": "இந்த எண் மின் தடைகளுக்கு மட்டுமே. மற்ற விஷயங்களுக்கு அலுவலக நேரத்தில் அழையுங்கள்.",
    "sms_fallback": "மன்னிக்கவும், அழைப்பைப் புரிந்துகொள்ள முடியவில்லை. {code} மற்றும் உங்கள் கணக்கு எண்ணை குறுஞ்செய்தியாக "
                    "அனுப்புங்கள்.",
    "close": "அழைத்ததற்கு நன்றி.",
}

AGENT_ES = {
    "greet": "Equipo de apagones. Le atiende un asistente automático. Dígame su dirección o número de cuenta, y qué "
             "está pasando.",
    "confirm_address": "Tengo su dirección como {address}. ¿Es ahí donde no hay luz?",
    "ask_address": "No encontré su dirección. Dígame el número de casa y la calle, o su número de cuenta.",
    "ask_hazard": "¿Ve algún poste, cable o árbol caído cerca de usted? Por favor, no se acerque.",
    "known_hazard": "Ya tenemos un reporte de {what} cerca de usted. Por favor, no se acerque y trate los cables como "
                    "si tuvieran corriente.",
    "ask_neighbour": "Una pregunta para ubicar la falla: ¿las casas de {address} tienen luz ahora mismo?",
    "safety_live": "Por favor, manténgase al menos a diez metros del cable y aleje a los demás. Trátelo como si tuviera "
                   "corriente. Enviamos una cuadrilla para asegurarlo.",
    "safety_down": "Por favor, no se acerque al poste ni a los cables caídos, y trátelos como si tuvieran corriente.",
    "safety_fire": "Si hay fuego, llame al 911 ahora.",
    "escalate": "Marqué su llamada como urgente para nuestro centro de control.",
    "status_enroute": "Sabemos de este apagón ({kind}). Una cuadrilla va en camino. Restablecimiento estimado: {eta}.",
    "status_onsite": "Sabemos de este apagón ({kind}). Una cuadrilla está trabajando ahí ahora. Restablecimiento "
                     "estimado: {eta}.",
    "status_waiting": "Sabemos de este apagón ({kind}). Pronto asignaremos una cuadrilla. Restablecimiento estimado: "
                      "{eta}.",
    "status_locating": "Gracias, su reporte quedó registrado. Estamos ubicando la falla y le enviaremos un mensaje con "
                       "la hora estimada.",
    "status_restored_dark": "Según nuestros registros, la luz volvió a su zona a las {at}. Registré que su casa sigue "
                            "sin luz; estamos buscando otra falla.",
    "repeat": "Usted ya lo reportó a las {at}, gracias.",
    "junk": "Esta línea es solo para apagones. Para otros temas, llame en horario de oficina.",
    "sms_fallback": "Lo siento, no pude entender la llamada. Por favor envíe un mensaje de texto con {code} y su "
                    "número de cuenta.",
    "close": "Gracias por llamar.",
}

AGENT_HI = {
    "greet": "बिजली शिकायत केंद्र। आप एक स्वचालित सहायक से बात कर रहे हैं। कृपया अपना पता या खाता नंबर बताइए, और क्या हुआ है।",
    "confirm_address": "आपका पता हमारे पास {address} है। क्या वहीं बिजली नहीं है?",
    "ask_address": "आपका पता नहीं मिला। कृपया मकान नंबर और गली, या अपना खाता नंबर बताइए।",
    "ask_hazard": "क्या आपके पास कोई गिरा हुआ खंभा, तार या पेड़ दिख रहा है? कृपया उसके पास मत जाइए।",
    "known_hazard": "आपके पास {what} की सूचना हमें पहले ही मिल चुकी है। कृपया उसके पास मत जाइए और तारों में करंट मानकर चलिए।",
    "ask_neighbour": "खराबी ढूंढने के लिए एक सवाल: क्या {address} के घरों में अभी बिजली है?",
    "safety_live": "कृपया तार से कम से कम दस मीटर दूर रहिए और दूसरों को भी दूर रखिए। उसमें करंट मानकर चलिए। उसे सुरक्षित "
                   "करने के लिए टीम भेज रहे हैं।",
    "safety_down": "कृपया गिरे हुए खंभे और तारों के पास मत जाइए। उनमें करंट मानकर चलिए।",
    "safety_fire": "अगर आग लगी है, तो तुरंत फायर ब्रिगेड को फोन कीजिए।",
    "escalate": "मैंने इसे तुरंत हमारे कंट्रोल रूम को भेज दिया है।",
    "status_enroute": "हमें इस बिजली कटौती की जानकारी है ({kind})। टीम रास्ते में है। बिजली लगभग {eta} तक लौटेगी।",
    "status_onsite": "हमें इस बिजली कटौती की जानकारी है ({kind})। टीम अभी वहाँ काम कर रही है। बिजली लगभग {eta} तक लौटेगी।",
    "status_waiting": "हमें इस बिजली कटौती की जानकारी है ({kind})। जल्द ही टीम भेजी जाएगी। बिजली लगभग {eta} तक लौटेगी।",
    "status_locating": "धन्यवाद, आपकी शिकायत दर्ज हो गई है। हम खराबी ढूंढ रहे हैं और बिजली लौटने का समय SMS से भेजेंगे।",
    "status_restored_dark": "हमारे रिकॉर्ड के अनुसार आपके इलाके में {at} बजे बिजली लौट आई थी। मैंने दर्ज कर लिया है कि आपके "
                            "घर में अभी भी बिजली नहीं है; हम दूसरी खराबी देख रहे हैं।",
    "repeat": "आपने यह {at} बजे पहले ही बता दिया था, धन्यवाद।",
    "junk": "यह नंबर केवल बिजली कटौती के लिए है। दूसरे कामों के लिए दफ़्तर के समय में फोन कीजिए।",
    "sms_fallback": "माफ़ कीजिए, कॉल समझ नहीं आई। कृपया {code} और अपना खाता नंबर SMS कीजिए।",
    "close": "फोन करने के लिए धन्यवाद।",
}

for _agent, _crew in ((AGENT_SI, _CREW_SI), (AGENT_TA, _CREW_TA), (AGENT_ES, _CREW_ES), (AGENT_HI, _CREW_HI)):
    _agent.update(_crew)

# Hazards as the agent names them in "known_hazard" (already reported near the caller).
HAZARD_NAMES = {
    "en": {"pole_down": "a fallen pole", "live_wire": "a live wire", "wire_down": "a fallen wire",
           "tree_on_line": "a tree on the lines", "fire": "a fire"},
    "si": {"pole_down": "වැටුණු කණුවක්", "live_wire": "විදුලිය සහිත වයරයක්", "wire_down": "වැටුණු වයරයක්",
           "tree_on_line": "වයර් මත වැටුණු ගසක්", "fire": "ගින්නක්"},
    "ta": {"pole_down": "விழுந்த மின்கம்பம்", "live_wire": "மின்சாரம் உள்ள கம்பி", "wire_down": "விழுந்த கம்பி",
           "tree_on_line": "கம்பிகள் மேல் விழுந்த மரம்", "fire": "தீ"},
    "es": {"pole_down": "un poste caído", "live_wire": "un cable con corriente", "wire_down": "un cable caído",
           "tree_on_line": "un árbol sobre los cables", "fire": "un incendio"},
    "hi": {"pole_down": "गिरे हुए खंभे", "live_wire": "करंट वाले तार", "wire_down": "गिरे हुए तार",
           "tree_on_line": "तारों पर गिरे पेड़", "fire": "आग"},
}

# What simulated callers say when the agent asks them something (the World picks the true answer).
CALLER_EN = {
    "address": "Number {house}, {street}.", "account": "My account number is {account}.", "yes": "Yes.", "no": "No.",
    "pole_down": "Yes, a pole has fallen near number {house}.", "live_wire": "Yes, there's a wire down and it's sparking.",
    "wire_down": "Yes, there's a wire on the ground.", "tree_on_line": "Yes, a tree has come down on the wires.",
    "fire": "Yes, something is burning near the pole.", "hazard_no": "No, I can't see anything like that.",
    "neighbour_on": "Yes, they have power.", "neighbour_off": "No, they're dark too.",
    "readback_ok": "Correct.", "readback_wrong": "Negative. Again: {report}",
}
CALLER_SI = {
    "address": "අංක {house}, {street}.", "account": "මගේ ගිණුම් අංකය {account}.", "yes": "ඔව්.", "no": "නැහැ.",
    "pole_down": "ඔව්, අංක {house} ළඟ කණුවක් වැටිලා.", "live_wire": "ඔව්, වයරයක් බිම වැටිලා ගිනි පුපුරනවා.",
    "wire_down": "ඔව්, වයරයක් බිම වැටිලා තියෙනවා.", "tree_on_line": "ඔව්, ගහක් වයර් උඩට වැටිලා.",
    "fire": "ඔව්, කණුව ළඟ මොකක්දෝ පිච්චෙනවා.", "hazard_no": "නැහැ, එහෙම දෙයක් පේන්නේ නැහැ.",
    "neighbour_on": "ඔව්, එයාලට විදුලිය තියෙනවා.", "neighbour_off": "නැහැ, එයාලටත් නැහැ.",
    "readback_ok": "හරි.", "readback_wrong": "නැහැ. ආයෙත් කියන්නම්: {report}",
}
CALLER_TA = {
    "address": "{house}, {street}.", "account": "என் கணக்கு எண் {account}.", "yes": "ஆமாம்.", "no": "இல்லை.",
    "pole_down": "ஆமாம், {house} எண் வீட்டுக்கு அருகில் ஒரு மின்கம்பம் விழுந்திருக்கிறது.",
    "live_wire": "ஆமாம், ஒரு கம்பி கீழே விழுந்து தீப்பொறி வருகிறது.", "wire_down": "ஆமாம், ஒரு கம்பி தரையில் கிடக்கிறது.",
    "tree_on_line": "ஆமாம், ஒரு மரம் கம்பிகள் மேல் விழுந்திருக்கிறது.", "fire": "ஆமாம், கம்பத்துக்கு அருகில் ஏதோ எரிகிறது.",
    "hazard_no": "இல்லை, அப்படி எதுவும் தெரியவில்லை.",
    "neighbour_on": "ஆமாம், அவர்களுக்கு மின்சாரம் இருக்கிறது.", "neighbour_off": "இல்லை, அவர்களுக்கும் இல்லை.",
    "readback_ok": "சரி.", "readback_wrong": "இல்லை. மீண்டும் சொல்கிறேன்: {report}",
}
CALLER_ES = {
    "address": "{house} {street}.", "account": "Mi número de cuenta es {account}.", "yes": "Sí.", "no": "No.",
    "pole_down": "Sí, se cayó un poste cerca del {house}.", "live_wire": "Sí, hay un cable en el suelo echando chispas.",
    "wire_down": "Sí, hay un cable en el suelo.", "tree_on_line": "Sí, un árbol cayó sobre los cables.",
    "fire": "Sí, algo se está quemando cerca del poste.", "hazard_no": "No, no veo nada de eso.",
    "neighbour_on": "Sí, ellos tienen luz.", "neighbour_off": "No, ellos tampoco.",
    "readback_ok": "Correcto.", "readback_wrong": "Negativo. Repito: {report}",
}
CALLER_HI = {
    "address": "मकान नंबर {house}, {street}।", "account": "मेरा खाता नंबर {account} है।", "yes": "हाँ।", "no": "नहीं।",
    "pole_down": "हाँ, मकान नंबर {house} के पास एक खंभा गिरा है।", "live_wire": "हाँ, एक तार नीचे गिरा है और चिंगारी निकल रही है।",
    "wire_down": "हाँ, एक तार ज़मीन पर पड़ा है।", "tree_on_line": "हाँ, एक पेड़ तारों पर गिरा है।",
    "fire": "हाँ, खंभे के पास कुछ जल रहा है।", "hazard_no": "नहीं, ऐसा कुछ नहीं दिख रहा।",
    "neighbour_on": "हाँ, उनके यहाँ बिजली है।", "neighbour_off": "नहीं, उनके यहाँ भी नहीं है।",
    "readback_ok": "सही है।", "readback_wrong": "नहीं। फिर से: {report}",
}

SRI_LANKA = {
    "country": "Sri Lanka",
    "hint": ("an electricity utility in Galle, Sri Lanka. Messages arrive in English, Sinhala (script or romanised "
             "'Singlish') or Tamil. Transliterate street names to the English name used locally "
             "(රෝහල පාර / ஹாஸ்பிடல் ரோட் -> Hospital Road, ටෙම්පල් පාර -> Temple Road)."),
    "sms_code": r"^\s*BD\s*(\d{10})\s*$",
    "sms_label": "BD SMS",
    "question": {
        "en": "Outage desk: we are locating a fault near you. Is the power on at your home right now? Reply YES or NO.",
        "si": "විදුලි දෝෂ අංශය: ඔබේ ප්‍රදේශයේ දෝෂයක් සොයමින් සිටිමු. දැන් ඔබේ නිවසේ විදුලිය තිබේද? ඔව් හෝ නැත ලෙස පිළිතුරු දෙන්න.",
        "ta": "மின் தடை பிரிவு: உங்கள் பகுதியில் ஒரு கோளாறைக் கண்டறிகிறோம். இப்போது உங்கள் வீட்டில் மின்சாரம் உள்ளதா? ஆம் அல்லது இல்லை என்று பதிலளிக்கவும்.",
    },
    "notice": {
        "en": "Outage desk: we have found the fault affecting your supply ({kind}). A crew is assigned. Estimated restoration around {eta}.",
        "si": "විදුලි දෝෂ අංශය: ඔබේ සැපයුමට බලපාන දෝෂය සොයාගෙන ඇත ({kind}). කණ්ඩායමක් යොදවා ඇත. විදුලිය නැවත ලැබීමට ආසන්න වේලාව {eta}.",
        "ta": "மின் தடை பிரிவு: உங்கள் மின் விநியோகத்தை பாதித்த கோளாறு கண்டறியப்பட்டது ({kind}). குழு அனுப்பப்பட்டுள்ளது. மின்சாரம் மீண்டும் வர சுமார் {eta}.",
    },
    "restored": {
        "en": "Outage desk: power has been restored in your area. If you are still without power, reply to this message.",
        "si": "විදුලි දෝෂ අංශය: ඔබේ ප්‍රදේශයට විදුලිය නැවත ලබා දී ඇත. තවමත් විදුලිය නැත්නම් මෙම පණිවිඩයට පිළිතුරු දෙන්න.",
        "ta": "மின் தடை பிரிவு: உங்கள் பகுதிக்கு மின்சாரம் மீண்டும் வழங்கப்பட்டுள்ளது. இன்னும் மின்சாரம் இல்லையெனில் இந்த செய்திக்கு பதிலளிக்கவும்.",
    },
    "reply": {
        True: {"en": "Yes, our power is on.", "si": "ඔව්, අපේ ගෙදර විදුලිය තියෙනවා.",
               "ta": "ஆம், எங்கள் வீட்டில் மின்சாரம் உள்ளது."},
        False: {"en": "No, we have no power here either.", "si": "නැහැ, අපිටත් විදුලිය නැහැ.",
                "ta": "இல்லை, எங்களுக்கும் மின்சாரம் இல்லை."},
    },
    "followup": {
        "en": "The neighbours have power again but our house is still dark. {street} {house}.",
        "si": "අසල්වැසියන්ට විදුලිය ආවා, අපිට තවම නැහැ. {street} {house}.",
        "ta": "பக்கத்து வீடுகளுக்கு மின்சாரம் வந்துவிட்டது, எங்களுக்கு இன்னும் இல்லை. {street} {house}.",
    },
    "address": "{house}, {street}",
    "agent": {"en": _agent_en("Outage desk", "If anything is on fire, call the fire service now."),
              "si": AGENT_SI, "ta": AGENT_TA},
    "caller": {"en": CALLER_EN, "si": CALLER_SI, "ta": CALLER_TA},
    # Neural text-to-speech voices (edge-tts); there is no Sri Lankan English voice, Indian English is closest.
    "voices": {"agent": {"en": "en-IN-NeerjaNeural", "si": "si-LK-ThiliniNeural", "ta": "ta-LK-SaranyaNeural"},
               "caller": {"en": ["en-IN-PrabhatNeural"],  # the only other Indian English voice is the agent's
                          "si": ["si-LK-SameeraNeural", "si-LK-ThiliniNeural"],
                          "ta": ["ta-LK-KumarNeural", "ta-LK-SaranyaNeural"]},
               "crew": {"en": ["en-IN-PrabhatNeural"], "ta": ["ta-IN-ValluvarNeural"], "hi": ["hi-IN-MadhurNeural"]}},
}

US = {
    "country": "United States",
    "hint": ("an electric utility in Houston, Texas. Messages arrive in English or Spanish, from calls, texts and "
             "the outage app. Street names stay as written (e.g. 'Burkhart Drive')."),
    "sms_code": r"^\s*OUT\s*(\d{10})\s*$",
    "sms_label": "OUT text",
    "question": {
        "en": "Outage team: we're pinpointing an outage near you. Is your power on right now? Reply YES or NO.",
        "es": "Equipo de apagones: estamos localizando una falla cerca de usted. ¿Tiene electricidad ahora mismo? Responda SÍ o NO.",
    },
    "notice": {
        "en": "Outage team: we found the problem affecting your power ({kind}). A crew is assigned. Estimated restoration {eta}.",
        "es": "Equipo de apagones: encontramos la falla que afecta su servicio ({kind}). Una cuadrilla está asignada. Restablecimiento estimado {eta}.",
    },
    "restored": {
        "en": "Outage team: power has been restored in your area. Still out? Reply to this message.",
        "es": "Equipo de apagones: se restableció la electricidad en su zona. ¿Sigue sin luz? Responda a este mensaje.",
    },
    "reply": {
        True: {"en": "Yes, power is on here.", "es": "Sí, aquí sí hay luz."},
        False: {"en": "No, still no power.", "es": "No, seguimos sin luz."},
    },
    "followup": {
        "en": "The street got power back but my house is still out. {house} {street}.",
        "es": "La calle ya tiene luz pero mi casa sigue sin electricidad. {house} {street}.",
    },
    "address": "{house} {street}",
    "agent": {"en": _agent_en("Outage team", "If anything is on fire, call 911 now."), "es": AGENT_ES},
    "caller": {"en": {**CALLER_EN, "address": "{house} {street}."}, "es": CALLER_ES},
    "voices": {"agent": {"en": "en-US-AvaNeural", "es": "es-US-PalomaNeural"},
               "caller": {"en": ["en-US-AndrewNeural", "en-US-EmmaNeural", "en-US-BrianNeural"],
                          "es": ["es-US-AlonsoNeural", "es-MX-DaliaNeural", "es-MX-JorgeNeural"]},
               "crew": {"en": ["en-US-GuyNeural", "en-US-ChristopherNeural", "en-US-RogerNeural"],
                        "es": ["es-US-AlonsoNeural", "es-MX-JorgeNeural"]}},
    "first": ["James", "Maria", "Robert", "Linda", "Michael", "Ana", "David", "Jennifer", "Jose", "Patricia", "Daniel",
              "Rosa", "Kevin", "Emily", "Luis", "Sarah", "Minh", "Grace", "Carlos", "Ashley"],
    "last": ["Smith", "Garcia", "Johnson", "Martinez", "Nguyen", "Brown", "Hernandez", "Davis", "Lopez", "Wilson",
             "Gonzalez", "Kim", "Anderson", "Rodriguez", "Thomas", "Perez", "Lee", "Moore"],
    "account": lambda rng: f"{rng.randint(0, 9_999_999_999):010d}",
    "phone": lambda rng: f"713{rng.randint(2_000_000, 9_999_999)}",
    "house_no": lambda i: 1000 + 4 * i,
    "facility_phone": "71355",
    "aliases": {"hospital": ["er", "emergency room"], "school": ["elementary", "middle school"]},
}

INDIA = {
    "country": "India",
    "hint": ("an electricity distribution company in Chennai, India. Messages arrive in English, Tamil (script or "
             "romanised 'Tanglish') and occasionally Hindi. Street names stay as written "
             "(e.g. 'Tansi Nagar 11th Street')."),
    "sms_code": r"^\s*PWR\s*(\d{10})\s*$",
    "sms_label": "PWR SMS",
    "question": {
        "en": "Power outage desk: we are locating a fault near you. Is there power at your home now? Reply YES or NO.",
        "ta": "மின் தடை பிரிவு: உங்கள் பகுதியில் ஒரு கோளாறைக் கண்டறிகிறோம். இப்போது உங்கள் வீட்டில் மின்சாரம் உள்ளதா? ஆம் அல்லது இல்லை என்று பதிலளிக்கவும்.",
        "hi": "बिजली शिकायत केंद्र: हम आपके पास एक खराबी ढूंढ रहे हैं। क्या अभी आपके घर में बिजली है? हाँ या नहीं में जवाब दें।",
    },
    "notice": {
        "en": "Power outage desk: the fault affecting your supply has been found ({kind}). A crew is assigned. Expected restoration around {eta}.",
        "ta": "மின் தடை பிரிவு: உங்கள் மின் விநியோகத்தை பாதித்த கோளாறு கண்டறியப்பட்டது ({kind}). குழு அனுப்பப்பட்டுள்ளது. மின்சாரம் மீண்டும் வர சுமார் {eta}.",
        "hi": "बिजली शिकायत केंद्र: आपकी बिजली को प्रभावित करने वाली खराबी मिल गई है ({kind})। टीम भेजी गई है। बिजली लगभग {eta} तक लौटेगी।",
    },
    "restored": {
        "en": "Power outage desk: supply has been restored in your area. If you still have no power, reply to this message.",
        "ta": "மின் தடை பிரிவு: உங்கள் பகுதிக்கு மின்சாரம் மீண்டும் வழங்கப்பட்டுள்ளது. இன்னும் மின்சாரம் இல்லையெனில் இந்த செய்திக்கு பதிலளிக்கவும்.",
        "hi": "बिजली शिकायत केंद्र: आपके क्षेत्र में बिजली बहाल कर दी गई है। अगर अब भी बिजली नहीं है, तो इस संदेश का जवाब दें।",
    },
    "reply": {
        True: {"en": "Yes, power is there.", "ta": "ஆம், மின்சாரம் உள்ளது.", "hi": "हाँ, बिजली है।"},
        False: {"en": "No, no power here also.", "ta": "இல்லை, இங்கும் மின்சாரம் இல்லை.", "hi": "नहीं, यहाँ भी बिजली नहीं है।"},
    },
    "followup": {
        "en": "Other houses got current but our house still no power. {street}, door no {house}.",
        "ta": "மற்ற வீடுகளுக்கு கரண்ட் வந்துவிட்டது, எங்கள் வீட்டில் இன்னும் இல்லை. {street}, கதவு எண் {house}.",
        "hi": "बाकी घरों में बिजली आ गई पर हमारे घर में अभी भी नहीं है। {street}, मकान नंबर {house}।",
    },
    "address": "{house}, {street}",
    "agent": {"en": _agent_en("Power outage desk", "If anything is on fire, call the fire service now."),
              "ta": AGENT_TA, "hi": AGENT_HI},
    "caller": {"en": {**CALLER_EN, "address": "Door number {house}, {street}."}, "ta": CALLER_TA, "hi": CALLER_HI},
    "voices": {"agent": {"en": "en-IN-NeerjaNeural", "ta": "ta-IN-PallaviNeural", "hi": "hi-IN-SwaraNeural"},
               "caller": {"en": ["en-IN-PrabhatNeural"],  # the only other Indian English voice is the agent's
                          "ta": ["ta-IN-ValluvarNeural", "ta-IN-PallaviNeural"],
                          "hi": ["hi-IN-MadhurNeural", "hi-IN-SwaraNeural"]},
               "crew": {"en": ["en-IN-PrabhatNeural"], "si": ["si-LK-SameeraNeural"], "ta": ["ta-LK-KumarNeural"]}},
    "first": ["Arun", "Lakshmi", "Karthik", "Priya", "Suresh", "Divya", "Rajesh", "Meena", "Vignesh", "Anitha",
              "Mohammed", "Fathima", "Ramesh", "Kavya", "Senthil", "Deepa", "Arjun", "Sangeetha", "Joseph", "Mary"],
    "last": ["Kumar", "Raman", "Subramanian", "Krishnan", "Iyer", "Natarajan", "Pillai", "Rajan", "Murugan", "Basha",
             "Narayanan", "Srinivasan", "Thomas", "Venkatesh", "Ganesan"],
    "account": lambda rng: f"{rng.randint(0, 9_999_999_999):010d}",
    "phone": lambda rng: f"9{rng.randint(100_000_000, 999_999_999)}",
    "house_no": lambda i: 1 + i,
    "facility_phone": "04422",
    "aliases": {"hospital": ["aspathri", "மருத்துவமனை", "अस्पताल"], "school": ["பள்ளி"],
                "place_of_worship": ["temple", "kovil", "கோவில்", "church", "mosque"]},
}

LOCALES = {"sri_lanka": SRI_LANKA, "us": US, "india": INDIA}
