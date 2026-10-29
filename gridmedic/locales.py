"""Per-country details: names, number formats, languages and the messages GridMedic sends.

The engine is the same everywhere; only these words and formats change. Customer names
and numbers are synthetic. Non-English texts should be checked by a native speaker.
"""

from __future__ import annotations

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
