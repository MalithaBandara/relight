# Native-speaker check: fault-type names (Sinhala, Tamil, Spanish, Hindi)

These phrases replaced the English label that used to appear in brackets in agent lines and SMS notices
(for example "We know about this outage (pole down)"). Each is a noun phrase that sits inside a sentence, so please
check that it reads naturally there, not just as a word.

Sentences they appear in (`relight/locales.py`): `status_enroute`, `status_onsite`, `status_waiting`, `crew_changed`
and the "fault found" SMS notice.

| Fault | English | Sinhala | Tamil | Spanish | Hindi |
|---|---|---|---|---|---|
| pole_down | pole down | කණුවක් වැටීම | மின்கம்பம் விழுதல் | poste caído | खंभा गिरना |
| tree_on_line | tree on line | ගසක් වයර් මත වැටීම | மரம் கம்பிகள் மேல் விழுதல் | árbol sobre la línea | लाइन पर पेड़ गिरना |
| live_wire | live wire on road | විදුලිය සහිත වයරයක් බිම වැටීම | மின்சாரம் உள்ள கம்பி அறுந்து விழுதல் | cable con corriente en el suelo | करंट वाले तार का गिरना |
| wire_down | wire down | වයරයක් බිම වැටීම | கம்பி அறுந்து விழுதல் | cable caído | तार का गिरना |
| blown_fuse | blown fuse | ෆියුස් එක පිච්චීම | ஃபியூஸ் போதல் | fusible quemado | फ़्यूज़ उड़ना |
| service_wire | service wire down | සර්විස් වයරය කැඩීම | சர்வீஸ் கம்பி அறுதல் | acometida caída | सर्विस तार टूटना |
| unknown | cause still being checked | හේතුව තවමත් පරීක්ෂා කරමින් පවතී | காரணம் இன்னும் ஆராயப்படுகிறது | causa en revisión | कारण की जाँच जारी है |

Example lines to read in context:

- Sinhala: `මෙම විදුලි බිඳවැටීම ගැන අපි දන්නවා (කණුවක් වැටීම). කණ්ඩායමක් එමින් සිටිනවා.`
- Tamil: `இந்த மின் தடை எங்களுக்குத் தெரியும் (மின்கம்பம் விழுதல்). குழு வந்துகொண்டிருக்கிறது.`
- Spanish: `Sabemos de este apagón (poste caído). Una cuadrilla va en camino.`
- Hindi: `हमें इस बिजली कटौती की जानकारी है (खंभा गिरना)। टीम रास्ते में है।`

Mark any phrase to change and send it back; it is a one-line edit in `KIND_NAME`.

## Restoration estimate update SMS (added 2026-11-04, not reviewed)

Sent when a customer's restoration time has moved (`notice_update` in `relight/locales.py`). `{kind}` is a fault name from
the table above and `{eta}` is a time such as 17:18.

- Sinhala: `විදුලි දෝෂ අංශය: ඔබේ සැපයුමට බලපාන දෝෂය ගැන යාවත්කාලීන තොරතුරක් ({kind}). විදුලිය නැවත ලැබීමට දැන් ආසන්න වේලාව {eta}.`
- Tamil: `மின் தடை பிரிவு: உங்கள் மின் விநியோகத்தை பாதித்த கோளாறு பற்றிய புதிய தகவல் ({kind}). மின்சாரம் மீண்டும் வர இப்போது சுமார் {eta}.`
- Spanish: `Equipo de apagones: novedades sobre la falla que afecta su servicio ({kind}). El restablecimiento estimado ahora es {eta}.`
- Hindi: `बिजली शिकायत केंद्र: आपकी बिजली को प्रभावित करने वाली खराबी की नई जानकारी ({kind})। बिजली अब लगभग {eta} तक लौटेगी।`
