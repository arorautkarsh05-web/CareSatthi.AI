"""Safety Workflow / Safety Agent for CareSaathi AI.
Enforces deterministic safety policies, clinical boundaries, and emergency escalations.
Strictly conforms to PRD Section 8 and FR-08 with full Multilingual Support.
"""
import re
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from caresaathi.config import NATIONAL_EMERGENCY_NUMBER, AMBULANCE_NUMBER
from caresaathi.models import SafetyEmergencyLevel, SafetyEvent
from caresaathi.db import save_safety_event


# Multilingual Safety Alert Translations
LOCALIZED_SAFETY_MESSAGES = {
    "EMERGENCY": {
        "en": (
            f"URGENT EMERGENCY ALERT: Your reported symptoms indicate potential acute cardiac distress or medical emergency. "
            f"Please stop all activity and CALL {NATIONAL_EMERGENCY_NUMBER} (National Emergency) or {AMBULANCE_NUMBER} (Ambulance) IMMEDIATELY. "
            "Do not wait for further chat replies or delay seeking emergency medical attention."
        ),
        "hi": (
            f"🚨 आपातकालीन चेतावनी (URGENT EMERGENCY ALERT): आपके द्वारा बताए गए लक्षण गंभीर आपातकाल की ओर संकेत कर रहे हैं। "
            f"कृपया तुरंत {NATIONAL_EMERGENCY_NUMBER} (राष्ट्रीय आपातकालीन नंबर) या {AMBULANCE_NUMBER} (एंबुलेंस) पर कॉल करें! "
            "चैट का इंतज़ार न करें और तत्काल नजदीकी अस्पताल या आपातकालीन सेवा से संपर्क करें।"
        ),
        "hinglish": (
            f"🚨 URGENT EMERGENCY ALERT: Aapke symptoms critical medical emergency indicate kar rahe hain! "
            f"Please turant {NATIONAL_EMERGENCY_NUMBER} (National Emergency) ya {AMBULANCE_NUMBER} (Ambulance) par CALL karein. "
            "Chat reply ka wait bilkul na karein aur turant emergency help lein."
        ),
        "gu": (
            f"🚨 કટોકટી ચેતવણી (URGENT EMERGENCY ALERT): તમારા લક્ષણો ગંભીર કટોકટી દર્શાવે છે. "
            f"કૃપા કરીને તરત જ {NATIONAL_EMERGENCY_NUMBER} (રાષ્ટ્રીય કટોકટી) અથવા {AMBULANCE_NUMBER} (એમ્બ્યુલન્સ) પર કૉલ કરો! "
            "ચેટમાં સમય બગાડ્યા વિના તાત્કાલિક સારવાર લો."
        ),
        "bn": (
            f"🚨 জরুরী সতর্কতা (URGENT EMERGENCY ALERT): আপনার লক্ষণগুলি গুরুতর জরুরি অবস্থা নির্দেশ করছে। "
            f"অনুগ্রহ করে অবিলম্বে {NATIONAL_EMERGENCY_NUMBER} বা {AMBULANCE_NUMBER} নম্বরে কল করুন! "
            "দেরি না করে দ্রুত জরুরি চিকিৎসা সহায়তা নিন।"
        ),
        "mr": (
            f"🚨 तातडीची आणीबाणी सूचना (URGENT EMERGENCY ALERT): तुमची लक्षणे गंभीर वैद्यकीय आणीबाणी दर्शवतात. "
            f"कृपया ताबडतोब {NATIONAL_EMERGENCY_NUMBER} किंवा {AMBULANCE_NUMBER} वर कॉल करा! "
            "विलंब न करता तात्काळ जवळच्या रुग्णालयात जा."
        ),
        "te": (
            f"🚨 అత్యవసర హెచ్చరిక (URGENT EMERGENCY ALERT): మీ లక్షణాలు తీవ్రమైన పరిస్థితిని సూచిస్తున్నాయి. "
            f"దయచేసి వెంటనే {NATIONAL_EMERGENCY_NUMBER} లేదా {AMBULANCE_NUMBER} కి కాల్ చేయండి! "
            "ఆలస్యం చేయకుండా తక్షణమే అత్యవసర వైద్య సహాయం పొందండి."
        ),
        "ta": (
            f"🚨 அவசர எச்சரிக்கை (URGENT EMERGENCY ALERT): உங்கள் அறிகுறிகள் தீவிர மருத்துவ அவசரநிலையைக் குறிக்கின்றன. "
            f"உடனடியாக {NATIONAL_EMERGENCY_NUMBER} அல்லது {AMBULANCE_NUMBER} ஐ அழைக்கவும்! "
            "தாமதிக்காமல் அவசர மருத்துவ உதவியை நாடுங்கள்."
        ),
        "pa": (
            f"🚨 ਐਮਰਜੈਂਸੀ ਚੇਤਾਵਨੀ (URGENT EMERGENCY ALERT): ਤੁਹਾਡੇ ਲੱਛਣ ਗੰਭੀਰ ਐਮਰਜੈਂਸੀ ਵੱਲ ਇਸ਼ਾਰਾ ਕਰ ਰਹੇ ਹਨ। "
            f"ਕਿਰਪਾ ਕਰਕੇ ਤੁਰੰਤ {NATIONAL_EMERGENCY_NUMBER} ਜਾਂ {AMBULANCE_NUMBER} 'ਤੇ ਕਾਲ ਕਰੋ!"
        )
    },
    "BLOCK_STOP_MEDICATION": {
        "en": (
            "SAFETY POLICY BLOCK: CareSaathi AI cannot advise you to discontinue, stop, or pause any prescribed medication. "
            "Medication changes must only be approved by your treating clinician. "
            "We have logged this inquiry as an unresolved question in your clinician report so you can discuss it safely at your next consult."
        ),
        "hi": (
            "🛑 सुरक्षा नीति ब्लॉक: केयरसाथी AI आपको कोई भी दवा रोकने, छोड़ने या बंद करने की सलाह नहीं दे सकता। "
            "दवा में कोई भी बदलाव केवल आपके डॉक्टर द्वारा किया जा सकता है। "
            "हमने यह सवाल आपके डॉक्टर की रिपोर्ट में जोड़ दिया है ताकि अगली मुलाकात में इस पर चर्चा हो सके।"
        ),
        "hinglish": (
            "🛑 SAFETY POLICY BLOCK: CareSaathi AI prescribed dawai band karne, rokne ya skip karne ki advise nahi de sakta. "
            "Dawai me koi bhi badlav sirf aapke doctor hi kar sakte hain. "
            "Humne yeh sawal aapki doctor progress report me record kar diya hai."
        ),
        "gu": (
            "🛑 સુરક્ષા નીતિ બ્લોક: CareSaathi AI તમને કોઈ દવા બંધ કરવાની કે છોડવાની સલાહ આપી શકતું નથી. "
            "દવામાં કોઈપણ ફેરફાર ફક્ત તમારા ડૉક્ટર જ કરી શકે છે. આ પ્રશ્ન તમારા ડૉક્ટરના રિપોર્ટમાં ઉમેરવામાં આવ્યો છે."
        ),
        "bn": (
            "🛑 সুরক্ষা নীতি ব্লক: CareSaathi AI কোনো ওষুধ বন্ধ বা স্থগিত করার পরামর্শ দিতে পারে না। "
            "ওষুধের যেকোনো পরিবর্তন কেবল আপনার চিকিৎসকের মাধ্যমেই হওয়া উচিত।"
        ),
        "mr": (
            "🛑 सुरक्षा धोरण ब्लॉक: CareSaathi AI विहित केलेले औषध थांबवण्याचा किंवा बंद करण्याचा सल्ला देऊ शकत नाही. "
            "औषधात बदल फक्त तुमचे डॉक्टरच करू शकतात."
        ),
        "te": (
            "🛑 భద్రతా నిబంధన: CareSaathi AI ప్రిస్క్రిప్షన్ మందులను ఆపడానికి లేదా నిలిపివేయడానికి సలహా ఇవ్వదు. "
            "వైద్యుడి అనుమతి లేకుండా మందులు మార్చకూడదు."
        ),
        "ta": (
            "🛑 பாதுகாப்புக் கொள்கை: பரிந்துரைக்கப்பட்ட மருந்தை நிறுத்த CareSaathi AI அறிவுறுத்தாது. "
            "மருத்துவ மாற்றங்கள் மருத்துவரால் மட்டுமே அங்கீகரிக்கப்பட வேண்டும்."
        ),
        "pa": (
            "🛑 ਸੁਰੱਖਿਆ ਨੀਤੀ: CareSaathi AI ਦਵਾਈ ਬੰਦ ਕਰਨ ਜਾਂ ਰੋਕਣ ਦੀ ਸਲਾਹ ਨਹੀਂ ਦੇ ਸਕਦਾ। "
            "ਕੋਈ ਵੀ ਬਦਲਾਅ ਸਿਰਫ ਤੁਹਾਡੇ ਡਾਕਟਰ ਦੁਆਰਾ ਹੀ ਕੀਤਾ ਜਾ ਸਕਦਾ ਹੈ।"
        )
    },
    "BLOCK_CHANGE_DOSAGE": {
        "en": (
            "SAFETY POLICY BLOCK: CareSaathi AI is strictly prohibited from modifying medication dosages. "
            "Changing doses without medical supervision can lead to toxicity or therapeutic failure. "
            "Please consult your treating doctor or pharmacist before making any dosage changes."
        ),
        "hi": (
            "🛑 सुरक्षा नीति ब्लॉक: केयरसाथी AI दवा की डोज़ या मात्रा बदलने की अनुमति नहीं देता। "
            "डॉक्टर के बिना डोज़ बढ़ाना या घटाना खतरनाक हो सकता है। कृपया अपने डॉक्टर से संपर्क करें।"
        ),
        "hinglish": (
            "🛑 SAFETY POLICY BLOCK: CareSaathi AI dawai ki dose badalne, double karne ya kam karne ki permission nahi deta. "
            "Bina doctor ke dose change karna dangerous ho sakta hai. Please apne doctor se consult karein."
        ),
        "gu": (
            "🛑 સુરક્ષા નીતિ બ્લોક: દવાનો ડોઝ વધારવા કે ઘટાડવાની મનાઈ છે. ડૉક્ટરની સલાહ વિના ડોઝ બદલવો જોખમી હોઈ શકે છે."
        ),
        "bn": (
            "🛑 সুরক্ষা নীতি ব্লক: ওষুধের ডোজ পরিবর্তন করা সম্পূর্ণ নিষিদ্ধ। চিকিৎসকের পরামর্শ ছাড়া ডোজ পরিবর্তন করবেন না।"
        ),
        "mr": (
            "🛑 सुरक्षा धोरण ब्लॉक: औषधाचा डोस बदलणे पूर्णपणे प्रतिबंधित आहे. डॉक्टरांच्या सल्ल्याशिवाय डोस बदलू नका."
        ),
        "te": (
            "🛑 భద్రతా నిబంధన: ఔషధ మోతాదులను మార్చడం ఖచ్చితంగా నిషిద్ధం."
        ),
        "ta": (
            "🛑 பாதுகாப்புக் கொள்கை: மருந்து அளவை மாற்றுவது கண்டிப்பாக தடைசெய்யப்பட்டுள்ளது."
        ),
        "pa": (
            "🛑 ਸੁਰੱਖਿਆ ਨੀਤੀ: ਦਵਾਈ ਦੀ ਖੁਰਾਕ ਬਦਲਣ ਦੀ ਸਖ਼ਤ ਮਨਾਹੀ ਹੈ।"
        )
    },
    "BLOCK_DIAGNOSIS_REQUEST": {
        "en": (
            "SAFETY POLICY BLOCK: CareSaathi AI is a care coordination agent, not a diagnostic medical system. "
            "It cannot diagnose medical conditions or rule out illnesses. "
            "Your symptoms have been logged as 'patient-reported' and added to your progress summary for your doctor."
        ),
        "hi": (
            "🛑 सुरक्षा नीति ब्लॉक: केयरसाथी AI एक केयर कोऑर्डिनेटर है, बीमारी डायग्नोज़ करने वाला डॉक्टर नहीं। "
            "यह किसी बीमारी का निदान नहीं कर सकता। आपके लक्षण 'पेशेंट-रिपोर्टेड' के रूप में डॉक्टर की रिपोर्ट में दर्ज कर लिए गए हैं।"
        ),
        "hinglish": (
            "🛑 SAFETY POLICY BLOCK: CareSaathi AI diagnostic tool nahi hai aur bimari diagnose nahi kar sakta. "
            "Aapke symptoms ko 'patient-reported' ke taur par record karke doctor summary me save kar diya gaya hai."
        ),
        "gu": (
            "🛑 સુરક્ષા નીતિ બ્લોક: CareSaathi AI નિદાન કરતી સિસ્ટમ નથી. તમારા લક્ષણો ડૉક્ટર માટે નોંધવામાં આવ્યા છે."
        ),
        "bn": (
            "🛑 সুরক্ষা নীতি ব্লক: CareSaathi AI কোনো রোগ নির্ণয় করতে পারে না।"
        ),
        "mr": (
            "🛑 सुरक्षा धोरण ब्लॉक: CareSaathi AI आजाराचे निदान करू शकत नाही."
        ),
        "te": (
            "🛑 భద్రతా నిబంధన: CareSaathi AI రోగ నిర్ధారణ చేయదు."
        ),
        "ta": (
            "🛑 பாதுகாப்புக் கொள்கை: CareSaathi AI நோய்களைக் கண்டறிய முடியாது."
        ),
        "pa": (
            "🛑 ਸੁਰੱਖਿਆ ਨੀਤੀ: CareSaathi AI ਬਿਮਾਰੀ ਦੀ ਜਾਂਚ ਨਹੀਂ ਕਰ ਸਕਦਾ।"
        )
    },
    "BLOCK_PRESCRIBE_NEW": {
        "en": (
            "SAFETY POLICY BLOCK: CareSaathi AI cannot prescribe, suggest, or recommend new medications or treatments. "
            "Only your registered healthcare practitioner can prescribe medications based on clinical evaluation."
        ),
        "hi": (
            "🛑 सुरक्षा नीति ब्लॉक: केयरसाथी AI कोई नई दवा या इलाज नहीं लिख सकता। "
            "केवल आपके डॉक्टर ही जांच के बाद नई दवा लिख सकते हैं।"
        ),
        "hinglish": (
            "🛑 SAFETY POLICY BLOCK: CareSaathi AI koi new medicine ya treatment recommend nahi kar sakta. "
            "Sirf registered doctor hi checkup ke baad dawai likh sakte hain."
        ),
        "gu": "🛑 સુરક્ષા નીતિ બ્લોક: નવી દવા લખી શકાતી નથી. ડૉક્ટરની સલાહ લો.",
        "bn": "🛑 সুরক্ষা নীতি ব্লক: নতুন কোনো ওষুধের পরামর্শ দেওয়া সম্ভব নয়।",
        "mr": "🛑 सुरक्षा धोरण ब्लॉक: नवीन औषध सुचवणे प्रतिबंधित आहे.",
        "te": "🛑 భద్రతా నిబంధన: కొత్త మందులను సూచించడం నిషిద్ధం.",
        "ta": "🛑 பாதுகாப்புக் கொள்கை: புதிய மருந்துகளை பரிந்துரைக்க முடியாது.",
        "pa": "🛑 ਸੁਰੱਖਿਆ ਨੀਤੀ: ਨਵੀਂ ਦਵਾਈ ਦੀ ਸਿਫ਼ਾਰਸ਼ ਨਹੀਂ ਕੀਤੀ ਜਾ ਸਕਦੀ।"
    }
}


# Emergency Red Flag Keywords & Scenarios (English, Hindi, Hinglish, Gujarati, Bengali, Marathi, etc.)
EMERGENCY_SCENARIOS = [
    {
        "code": "EMERGENCY_CHEST_PAIN",
        "keywords": [
            r"chest\s+(?:\w+\s+){0,3}pain", r"pain\s+(?:in\s+)?(?:the\s+)?chest", r"chest\s+pressure", r"tightness\s+(?:in\s+)?(?:the\s+)?chest", r"crushing\s+chest", r"pain\s+radiating\s+to\s+(?:arm|jaw|back)",
            r"(?:chhati|seene|chati|dil)\s+(?:me\s+)?(?:\w+\s+){0,3}dard",
            r"(?:छाती|सीने|हार्ट|दिल)\s+(?:में\s+)?(?:\S+\s+){0,3}दर्द",
            r"छातीत\s+(?:\S+\s+){0,2}दुखणे", r"છાતીમાં\s+(?:\S+\s+){0,2}દુખાવો", r"বুকে\s+(?:\S+\s+){0,2}ব্যথা", r"గుండెల్లో\s+నొప్పి", r"நெஞ்சு\s+வலி", r"ਛਾਤੀ\s+ਵਿੱਚ\s+ਦਰਦ"
        ]
    },
    {
        "code": "EMERGENCY_SEVERE_DYSPNEA",
        "keywords": [
            r"severe\s+shortness\s+of\s+breath", r"can'?t\s+breathe", r"struggling\s+to\s+breathe", r"gasping\s+for\s+air", r"choking", r"blue\s+lips",
            r"saans\s+(?:nahi|phool|lene\s+me\s+takleef)", r"sans\s+(?:nahi\s+aa\s+rahi|phool)", r"dum\s+ghut",
            r"सांस\s+(?:लेने\s+में\s+तकलीफ|फूल|नहीं\s+आ\s+रही)", r"श्वास\s+घेण्यास\s+त्रास", r"શ્વાસ\s+લેવામાં\s+તકલીફ", r"শ্বাসকষ্ট", r"శ్వాస\s+ఆడకపోవడం", r"மூச்சுத்\s+திணறல்", r"ਸਾਹ\s+ਲੈਣ\s+ਵਿੱਚ\s+ਤਕਲੀਫ"
        ]
    },
    {
        "code": "EMERGENCY_STROKE_SIGNS",
        "keywords": [
            r"face droop", r"arm weakness", r"slurred speech", r"sudden numbness", r"sudden paralysis", r"loss of balance",
            r"muh tedha", r"mooh tedha", r"awaz ladkhada", r"haath kaam nahi",
            r"लकवा", r"मुंह टेढ़ा", r"बोली लड़खड़ा", r"લકવો", r"పక్షవాతం"
        ]
    },
    {
        "code": "EMERGENCY_ANAPHYLAXIS",
        "keywords": [
            r"swollen throat", r"tongue swelling", r"throat closing", r"anaphylaxis", r"severe allergic reaction",
            r"gala sooj", r"jeebh sooj", r"gala band",
            r"गला सूज", r"जीभ सूज", r"गळा सुजणे", r"ગળું સૂજી"
        ]
    },
    {
        "code": "EMERGENCY_SEVERE_BLEEDING",
        "keywords": [
            r"severe bleeding", r"blood won't stop", r"coughing up blood", r"vomiting blood", r"black tarry stool",
            r"khoon beh raha", r"khoon ki ulti", r"khoon band nahi",
            r"खून बह रहा", r"खून की उल्टी", r"रक्तस्त्राव", r"લોહી નીકળવું", r"রক্তপাত"
        ]
    },
    {
        "code": "EMERGENCY_LOSS_OF_CONSCIOUSNESS",
        "keywords": [
            r"fainted", r"passed out", r"loss of consciousness", r"unresponsive",
            r"behosh", r"chakkar aake gir", r"hosh kho",
            r"बेहोश", r"शुद्ध हरपणे", r"બેભાન", r"অজ্ঞান"
        ]
    }
]

# Clinical Boundary Violations (Actions forbidden by PRD Section 2.4 and 8)
CLINICAL_BOUNDARY_PATTERNS = [
    {
        "code": "BLOCK_CHANGE_DOSAGE",
        "pattern": (
            r"\b(?:increase|decrease|double|halve|cut in half|change|modify|adjust|take 2|take two)\s+(?:the\s+|my\s+)?(?:[a-z0-9\-]+\s+)?(?:dose|dosage|amount|milligrams|mg|tablets?|pills?)|"
            r"\b(?:dose badha|dose kam|dose double|khurak badha|dawai badha|डोज़ बढ़ा|डबल कर|डोज़ कम|ડોઝ વધાર|ડોઝ ડબલ|ডোজ বাড়ਾ)\b"
        )
    },
    {
        "code": "BLOCK_STOP_MEDICATION",
        "pattern": (
            r"\b(?:(?:can i|should i|want to|shall i)\s+(?:stop|discontinue|quit|hold|pause|skip)|stop\s+taking|discontinue|quit\s+taking)\s*(?:the\s+|my\s+)?(?:[a-z0-9\-]+\s+)?(?:tablet|medication|medicine|pill|dose|aspirin|metformin|statin|insulin|blood thinner|antibiotic)?|"
            r"\b(?:[a-z0-9\-]+\s+)?(?:band\s+(?:kar\s+du|kardu|kar\s+sakta|karein|karna|du|dena)|chhod\s+(?:du|sakta|de))|"
            r"\b(?:dawa|dawai|tablet|goli|medicine|medication)\s+band|"
            r"\b(?:दवा|दवाई|गोली)\s*(?:बंद|रोक)|"
            r"\b(?:औषध\s*बंद|દવા\s*(?:બંધ|છોડી)|ওষুধ\s*বন্ধ)\b"
        )
    },
    {
        "code": "BLOCK_DIAGNOSIS_REQUEST",
        "pattern": (
            r"\b(?:do i have|could this be|diagnose|what disease|is this (?:a heart attack|cancer|infection|covid|diabetes|stroke))|"
            r"\b(?:kya mujhe|kya yeh|kya ye|batao kya hua|kya bimari|kya heart attack|क्या मुझे|क्या बीमारी|મને શું થયું|મને હાર્ટ એટેક|কী রোগ হয়েছে)\b"
        )
    },
    {
        "code": "BLOCK_PRESCRIBE_NEW",
        "pattern": (
            r"\b(?:what (?:medicine|pill|tablet|drug) should i take|prescribe|recommend a (?:medicine|cure|remedy))|"
            r"\b(?:kaun si dawa|kya dawa lu|dawai batao|medicine batao|कौन सी दवा लूं|दवा बताओ|કઈ દવા લઉં|কোন ওষুধ খাব)\b"
        )
    }
]


class SafetyWorkflow:
    """Specialist workflow for deterministic safety enforcement and clinical guardrails."""

    @staticmethod
    def get_localized_message(scenario_code: str, language: str = "en") -> str:
        lang = language.lower() if language else "en"
        # Match emergency general
        if scenario_code.startswith("EMERGENCY"):
            trans_dict = LOCALIZED_SAFETY_MESSAGES.get("EMERGENCY", {})
            return trans_dict.get(lang) or trans_dict.get("en")
        else:
            trans_dict = LOCALIZED_SAFETY_MESSAGES.get(scenario_code, {})
            return trans_dict.get(lang) or trans_dict.get("en") or LOCALIZED_SAFETY_MESSAGES["BLOCK_STOP_MEDICATION"]["en"]

    @staticmethod
    def evaluate_text_safety(text: str, language: str = "en") -> Dict[str, Any]:
        """Evaluates arbitrary user input against emergency red flags and clinical boundary blocks."""
        lower = text.lower()
        lang = language.lower() if language else "en"

        # 1. Check for life-threatening emergency scenarios first
        for scenario in EMERGENCY_SCENARIOS:
            for kw in scenario["keywords"]:
                if re.search(kw, lower, re.IGNORECASE):
                    event = SafetyEvent(
                        event_id=f"safe_{int(datetime.now().timestamp() * 1000)}",
                        scenario_code=scenario["code"],
                        triggered_at=datetime.now().isoformat(),
                        trigger_text=text,
                        action_taken="Emergency Escalation Triggered",
                        emergency_level=SafetyEmergencyLevel.EMERGENCY,
                        rule_version="1.0.0",
                        acknowledged_status=False,
                        emergency_contact_number=NATIONAL_EMERGENCY_NUMBER
                    )
                    save_safety_event(event)

                    msg = SafetyWorkflow.get_localized_message("EMERGENCY", lang)
                    return {
                        "is_safe": False,
                        "emergency_level": SafetyEmergencyLevel.EMERGENCY.value,
                        "scenario_code": scenario["code"],
                        "emergency_contact": NATIONAL_EMERGENCY_NUMBER,
                        "message": msg,
                        "requires_immediate_action": True
                    }

        # 2. Check for clinical boundary violations
        for boundary in CLINICAL_BOUNDARY_PATTERNS:
            if re.search(boundary["pattern"], lower, re.IGNORECASE):
                event = SafetyEvent(
                    event_id=f"safe_{int(datetime.now().timestamp() * 1000)}",
                    scenario_code=boundary["code"],
                    triggered_at=datetime.now().isoformat(),
                    trigger_text=text,
                    action_taken="Clinical Boundary Block Enforced",
                    emergency_level=SafetyEmergencyLevel.CLINICAL_BLOCK,
                    rule_version="1.0.0",
                    acknowledged_status=True,
                    emergency_contact_number=None
                )
                save_safety_event(event)

                msg = SafetyWorkflow.get_localized_message(boundary["code"], lang)
                return {
                    "is_safe": False,
                    "emergency_level": SafetyEmergencyLevel.CLINICAL_BLOCK.value,
                    "scenario_code": boundary["code"],
                    "emergency_contact": None,
                    "message": msg,
                    "requires_immediate_action": False
                }

        return {
            "is_safe": True,
            "emergency_level": SafetyEmergencyLevel.NORMAL.value,
            "scenario_code": None,
            "emergency_contact": None,
            "message": "Passed deterministic safety screening."
        }

    @staticmethod
    def evaluate_vital_reading(reading_type: str, value: float) -> Tuple[SafetyEmergencyLevel, Optional[str]]:
        """Evaluates numerical vitals with standard clinical safety thresholds."""
        r_type = reading_type.lower()

        # Blood pressure systolic check
        if "systolic" in r_type or "bp" in r_type:
            if value >= 180:
                return (
                    SafetyEmergencyLevel.EMERGENCY,
                    f"CRITICAL WARNING: Blood pressure reading of {value} mmHg indicates a potential hypertensive crisis. If accompanied by headache, chest pain, or vision changes, CALL {NATIONAL_EMERGENCY_NUMBER} immediately."
                )
            elif value >= 140:
                return (
                    SafetyEmergencyLevel.WARNING,
                    f"Elevated blood pressure ({value} mmHg). Recorded as patient-reported reading for clinician review."
                )
            elif value < 90:
                return (
                    SafetyEmergencyLevel.WARNING,
                    f"Low blood pressure ({value} mmHg). If feeling dizzy or lightheaded, sit down safely and hydrate."
                )

        # Blood glucose check
        if "glucose" in r_type or "sugar" in r_type:
            if value < 60:
                return (
                    SafetyEmergencyLevel.EMERGENCY,
                    f"CRITICAL ALERT: Blood glucose of {value} mg/dL indicates hypoglycemia. Consume 15g fast-acting sugar (fruit juice or glucose tablets) immediately. If confusion or lethargy occurs, seek emergency care."
                )
            elif value > 300:
                return (
                    SafetyEmergencyLevel.WARNING,
                    f"High blood glucose reading ({value} mg/dL). Ensure prescribed hydration and notify clinician if persistent ketones or symptoms occur."
                )

        # SpO2 (Oxygen saturation)
        if "spo2" in r_type or "oxygen" in r_type:
            if value < 92:
                return (
                    SafetyEmergencyLevel.EMERGENCY,
                    f"CRITICAL ALERT: Oxygen saturation of {value}% is below normal threshold. If experiencing shortness of breath, CALL {NATIONAL_EMERGENCY_NUMBER} immediately."
                )

        # Temperature
        if "temp" in r_type:
            if value >= 103.0:
                return (
                    SafetyEmergencyLevel.WARNING,
                    f"High temperature ({value}°F). Recorded as patient-reported symptom. Contact clinician if fever fails to respond to prescribed care plan."
                )

        return SafetyEmergencyLevel.NORMAL, None
