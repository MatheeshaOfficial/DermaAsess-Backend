from pyrogram import filters
from pyrogram.enums import ParseMode, ChatAction
from bot.client import bot
from database import supabase_client
from services.gemini_service import ocr_prescription, check_drug_safety
from services.cloudinary_service import upload_image
from services.notification_service import notify_user


@bot.on_message(filters.command("medi") & filters.private)
async def medi_command_handler(client, message):
    try:
        telegram_id = message.from_user.id
        supabase_client.table("bot_users").update({"current_state": "awaiting_medi_photo"}).eq("telegram_id", telegram_id).execute()
        
        await message.reply_text(
            "💊 *Prescription Scanner*\n\n"
            "Send me a photo of:\n"
            "• A prescription (handwritten or printed)\n"
            "• A medicine packet or label\n"
            "• A pill bottle\n\n"
            "I'll extract all medicines and check for safety issues.",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        await message.reply_text("Sorry, try again later.")

async def medi_photo_handler(client, message):
    try:
        telegram_id = message.from_user.id
        supabase_client.table("bot_users").update({"current_state": "idle"}).eq("telegram_id", telegram_id).execute()
        
        await client.send_chat_action(telegram_id, ChatAction.TYPING)
        await message.reply_text("💊 Reading your prescription...")
        
        file = await client.download_media(message.photo, in_memory=True)
        img_bytes = bytes(file.getvalue())
        
        resp = supabase_client.table("bot_users").select("profile_id").eq("telegram_id", telegram_id).execute()
        profile_id = resp.data[0]["profile_id"] if resp.data else None
        profile = {}
        if profile_id:
            p_resp = supabase_client.table("profiles").select("*").eq("id", profile_id).execute()
            if p_resp.data: profile = p_resp.data[0]
            
        ocr_res = await ocr_prescription(img_bytes, "image/jpeg")
        medicines = ocr_res.get("medicines", [])
        
        safety_res = await check_drug_safety(medicines, profile)
        
        if profile_id:
            img_url = upload_image(img_bytes, f"dermaassess/users/{profile_id}/prescriptions")
            supabase_client.table("prescriptions").insert({
               "user_id": profile_id,
               "image_url": img_url,
               "medicines_found": medicines,
               "medicines_count": len(medicines),
               "overall_safety": safety_res.get("overall_safety", "caution"),
               "safety_advice": safety_res.get("advice", ""),
               "interactions": safety_res.get("interactions", []),
               "allergy_alerts": safety_res.get("allergy_alerts", [])
            }).execute()
        
        safety = safety_res.get('overall_safety', 'caution')
        emoji = "✅" if safety == "safe" else "⚠️" if safety == "caution" else "🚨"
        count = len(medicines)
        meds_txt = "\n".join(f"• *{m.get('name')}* — {m.get('dosage','')}, {m.get('frequency','')}" for m in medicines)
        
        text = f"{emoji} *Prescription Scan Complete*\n\n*Medicines found ({count}):*\n{meds_txt}\n\n*Safety:* {safety}\n{safety_res.get('advice', '')}\n"
        if safety_res.get("interactions"):
            text += "\n⚠️ *Interactions:*\n" + "\n".join(safety_res["interactions"])
        if safety_res.get("allergy_alerts"):
            text += "\n🚨 *Allergy alerts:*\n" + "\n".join(safety_res["allergy_alerts"])
            
        text += "\n\n_Always verify with your pharmacist before taking medication._"
        await message.reply_text(text.strip(), parse_mode=ParseMode.MARKDOWN)
        
        if profile_id:
            await notify_user(profile_id, "prescription_scan", {
                "medicines_count": count,
                "overall_safety": safety,
                "safety_advice": safety_res.get("advice"),
                "interactions": safety_res.get("interactions", []),
                "allergy_alerts": safety_res.get("allergy_alerts", [])
            })
            
    except Exception as e:
        print(f"Medi photo error: {e}")
        await message.reply_text("Sorry, something went wrong reading the prescription.")
        supabase_client.table("bot_users").update({"current_state": "idle"}).eq("telegram_id", message.from_user.id).execute()
