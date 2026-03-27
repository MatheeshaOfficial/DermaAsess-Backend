import traceback
from pyrogram.enums import ParseMode
from database import supabase_client

def _format_skin_telegram(data: dict) -> str:
    action = data.get("recommended_action", "")
    emoji = "✅" if action == "self-care" else "⚠️" if action == "clinic" else "🚨"
    score = data.get("severity_score", data.get("severity", 0))
    diagnosis = data.get("diagnosis", data.get("ai_diagnosis", ""))
    advice = data.get("advice", data.get("ai_advice", ""))
    return f"{emoji} *Skin Assessment Complete*\n\nSeverity: {score}/10\nAction: {action}\n{diagnosis}\n\n💡 {advice[:200]}...\n\nOpen the app to see full results."

def _format_prescription_telegram(data: dict) -> str:
    safety = data.get("overall_safety", "")
    emoji = "✅" if safety == "safe" else "⚠️" if safety == "caution" else "🚨"
    count = data.get("medicines_count", 0)
    advice = data.get("safety_advice", "")
    interactions = data.get("interactions", [])
    allergy_alerts = data.get("allergy_alerts", [])
    
    text = f"{emoji} *Prescription Scanned*\n\nMedicines found: {count}\nSafety: {safety}\n{advice}\n"
    if interactions:
        text += "\n⚠️ Interactions detected — check the app"
    if allergy_alerts:
        text += "\n🚨 Allergy alert — check the app immediately"
    return text

def _format_weight_telegram(data: dict) -> str:
    w = data.get("weight_kg", 0)
    meal = data.get("meal_description")
    cal = data.get("calories")
    adv = data.get("ai_advice", "Keep it up!")
    
    text = f"✅ *Weight Logged*\n\n⚖️ {w} kg\n"
    if meal:
        text += f"🍽️ Meal: {meal}\n"
    if cal:
        text += f"🔥 ~{cal} kcal\n"
    text += f"\n💡 {adv}"
    return text

def _format_skin_email(data: dict) -> dict:
    return {"subject": "Skin Assessment Complete", "html_body": f"<h1>Skin Assessment</h1><p>Action: {data.get('recommended_action')}</p>"}

def _format_prescription_email(data: dict) -> dict:
     return {"subject": "Prescription Checked", "html_body": f"<h1>Prescription Scan</h1><p>Safety: {data.get('overall_safety')}</p>"}

def _format_weight_email(data: dict) -> dict:
    return {"subject": "Weight Logged", "html_body": f"<h1>Weight Logged</h1><p>{data.get('weight_kg')} kg</p>"}

async def notify_user(user_id: str, event_type: str, data: dict):
    from services.email_service import send_email
    from bot.client import bot # dynamic import
    
    try:
        
        response = supabase_client.table("profiles").select("*").eq("id", user_id).execute()
        if not response.data:
            return
            
        profile = response.data[0]
        telegram_id = profile.get("telegram_id")
        email = profile.get("email")
        pref = profile.get("notification_channel", "telegram")

        should_send_telegram = telegram_id and (pref in ["telegram", "both"] or event_type == "emergency")
        should_send_email = email and (pref in ["email", "both"] or event_type == "emergency")

        # Fallback
        if telegram_id and not email and not should_send_telegram:
            should_send_telegram = True
        if email and not telegram_id and not should_send_email:
            should_send_email = True

        if should_send_telegram:
            text = ""
            if event_type in ["skin_assessment", "emergency"]:
                text = _format_skin_telegram(data)
            elif event_type == "prescription_scan":
                text = _format_prescription_telegram(data)
            elif event_type == "weight_logged":
                text = _format_weight_telegram(data)
                
            if text:
                try:
                    await bot.send_message(telegram_id, text, parse_mode=ParseMode.MARKDOWN)
                    if event_type == "emergency":
                        await bot.send_message(telegram_id, "🚨 *URGENT:* This appears serious. Please seek immediate medical attention or call emergency services.", parse_mode=ParseMode.MARKDOWN)
                except Exception as e:
                    print(f"Failed to send telegram msg: {e}")

        if should_send_email:
            subject, html_body = "", ""
            if event_type in ["skin_assessment", "emergency"]:
                edata = _format_skin_email(data)
                subject, html_body = edata["subject"], edata["html_body"]
            elif event_type == "prescription_scan":
                edata = _format_prescription_email(data)
                subject, html_body = edata["subject"], edata["html_body"]
            elif event_type == "weight_logged":
                edata = _format_weight_email(data)
                subject, html_body = edata["subject"], edata["html_body"]

            if subject and html_body:
                await send_email(email, subject, html_body)

    except Exception:
        print("Notification error:", traceback.format_exc())
