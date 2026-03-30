from pyrogram import filters
from bot.client import bot
from pyrogram.enums import ParseMode, ChatAction
from database import supabase_client
from services.gemini_service import chat_with_dermabot


@bot.on_message(filters.text & filters.private & ~filters.regex(r"^/"))
async def text_handler(client, message):
    try:
        telegram_id = message.from_user.id
        text = message.text
        
        response = supabase_client.table("bot_users").select("*").eq("telegram_id", telegram_id).execute()
        if not response.data:
            await message.reply_text("Please send /start first.")
            return
            
        bot_user = response.data[0]
        state = bot_user.get("current_state", "idle")
        
        if state == "awaiting_age":
            try:
                age = int(text)
                if 1 <= age <= 120:
                    supabase_client.table("bot_users").update({"current_state": "awaiting_height"}).eq("telegram_id", telegram_id).execute()
                    profile_id = bot_user.get("profile_id")
                    if profile_id: supabase_client.table("profiles").update({"age": age}).eq("id", profile_id).execute()
                    await message.reply_text("Height in cm? (e.g. 170)")
                else:
                    await message.reply_text("Please send a valid age (e.g. 25)")
            except ValueError:
                await message.reply_text("Please send a valid age (e.g. 25)")
                
        elif state == "awaiting_height":
            try:
                height = float(text)
                if 50 <= height <= 300:
                    supabase_client.table("bot_users").update({"current_state": "awaiting_weight"}).eq("telegram_id", telegram_id).execute()
                    profile_id = bot_user.get("profile_id")
                    if profile_id: supabase_client.table("profiles").update({"height": height}).eq("id", profile_id).execute()
                    await message.reply_text("Weight in kg? (e.g. 65.5)")
                else:
                    await message.reply_text("Please send height in cm (e.g. 170)")
            except ValueError:
                await message.reply_text("Please send height in cm (e.g. 170)")
                
        elif state == "awaiting_weight":
            try:
                weight = float(text)
                if 20 <= weight <= 500:
                    supabase_client.table("bot_users").update({"current_state": "awaiting_allergies"}).eq("telegram_id", telegram_id).execute()
                    profile_id = bot_user.get("profile_id")
                    if profile_id: supabase_client.table("profiles").update({"weight": weight}).eq("id", profile_id).execute()
                    await message.reply_text("Any known allergies?\n(e.g. Penicillin, Aspirin, Latex)\nType them separated by commas, or type <b>none</b>", parse_mode=ParseMode.HTML)
                else:
                    await message.reply_text("Please send weight in kg (e.g. 65.5)")
            except ValueError:
                await message.reply_text("Please send weight in kg (e.g. 65.5)")
                
        elif state == "awaiting_allergies":
            allergies = [] if text.lower() == "none" else [a.strip() for a in text.split(",")]
            supabase_client.table("bot_users").update({"current_state": "awaiting_conditions"}).eq("telegram_id", telegram_id).execute()
            profile_id = bot_user.get("profile_id")
            if profile_id: supabase_client.table("profiles").update({"allergies": allergies}).eq("id", profile_id).execute()
            await message.reply_text("Any chronic conditions?\n(e.g. Diabetes, Hypertension, Asthma)\nType them separated by commas, or type <b>none</b>", parse_mode=ParseMode.HTML)
            
        elif state == "awaiting_conditions":
            conditions = [] if text.lower() == "none" else [c.strip() for c in text.split(",")]
            profile_id = bot_user.get("profile_id")
            if profile_id:
                prof_resp = supabase_client.table("profiles").update({"conditions": conditions}).eq("id", profile_id).execute()
                profile = prof_resp.data[0]
            else:
                profile = {"age": "N/A", "height": "N/A", "weight": "N/A", "allergies": [], "conditions": []}
            
            supabase_client.table("bot_users").update({"onboarded": True, "current_state": "idle"}).eq("telegram_id", telegram_id).execute()
            
            al_str = ", ".join(profile.get("allergies", [])) or 'None'
            cond_str = ", ".join(profile.get("conditions", [])) or 'None'
            
            await message.reply_text(
                f"✅ <b>Profile complete!</b>\n\nAge: {profile.get('age', 'N/A')} | Height: {profile.get('height', 'N/A')}cm | Weight: {profile.get('weight', 'N/A')}kg\n"
                f"Allergies: {al_str}\nConditions: {cond_str}\n\n"
                "You're all set! You can now:\n📸 Send me a photo of a skin concern\n/medi — scan a prescription\n/weight — log your weight\n\n"
                "🌐 <b>Web app login:</b> Visit dermaassess.vercel.app\nand click 'Login with Telegram' — your account is ready!", parse_mode=ParseMode.HTML)
            
        elif state == "awaiting_weight_input":
            try:
                weight = float(text)
                
                # Direct save to DB instead of waiting for meal image
                supabase_client.table("bot_users").update({"current_state": "idle"}).eq("telegram_id", telegram_id).execute()
                
                profile_id = bot_user.get("profile_id")
                trend_text = "→ stable"
                if profile_id:
                    prev_logs = supabase_client.table("weight_logs").select("weight_kg").eq("user_id", profile_id).order("created_at", desc=True).limit(1).execute()
                    if prev_logs.data:
                        prev_w = prev_logs.data[0]["weight_kg"]
                        trend_text = "▼ down" if weight < prev_w else "▲ up" if weight > prev_w else "→ stable"
                    
                    supabase_client.table("weight_logs").insert({"user_id": profile_id, "weight_kg": weight}).execute()
                    supabase_client.table("profiles").update({"weight": weight}).eq("id", profile_id).execute()
                    
                await message.reply_text(
                    f"✅ <b>Weight logged: {weight}kg</b>\n\nTrend: {trend_text} from last entry\n\n💪 Keep it consistent — you're doing great!", 
                    parse_mode=ParseMode.HTML
                )
            except ValueError:
                await message.reply_text("Please send your weight as a number in kg (e.g. 68.5)", parse_mode=ParseMode.HTML)
                
        elif state == "idle":
            if not bot_user.get("onboarded"):
                await message.reply_text("Please complete setup first — send /start")
                return
            await client.send_chat_action(telegram_id, ChatAction.TYPING)
            profile_id = bot_user.get("profile_id")
            if not profile_id: return
            
            prof_resp = supabase_client.table("profiles").select("*").eq("id", profile_id).execute()
            profile = prof_resp.data[0] if prof_resp.data else {}
            session_id = f"tg_{telegram_id}"
            hist_resp = supabase_client.table("chat_messages").select("role, content").eq("session_id", session_id).order("created_at", desc=False).limit(10).execute()
            history = hist_resp.data if hist_resp.data else []
            
            reply_text = await chat_with_dermabot(text, None, None, history, profile, "")
            
            supabase_client.table("chat_messages").insert({"session_id": session_id, "user_id": profile_id, "role": "user", "content": text}).execute()
            supabase_client.table("chat_messages").insert({"session_id": session_id, "user_id": profile_id, "role": "assistant", "content": reply_text}).execute()
            
            if len(reply_text) > 4000:
                for chunk in [reply_text[i:i+4000] for i in range(0, len(reply_text), 4000)]: await message.reply_text(chunk)
            else: await message.reply_text(reply_text)
                
    except Exception as e:
        print(f"Text handler error: {e}")
        await message.reply_text("Sorry, something went wrong.")
