from pyrogram import filters
from bot.client import bot
from pyrogram.enums import ParseMode
from database import supabase_client
from services.gemini_service import analyze_skin_image
from services.cloudinary_service import upload_image


@bot.on_message(filters.photo & filters.private)
async def photo_handler(client, message):
    try:
        telegram_id = message.from_user.id
        
        response = supabase_client.table("bot_users").select("*").eq("telegram_id", telegram_id).execute()
        if not response.data:
            await message.reply_text("Please send /start first.")
            return
            
        bot_user = response.data[0]
        state = bot_user.get("current_state", "idle")
        
        if state == "awaiting_medi_photo":
            from bot.handlers.medi import medi_photo_handler
            await medi_photo_handler(client, message)
            return
        elif state == "awaiting_meal_photo":
            from bot.handlers.weight_handler import meal_photo_handler
            await meal_photo_handler(client, message)
            return
            
        await client.send_chat_action(telegram_id, "typing")
        await message.reply_text("🔬 Analysing your skin image...")
        
        photo = message.photo
        file = await client.download_media(photo, in_memory=True)
        image_bytes = bytes(file.getvalue())
        
        symptoms = message.caption or "No symptoms described"
        
        profile_id = bot_user.get("profile_id")
        profile = {}
        if profile_id:
            prof_resp = supabase_client.table("profiles").select("*").eq("id", profile_id).execute()
            if prof_resp.data:
                profile = prof_resp.data[0]
                
        result = await analyze_skin_image(image_bytes, "image/jpeg", symptoms, profile)
        
        image_url = upload_image(image_bytes, folder=f"dermaassess/users/{profile_id or telegram_id}/skin")
        score = result.get("severity", 5)
        action = result.get("recommended_action", "clinic")
        
        if profile_id:
            supabase_client.table("skin_assessments").insert({
                "user_id": profile_id,
                "image_url": image_url,
                "severity_score": score,
                "contagion_risk": result.get("contagion_risk", "low"),
                "recommended_action": action,
                "diagnosis": result.get("diagnosis", ""),
                "possible_conditions": result.get("possible_conditions", []),
                "advice": result.get("advice", ""),
                "symptoms": symptoms
            }).execute()
            
        action_emoji = {"self-care":"✅", "clinic":"⚠️", "emergency":"🚨"}
        emoji = action_emoji.get(action, "⚠️")
        severity_bar = "█" * score + "░" * (10 - score)
        
        text = f"""
{emoji} *Skin Assessment Result*

*Severity:* {score}/10  {severity_bar}
*Risk level:* {result.get('contagion_risk', 'unknown')}
*Recommended:* {action}

*Assessment:*
{result.get('diagnosis', '')}

*Possible conditions:*
{chr(10).join("• " + c for c in result.get('possible_conditions', []))}

*What to do:*
{result.get('advice', '')}

⚠️ _AI guidance only — not a medical diagnosis._
_Always consult a qualified doctor._
"""
        await message.reply_text(text.strip(), parse_mode=ParseMode.MARKDOWN)
        
        if score >= 7:
            await message.reply_text("🚨 *URGENT:* This appears serious. Please seek immediate medical attention.", parse_mode=ParseMode.MARKDOWN)
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Skin photo error: {e}")
        await message.reply_text("Sorry, something went wrong. Please try again or send /start")
