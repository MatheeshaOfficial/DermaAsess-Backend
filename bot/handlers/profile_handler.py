<<<<<<< HEAD
from pyrogram import filters
from pyrogram.enums import ParseMode
from bot.client import bot
from database import supabase_client


@bot.on_message(filters.command("profile") & filters.private)
async def profile_handler(client, message):
    try:
        telegram_id = message.from_user.id
        resp = supabase_client.table("bot_users").select("profile_id, first_name").eq("telegram_id", telegram_id).execute()
        if not resp.data: return
        
        profile_id = resp.data[0].get("profile_id")
        first_name = resp.data[0].get("first_name", "Not set")
        
        if not profile_id:
            await message.reply_text("No profile found.")
            return
            
        p_resp = supabase_client.table("profiles").select("*").eq("id", profile_id).execute()
        p = p_resp.data[0] if p_resp.data else {}
        
        age, height, weight = p.get('age', 'N/A'), p.get('height', 0), p.get('weight', 0)
        
        bmi, bmi_label = 0, "N/A"
        if height and weight:
            bmi = weight / ((height/100)**2)
            if bmi < 18.5: bmi_label = "Underweight"
            elif bmi < 25: bmi_label = "Normal"
            elif bmi < 30: bmi_label = "Overweight"
            else: bmi_label = "Obese"
            
        al, co = p.get("allergies", []), p.get("conditions", [])
        al_str = "\n".join([f"• {a}" for a in al]) if al else "• None recorded"
        co_str = "\n".join([f"• {c}" for c in co]) if co else "• None recorded"
        
        text = f"👤 *Your Health Profile*\n\n*Name:* {first_name}\n*Age:* {age} yrs  |  *Height:* {height}cm  |  *Weight:* {weight}kg\n"
        
        bmi_part = f"*BMI:* {bmi:.1f} ({bmi_label})" if bmi > 0 else f"*BMI:* {bmi_label}"
        text += f"{bmi_part}\n\n*Allergies:*\n{al_str}\n\n*Chronic Conditions:*\n{co_str}\n\n🌐 Update your profile at dermaassess.vercel.app"
        await message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await message.reply_text("Error loading profile.")

@bot.on_message(filters.command("history") & filters.private)
async def history_handler(client, message):
    try:
        telegram_id = message.from_user.id
        resp = supabase_client.table("bot_users").select("profile_id").eq("telegram_id", telegram_id).execute()
        if not resp.data: return
        profile_id = resp.data[0].get("profile_id")
        
        if profile_id:
            h_resp = supabase_client.table("skin_assessments").select("*").eq("user_id", profile_id).order("created_at", desc=True).limit(5).execute()
            assessments = h_resp.data
            
            if not assessments:
                await message.reply_text("No skin assessments found.")
                return
                
            lines = []
            for i, a in enumerate(assessments, 1):
                date = a.get("created_at", "")[:10]
                cond = a["possible_conditions"][0] if a.get("possible_conditions") else "Unknown"
                lines.append(f"{i}. {date} — {cond} (severity {a.get('severity_score', 5)}/10) → {a.get('recommended_action', 'clinic')}")
                
            await message.reply_text("*Your recent skin assessments:*\n\n" + "\n".join(lines) + "\n\nOpen the web app for full details and images.", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        pass

@bot.on_message(filters.command("cancel") & filters.private)
async def cancel_handler(client, message):
    try:
        telegram_id = message.from_user.id
        supabase_client.table("bot_users").update({"current_state": "idle", "session_data": {}}).eq("telegram_id", telegram_id).execute()
        await message.reply_text("❌ Cancelled. Send /help to see what I can do.")
    except Exception:
        pass
=======
from pyrogram import filters
from pyrogram.enums import ParseMode
from bot.client import bot
from database import supabase_client


@bot.on_message(filters.command("profile") & filters.private)
async def profile_handler(client, message):
    try:
        telegram_id = message.from_user.id
        resp = supabase_client.table("bot_users").select("profile_id, first_name").eq("telegram_id", telegram_id).execute()
        if not resp.data: return
        
        profile_id = resp.data[0].get("profile_id")
        first_name = resp.data[0].get("first_name", "Not set")
        
        if not profile_id:
            await message.reply_text("No profile found.")
            return
            
        p_resp = supabase_client.table("profiles").select("*").eq("id", profile_id).execute()
        p = p_resp.data[0] if p_resp.data else {}
        
        age, height, weight = p.get('age', 'N/A'), p.get('height', 0), p.get('weight', 0)
        
        bmi, bmi_label = 0, "N/A"
        if height and weight:
            bmi = weight / ((height/100)**2)
            if bmi < 18.5: bmi_label = "Underweight"
            elif bmi < 25: bmi_label = "Normal"
            elif bmi < 30: bmi_label = "Overweight"
            else: bmi_label = "Obese"
            
        al, co = p.get("allergies", []), p.get("conditions", [])
        al_str = "\n".join([f"• {a}" for a in al]) if al else "• None recorded"
        co_str = "\n".join([f"• {c}" for c in co]) if co else "• None recorded"
        
        text = f"👤 *Your Health Profile*\n\n*Name:* {first_name}\n*Age:* {age} yrs  |  *Height:* {height}cm  |  *Weight:* {weight}kg\n"
        
        bmi_part = f"*BMI:* {bmi:.1f} ({bmi_label})" if bmi > 0 else f"*BMI:* {bmi_label}"
        text += f"{bmi_part}\n\n*Allergies:*\n{al_str}\n\n*Chronic Conditions:*\n{co_str}\n\n🌐 Update your profile at dermaassess.vercel.app"
        await message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await message.reply_text("Error loading profile.")

@bot.on_message(filters.command("history") & filters.private)
async def history_handler(client, message):
    try:
        telegram_id = message.from_user.id
        resp = supabase_client.table("bot_users").select("profile_id").eq("telegram_id", telegram_id).execute()
        if not resp.data: return
        profile_id = resp.data[0].get("profile_id")
        
        if profile_id:
            h_resp = supabase_client.table("skin_assessments").select("*").eq("user_id", profile_id).order("created_at", desc=True).limit(5).execute()
            assessments = h_resp.data
            
            if not assessments:
                await message.reply_text("No skin assessments found.")
                return
                
            lines = []
            for i, a in enumerate(assessments, 1):
                date = a.get("created_at", "")[:10]
                cond = a["possible_conditions"][0] if a.get("possible_conditions") else "Unknown"
                lines.append(f"{i}. {date} — {cond} (severity {a.get('severity_score', 5)}/10) → {a.get('recommended_action', 'clinic')}")
                
            await message.reply_text("*Your recent skin assessments:*\n\n" + "\n".join(lines) + "\n\nOpen the web app for full details and images.", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        pass

@bot.on_message(filters.command("cancel") & filters.private)
async def cancel_handler(client, message):
    try:
        telegram_id = message.from_user.id
        supabase_client.table("bot_users").update({"current_state": "idle", "session_data": {}}).eq("telegram_id", telegram_id).execute()
        await message.reply_text("❌ Cancelled. Send /help to see what I can do.")
    except Exception:
        pass
>>>>>>> 3efa2a2850a1b0535bb86f92f3a35fd5c8ece0cc
