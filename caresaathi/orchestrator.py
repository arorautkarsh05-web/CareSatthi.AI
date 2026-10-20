"""CareSaathi Orchestrator.
Central coordination engine for intent routing, workflow dispatch, and safety screening.
Includes rich multilingual capabilities (English, Hindi, Hinglish, Gujarati, Bengali, Marathi, Telugu, Tamil, Punjabi).
"""
import re
from typing import Dict, Any, Optional, List
from caresaathi.models import TaskStatus
from caresaathi.plan_workflow import PlanWorkflow
from caresaathi.routine_workflow import RoutineWorkflow
from caresaathi.monitoring_workflow import MonitoringWorkflow
from caresaathi.safety_workflow import SafetyWorkflow
from caresaathi.report_workflow import ReportWorkflow
from caresaathi.db import init_db, get_latest_care_plan


LOCALIZED_HELP_MESSAGES = {
    "en": (
        "CareSaathi AI is ready to help coordinate your doctor-approved care plan. You can:\n"
        "1. Paste a care plan to extract tasks with source links.\n"
        "2. Say 'confirm plan' to activate proposed tasks.\n"
        "3. Ask for 'today's checklist' to see your routine.\n"
        "4. Update a task (e.g., 'mark plan_t01 as completed').\n"
        "5. Log a symptom or vital reading (e.g., 'logged BP 120/80').\n"
        "6. Say 'generate report' to compile a clinician progress summary."
    ),
    "hi": (
        "केयरसाथी AI आपकी डॉक्टर द्वारा अनुमोदित देखभाल योजना में सहायता के लिए तैयार है। आप कह सकते हैं:\n"
        "1. 'आज की चेकलिस्ट दिखाओ' - आज की दवाइयाँ और काम देखने के लिए।\n"
        "2. 'प्लान कन्फर्म करो' - डॉक्टर के प्लान को सक्रिय करने के लिए।\n"
        "3. 'सिरदर्द हो रहा है' या 'BP 120/80' - लक्षण या रीडिंग दर्ज करने के लिए।\n"
        "4. 'रिपोर्ट बनाओ' - डॉक्टर के लिए प्रगति रिपोर्ट तैयार करने के लिए।"
    ),
    "hinglish": (
        "CareSaathi AI aapke doctor-approved care plan ko coordinate karne ke liye ready hai! Aap bol sakte hain:\n"
        "1. 'Aaj ka checklist dikhao' - Today's routine dekhne ke liye.\n"
        "2. 'Confirm plan' - Extracted tasks activate karne ke liye.\n"
        "3. 'Sir dard ho raha hai' ya 'BP 130/85' - Symptom ya vitals log karne ke liye.\n"
        "4. 'Report banao' - Doctor ke liye progress summary generate karne ke liye."
    ),
    "gu": (
        "CareSaathi AI તમારા ડૉક્ટર દ્વારા મંજૂર કેર પ્લાનને ટ્રેક કરવા માટે તૈયાર છે:\n"
        "1. 'આજનો ચેકલિસ્ટ બતાવો' - આજની દવાઓ અને નિયમિત કામ જોવા માટે.\n"
        "2. 'પ્લાન કન્ફર્મ કરો' - કાર્યો સક્રિય કરવા માટે.\n"
        "3. 'માથું દુખે છે' અથવા 'BP 125/80' - લક્ષણો કે રીડિંગ નોંધવા માટે.\n"
        "4. 'રિપોર્ટ બનાવો' - ડૉક્ટર માટે પ્રોગ્રેસ રિપોર્ટ તૈયાર કરવા માટે."
    ),
    "bn": (
        "CareSaathi AI আপনার ডাক্তারের অনুমোদিত যত্নের পরিকল্পনা সমন্বয় করতে প্রস্তুত:\n"
        "1. 'আজকের চেকলিস্ট দেখাও' - আজকের ওষুধ ও রুটিন দেখতে।\n"
        "2. 'প্ল্যান নিশ্চিত করুন' - কাজ সক্রিয় করতে।\n"
        "3. 'মাথা ব্যথা করছে' - উপসর্গ রেকর্ড করতে।\n"
        "4. 'প্রতিবেদন তৈরি করুন' - ডাক্তারের জন্য রিপোর্ট তৈরি করতে।"
    ),
    "mr": (
        "CareSaathi AI तुमच्या डॉक्टरांच्या काळजी योजनेचे समन्वय साधण्यासाठी सज्ज आहे:\n"
        "1. 'आजची चेकलिस्ट दाखवा' - आजची औषधे आणि दिनचर्या पाहण्यासाठी.\n"
        "2. 'प्लॅन कन्फर्म करा' - कार्ये सक्रिय करण्यासाठी.\n"
        "3. 'डोकेदुखी होत आहे' - लक्षणे नोंदवण्यासाठी.\n"
        "4. 'अहवाल तयार करा' - डॉक्टरांसाठी प्रगती अहवाल मिळवण्यासाठी."
    ),
    "te": (
        "CareSaathi AI మీ వైద్యుడి సంరక్షణ ప్రణాళికను నిర్వహించడానికి సిద్ధంగా ఉంది:\n"
        "1. 'నేటి చెక్‌లిస్ట్ చూపించు' - నేటి మందులను చూడటానికి.\n"
        "2. 'ప్లాన్ నిర్ధారించండి' - పనులను యాక్టివేట్ చేయడానికి.\n"
        "3. 'రిపోర్ట్ రూపొందించండి' - వైద్యుడి నివేదిక పొందడానికి."
    ),
    "ta": (
        "CareSaathi AI உங்கள் மருத்துவ பராமரிப்புத் திட்டத்தை நிர்வகிக்கத் தயாராக உள்ளது:\n"
        "1. 'இன்றைய பட்டியல்' - அன்றாட மருந்துகளைப் பார்க்க.\n"
        "2. 'திட்டத்தை உறுதிப்படுத்து' - பணிகளைச் செயல்படுத்த.\n"
        "3. 'அறிக்கை உருவாக்கு' - மருத்துவ முன்னேற்ற அறிக்கையைப் பெற."
    ),
    "pa": (
        "CareSaathi AI ਤੁਹਾਡੀ ਡਾਕਟਰ ਦੁਆਰਾ ਪ੍ਰਵਾਨਿਤ ਦੇਖਭਾਲ ਯੋਜਨਾ ਵਿੱਚ ਮਦਦ ਲਈ ਤਿਆਰ ਹੈ:\n"
        "1. 'ਅੱਜ ਦੀ ਚੈੱਕਲਿਸਟ' - ਅੱਜ ਦੀਆਂ ਦਵਾਈਆਂ ਦੇਖਣ ਲਈ।\n"
        "2. 'ਰਿਪੋਰਟ ਬਣਾਓ' - ਡਾਕਟਰ ਲਈ ਰਿਪੋਰਟ ਤਿਆਰ ਕਰਨ ਲਈ।"
    )
}


class CareSaathiOrchestrator:
    """Orchestrates workflows across Plan, Routine, Monitoring, Safety, and Report agents."""

    def __init__(self):
        init_db()

    def process_message(
        self,
        user_message: str,
        patient_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        language: str = "en"
    ) -> Dict[str, Any]:
        """Routes a natural language message with multilingual safety screening and responses."""
        text = user_message.strip()
        lower = text.lower()
        patient_id = patient_id or "Demo-Patient-01"
        lang = (language or "en").lower()

        # 1. Deterministic Safety Check on all incoming text FIRST (PRD Principle 6)
        safety_eval = SafetyWorkflow.evaluate_text_safety(text, language=lang)
        if not safety_eval["is_safe"]:
            return {
                "intent": "SAFETY_INTERVENTION",
                "status": "blocked" if safety_eval["emergency_level"] == "clinical_block" else "emergency",
                "emergency_level": safety_eval["emergency_level"],
                "emergency_contact": safety_eval.get("emergency_contact"),
                "message": safety_eval["message"],
                "requires_immediate_action": safety_eval.get("requires_immediate_action", False),
                "language": lang
            }

        # 2. Intent Detection with Multilingual Keywords
        # Intent: Report Generation
        report_keywords = [
            "report", "doctor summary", "clinical summary", "weekly summary", "progress summary",
            "रिपोर्ट", "રિપોર્ટ", "প্রতিবেদন", "अहवाल", "నివేదిక", "அறிக்கை", "ਰਿਪੋਰਟ", "report banao", "summary banao"
        ]
        if any(w in lower for w in report_keywords):
            res = ReportWorkflow.generate_progress_report(patient_id)
            msg = self._format_report_message(res, lang)
            return {
                "intent": "GENERATE_REPORT",
                "status": "success",
                "data": res,
                "message": msg,
                "language": lang
            }

        # Intent: Daily Checklist
        checklist_keywords = [
            "checklist", "today's tasks", "todays tasks", "schedule", "routine", "what do i take today", "my tasks",
            "चेकलिस्ट", "आज की दवा", "आज के काम", "रूटीन", "आज क्या लेना है",
            "aaj ka checklist", "aaj ki dawai", "aaj kya lena hai", "routine batao", "tasks dikhao",
            "ચેકલિસ્ટ", "આજની દવાઓ", "આજના કામ",
            "চেকলিস্ট", "আজকের ওষুধ", "আজকের কাজ",
            "चेकलिस्ट", "आजची औषधे", "आजचे काम",
            "చెక్‌లిస్ట్", "నేటి మందులు", "పட்டியல்", "இன்றைய மருந்துகள்", "ਚੈੱਕਲਿਸਟ", "ਅੱਜ ਦੀਆਂ ਦਵਾਈਆਂ"
        ]
        if any(w in lower for w in checklist_keywords):
            res = RoutineWorkflow.get_daily_checklist(patient_id)
            msg = self._format_checklist_message(res, lang)
            return {
                "intent": "GET_CHECKLIST",
                "status": "success",
                "data": res,
                "message": msg,
                "language": lang
            }

        # Intent: Confirm Care Plan
        confirm_keywords = [
            "confirm plan", "confirm tasks", "approve plan", "activate plan", "confirm all",
            "प्लान कन्फर्म", "plan confirm", "कन्फर्म करो", "પ્લાન કન્ફર્મ", "প্ল্যান নিশ্চিত", "प्लॅन कन्फर्म"
        ]
        if any(w in lower for w in confirm_keywords):
            latest_plan = get_latest_care_plan(patient_id)
            if not latest_plan:
                err_msg = {
                    "en": "No draft care plan found to confirm. Please submit a care plan first.",
                    "hi": "कन्फर्म करने के लिए कोई ड्राफ्ट केयर प्लान नहीं मिला। कृपया पहले प्लान पेस्ट करें।",
                    "hinglish": "Confirm karne ke liye koi draft care plan nahi mila. Pehle plan submit karein.",
                    "gu": "કન્ફર્મ કરવા માટે કોઈ ડ્રાફ્ટ પ્લાન મળ્યો નથી.",
                    "bn": "নিশ্চিত করার জন্য কোনো ড্রাফট প্ল্যান পাওয়া যায়নি।"
                }.get(lang, "No draft care plan found to confirm.")
                return {
                    "intent": "CONFIRM_PLAN",
                    "status": "error",
                    "message": err_msg,
                    "language": lang
                }
            res = PlanWorkflow.confirm_care_plan(latest_plan.plan_id)
            conf_msg = {
                "en": res["message"],
                "hi": f"✅ कन्फर्मेशन गेट पास: {res['confirmed_tasks_count']} काम स्वीकृत और आज की चेकलिस्ट में सक्रिय हैं।",
                "hinglish": f"✅ Confirmation Gate passed: {res['confirmed_tasks_count']} tasks confirm ho kar daily checklist me active ho gaye hain.",
                "gu": f"✅ કન્ફર્મેશન ગેટ પાસ: {res['confirmed_tasks_count']} કાર્યો દૈનિક ચેકલિસ્ટમાં સક્રિય થયા છે."
            }.get(lang, res["message"])
            return {
                "intent": "CONFIRM_PLAN",
                "status": "success",
                "data": res,
                "message": conf_msg,
                "language": lang
            }

        # Intent: Task Status Update (e.g. "Mark task p1_t01 as completed" or "completed aspirin")
        update_match = re.search(r"(?:mark|set)?\s*(?:task\s+)?([a-zA-Z0-9_\-]+)\s+(?:as\s+)?(completed|done|skipped|delayed|pending|ho gayi|le li|pura)", lower)
        if update_match:
            task_id, raw_status = update_match.groups()
            status_map = {
                "done": "completed", "completed": "completed", "ho gayi": "completed", "le li": "completed", "pura": "completed",
                "skipped": "skipped", "delayed": "delayed", "pending": "pending"
            }
            mapped_status = status_map.get(raw_status, "completed")
            res = RoutineWorkflow.update_task_status(task_id, mapped_status)
            update_msg = {
                "en": res["message"],
                "hi": f"✅ टास्क '{task_id}' को {mapped_status} के रूप में मार्क कर दिया गया है।",
                "hinglish": f"✅ Task '{task_id}' ko {mapped_status} mark kar diya gaya hai.",
                "gu": f"✅ કાર્ય '{task_id}' {mapped_status} તરીકે નોંધાયું છે."
            }.get(lang, res["message"])
            return {
                "intent": "UPDATE_TASK",
                "status": res["status"],
                "data": res,
                "message": update_msg,
                "language": lang
            }

        # Intent: Symptom Logging
        symptom_keywords = [
            "symptom", "feeling", "pain", "nausea", "headache", "dizzy", "fatigue", "fever", "cough", "swelling", "vomit", "cramp",
            "दर्द", "सिरदर्द", "चक्कर", "बुखार", "उल्टी", "खांसी", "कमजोरी", "थकान",
            "sir dard", "chakkar", "bukhar", "khansi", "dizzy", "vomit", "vomiting", "dard ho raha", "pet dard",
            "દુખાવો", "માથું દુખે છે", "તાવ", "ચક્કર",
            "ব্যথা", "মাথা ব্যথা", "জ্বর", "বমি",
            "दुखणे", "डोकेदुखी", "ताप", "चक्कर",
            "నొప్పి", "తలనెప్పి", "జ్వరం", "வலி", "தலைவலி", "காய்ச்சல்", "ਸਿਰ ਦਰਦ", "ਬੁਖਾਰ"
        ]
        if any(w in lower for w in symptom_keywords):
            res = MonitoringWorkflow.log_symptom(synthetic_patient_id=patient_id, description=text)
            sym_msg = {
                "en": res["message"] + f" Logged: '{text}'.",
                "hi": f"📝 लक्षण दर्ज: '{text}'। यह जानकारी 'पेशेंट-रिपोर्टेड' के रूप में सुरक्षित की गई है।",
                "hinglish": f"📝 Symptom logged: '{text}'. Isse patient-reported observation ke taur par save kar liya gaya hai.",
                "gu": f"📝 લક્ષણ નોંધાયું: '{text}'. આ દર્દી-રિપોર્ટેડ માહિતી તરીકે સંગ્રહિત છે.",
                "bn": f"📝 লক্ষণ নথিভুক্ত করা হয়েছে: '{text}'।"
            }.get(lang, res["message"])
            return {
                "intent": "LOG_SYMPTOM",
                "status": "success",
                "data": res,
                "message": sym_msg,
                "language": lang
            }

        # Intent: Care Plan Setup / Ingestion
        if "\n" in text or any(w in lower for w in ["tab ", "mg ", "twice daily", "care plan", "instructions:", "take 1", "take 2", "डॉक्टर का पर्चा"]):
            plan_id = f"plan_{int(datetime.now().timestamp() * 1000)}"
            res = PlanWorkflow.process_new_care_plan(
                plan_id=plan_id,
                synthetic_patient_id=patient_id,
                patient_name="Synthetic Patient",
                doctor_name="Treating Clinician",
                diagnosis_context="Doctor Care Plan",
                source_text=text
            )
            ingest_msg = {
                "en": f"Care plan extracted successfully! {res['total_tasks']} tasks parsed with source links. Say 'confirm plan' to activate them.",
                "hi": f"केयर प्लान सफलतापूर्वक निकाला गया! {res['total_tasks']} काम स्रोत के साथ जोड़े गए हैं। सक्रिय करने के लिए 'प्लान कन्फर्म' कहें।",
                "hinglish": f"Care plan successfully extract ho gaya! {res['total_tasks']} tasks source snippets ke sath parse ho gaye hain. Inhe activate karne ke liye 'confirm plan' bolein.",
                "gu": f"કેર પ્લાન સફળતાપૂર્વક મેળવાયો! {res['total_tasks']} કાર્યો પાર્સ થયા છે. સક્રિય કરવા માટે 'કન્ફર્મ' કહો."
            }.get(lang, res["message"])
            return {
                "intent": "SET_PLAN",
                "status": "success",
                "data": res,
                "message": ingest_msg,
                "language": lang
            }

        # Fallback informative guidance in selected language
        help_msg = LOCALIZED_HELP_MESSAGES.get(lang, LOCALIZED_HELP_MESSAGES["en"])
        return {
            "intent": "GENERAL_QUERY",
            "status": "info",
            "message": help_msg,
            "language": lang
        }

    def _format_checklist_message(self, res: Dict[str, Any], lang: str) -> str:
        items = res.get("checklist", [])
        if not items:
            empty_msgs = {
                "en": "No confirmed tasks found for today. Please confirm a doctor care plan first.",
                "hi": "आज के लिए कोई सक्रिय दवा या काम नहीं मिला। कृपया पहले डॉक्टर का प्लान कन्फर्म करें।",
                "hinglish": "Aaj ke liye koi confirmed task nahi mila. Pehle Step 1 me doctor plan confirm karein.",
                "gu": "આજ માટે કોઈ કાર્ય મળ્યું નથી. કૃપા કરીને પ્રથમ પ્લાન કન્ફર્મ કરો."
            }
            return empty_msgs.get(lang, empty_msgs["en"])

        counts = res.get("counts", {})
        header_map = {
            "en": f"📋 Today's Care Checklist ({counts.get('completed', 0)}/{len(items)} completed):\n",
            "hi": f"📋 आज की केयर चेकलिस्ट ({counts.get('completed', 0)}/{len(items)} पूर्ण):\n",
            "hinglish": f"📋 Aaj ka Daily Care Checklist ({counts.get('completed', 0)}/{len(items)} completed):\n",
            "gu": f"📋 આજનો કેર ચેકલિસ્ટ ({counts.get('completed', 0)}/{len(items)} પૂર્ણ):\n"
        }
        lines = [header_map.get(lang, header_map["en"])]
        for i, item in enumerate(items[:6], 1):
            status_icon = "✅" if item["status"] == "completed" else ("⏳" if item["status"] == "delayed" else "⏰")
            lines.append(f"{i}. {status_icon} [{item['scheduled_time']}] {item['instruction_text']} ({item['status'].upper()})")

        if len(items) > 6:
            lines.append(f"... (+{len(items)-6} more tasks in Checklist tab)")

        return "\n".join(lines)

    def _format_report_message(self, res: Dict[str, Any], lang: str) -> str:
        rate = res.get("adherence_rate", 0)
        task_counts = res.get("task_counts", {})
        header_map = {
            "en": (
                f"📄 Clinician Progress Report Generated!\n"
                f"• Adherence Rate: {rate}%\n"
                f"• Tasks: {task_counts.get('completed', 0)} completed, {task_counts.get('pending', 0)} pending\n"
                f"• Patient-Reported Symptoms: {res.get('total_symptoms', 0)}\n"
                f"• Unresolved Questions for Doctor: {res.get('unresolved_questions_count', 0)}\n"
                "View the complete formatted report in the 'Doctor Progress Report' tab."
            ),
            "hi": (
                f"📄 डॉक्टर प्रगति रिपोर्ट तैयार हो गई है!\n"
                f"• पालन दर (Adherence): {rate}%\n"
                f"• काम: {task_counts.get('completed', 0)} पूर्ण, {task_counts.get('pending', 0)} बाकी\n"
                f"• मरीज द्वारा दर्ज लक्षण: {res.get('total_symptoms', 0)}\n"
                f"• डॉक्टर के लिए प्रश्न: {res.get('unresolved_questions_count', 0)}\n"
                "पूरी रिपोर्ट 'Doctor Progress Report' टैब में देखें।"
            ),
            "hinglish": (
                f"📄 Clinician Progress Report Generate ho gaya hai!\n"
                f"• Adherence Rate: {rate}%\n"
                f"• Tasks: {task_counts.get('completed', 0)} complete, {task_counts.get('pending', 0)} pending\n"
                f"• Patient-Reported Symptoms: {res.get('total_symptoms', 0)}\n"
                f"• Unresolved Questions for Doctor: {res.get('unresolved_questions_count', 0)}\n"
                "Poora report 'Doctor Progress Report' tab me view aur print kar sakte hain."
            ),
            "gu": (
                f"📄 ડૉક્ટર પ્રોગ્રેસ રિપોર્ટ તૈયાર છે!\n"
                f"• પાલન દર: {rate}%\n"
                f"• કાર્યો: {task_counts.get('completed', 0)} પૂર્ણ, {task_counts.get('pending', 0)} બાકી\n"
                f"• દર્દી દ્વારા નોંધાયેલ લક્ષણો: {res.get('total_symptoms', 0)}\n"
                "સંપૂર્ણ રિપોર્ટ 'Doctor Progress Report' ટેબમાં જુઓ."
            )
        }
        return header_map.get(lang, header_map["en"])
