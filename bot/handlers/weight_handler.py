<<<<<<< HEAD
from pyrogram import filters
from bot.client import bot
from pyrogram.enums import ParseMode, ChatAction
from database import supabase_client
import os
from services.gemini_service import analyze_meal
from services.nutrition_service import lookup_nutrition
from services.notification_service import notify_user
from services.cloudinary_service import upload_image


@bot.on_message(filters.command("weight") & filters.private)
async def weight_command_handler(client, message):
    try:
        telegram_id = message.from_user.id
        supabase_client.table("bot_users").update({"current_state": "awaiting_weight_input"}).eq("telegram_id", telegram_id).execute()
        await message.reply_text("📊 *Weight Tracker*\n\nWhat is your current weight in kg?\n(e.g. type: 68.5)", parse_mode=ParseMode.MARKDOWN)
    except Exception:
        await message.reply_text("Sorry, try again later.")

@bot.on_callback_query(filters.regex("^weight_"))
async def weight_callback_handler(client, query):
    try:
        telegram_id = query.from_user.id
        response = supabase_client.table("bot_users").select("*").eq("telegram_id", telegram_id).execute()
        if not response.data: return
        bot_user = response.data[0]
        profile_id = bot_user.get("profile_id")
        
        if query.data == "weight_add_meal":
            supabase_client.table("bot_users").update({"current_state": "awaiting_meal_photo"}).eq("telegram_id", telegram_id).execute()
            await query.message.reply_text("📸 Send me a photo of your meal!")
            await query.answer()
            
        elif query.data == "weight_skip_meal":
            sess_data = bot_user.get("session_data", {})
            weight = sess_data.get("pending_weight")
            supabase_client.table("bot_users").update({"current_state": "idle", "session_data": {}}).eq("telegram_id", telegram_id).execute()
            
            trend_text = "→ stable"
            if profile_id and weight:
                prev_logs = supabase_client.table("weight_logs").select("weight_kg").eq("user_id", profile_id).order("created_at", desc=True).limit(1).execute()
                if prev_logs.data:
                    prev_w = prev_logs.data[0]["weight_kg"]
                    trend_text = "▼ down" if weight < prev_w else "▲ up" if weight > prev_w else "→ stable"
                supabase_client.table("weight_logs").insert({"user_id": profile_id, "weight_kg": weight}).execute()
                supabase_client.table("profiles").update({"weight": weight}).eq("id", profile_id).execute()
                
            await query.message.reply_text(f"✅ *Weight logged: {weight}kg*\n\nTrend: {trend_text} from last entry\n\n💪 Keep it consistent — you're doing great!", parse_mode=ParseMode.MARKDOWN)
            if profile_id and weight: await notify_user(profile_id, "weight_logged", {"weight_kg": weight})
            await query.answer()
    except Exception as e:
        await query.answer("An error occurred.", show_alert=True)

async def meal_photo_handler(client, message):
    try:
        telegram_id = message.from_user.id
        response = supabase_client.table("bot_users").select("*").eq("telegram_id", telegram_id).execute()
        if not response.data: return
        bot_user = response.data[0]
        profile_id = bot_user.get("profile_id")
        
        sess_data = bot_user.get("session_data", {})
        weight = sess_data.get("pending_weight", 0)
        supabase_client.table("bot_users").update({"current_state": "idle", "session_data": {}}).eq("telegram_id", telegram_id).execute()
        
        await client.send_chat_action(telegram_id, ChatAction.TYPING)
        await message.reply_text("🍽️ Analysing your meal...")
        
        file = await client.download_media(message.photo, in_memory=True)
        img_bytes = bytes(file.getvalue())
        
        meal_analysis = await analyze_meal(img_bytes, "image/jpeg")
        food_items = meal_analysis.get("food_items", ["Unknown"])
        macros = await lookup_nutrition(food_items[0])
        
        cals, p, c, f = meal_analysis.get("calories_estimate", 0), meal_analysis.get("protein_g", 0), meal_analysis.get("carbs_g", 0), meal_analysis.get("fat_g", 0)
        if macros:
             cals = cals or macros.get("calories", 0)
             p = p or macros.get("protein", 0)
             c = c or macros.get("carbs", 0)
             f = f or macros.get("fat", 0)
             
        advice = meal_analysis.get("advice", "Keep enjoying healthy meals!")
        
        if profile_id:
            img_url = upload_image(img_bytes, f"dermaassess/users/{profile_id}/meals")
            supabase_client.table("weight_logs").insert({
                "user_id": profile_id, "weight_kg": weight, "meal_description": ", ".join(food_items),
                "calories_estimate": cals, "protein_g": p, "carbs_g": c, "fat_g": f, "meal_image_url": img_url
            }).execute()
            supabase_client.table("profiles").update({"weight": weight}).eq("id", profile_id).execute()
            await notify_user(profile_id, "weight_logged", {"weight_kg": weight, "meal_description": ", ".join(food_items), "calories": cals, "ai_advice": advice})
            
        await message.reply_text(f"✅ *Weight & Meal Logged*\n\n⚖️ Weight: {weight}kg\n🍽️ {', '.join(food_items)}\n🔥 ~{cals} kcal\n\n*Macros:*\nProtein: {p}g | Carbs: {c}g | Fat: {f}g\n\n💡 {advice}", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await message.reply_text("Sorry, error logging meal.")
=======
from pyrogram import filters
from bot.client import bot
from pyrogram.enums import ParseMode, ChatAction
from database import supabase_client
import os
from services.gemini_service import analyze_meal
from services.nutrition_service import lookup_nutrition
from services.notification_service import notify_user
from services.cloudinary_service import upload_image


@bot.on_message(filters.command("weight") & filters.private)
async def weight_command_handler(client, message):
    try:
        telegram_id = message.from_user.id
        supabase_client.table("bot_users").update({"current_state": "awaiting_weight_input"}).eq("telegram_id", telegram_id).execute()
        await message.reply_text("📊 *Weight Tracker*\n\nWhat is your current weight in kg?\n(e.g. type: 68.5)", parse_mode=ParseMode.MARKDOWN)
    except Exception:
        await message.reply_text("Sorry, try again later.")

@bot.on_callback_query(filters.regex("^weight_"))
async def weight_callback_handler(client, query):
    try:
        telegram_id = query.from_user.id
        response = supabase_client.table("bot_users").select("*").eq("telegram_id", telegram_id).execute()
        if not response.data: return
        bot_user = response.data[0]
        profile_id = bot_user.get("profile_id")
        
        if query.data == "weight_add_meal":
            supabase_client.table("bot_users").update({"current_state": "awaiting_meal_photo"}).eq("telegram_id", telegram_id).execute()
            await query.message.reply_text("📸 Send me a photo of your meal!")
            await query.answer()
            
        elif query.data == "weight_skip_meal":
            sess_data = bot_user.get("session_data", {})
            weight = sess_data.get("pending_weight")
            supabase_client.table("bot_users").update({"current_state": "idle", "session_data": {}}).eq("telegram_id", telegram_id).execute()
            
            trend_text = "→ stable"
            if profile_id and weight:
                prev_logs = supabase_client.table("weight_logs").select("weight_kg").eq("user_id", profile_id).order("created_at", desc=True).limit(1).execute()
                if prev_logs.data:
                    prev_w = prev_logs.data[0]["weight_kg"]
                    trend_text = "▼ down" if weight < prev_w else "▲ up" if weight > prev_w else "→ stable"
                supabase_client.table("weight_logs").insert({"user_id": profile_id, "weight_kg": weight}).execute()
                supabase_client.table("profiles").update({"weight": weight}).eq("id", profile_id).execute()
                
            await query.message.reply_text(f"✅ *Weight logged: {weight}kg*\n\nTrend: {trend_text} from last entry\n\n💪 Keep it consistent — you're doing great!", parse_mode=ParseMode.MARKDOWN)
            if profile_id and weight: await notify_user(profile_id, "weight_logged", {"weight_kg": weight})
            await query.answer()
    except Exception as e:
        await query.answer("An error occurred.", show_alert=True)

async def meal_photo_handler(client, message):
    try:
        telegram_id = message.from_user.id
        response = supabase_client.table("bot_users").select("*").eq("telegram_id", telegram_id).execute()
        if not response.data: return
        bot_user = response.data[0]
        profile_id = bot_user.get("profile_id")
        
        sess_data = bot_user.get("session_data", {})
        weight = sess_data.get("pending_weight", 0)
        supabase_client.table("bot_users").update({"current_state": "idle", "session_data": {}}).eq("telegram_id", telegram_id).execute()
        
        await client.send_chat_action(telegram_id, ChatAction.TYPING)
        await message.reply_text("🍽️ Analysing your meal...")
        
        file = await client.download_media(message.photo, in_memory=True)
        img_bytes = bytes(file.getvalue())
        
        meal_analysis = await analyze_meal(img_bytes, "image/jpeg")
        food_items = meal_analysis.get("food_items", ["Unknown"])
        macros = await lookup_nutrition(food_items[0])
        
        cals, p, c, f = meal_analysis.get("calories_estimate", 0), meal_analysis.get("protein_g", 0), meal_analysis.get("carbs_g", 0), meal_analysis.get("fat_g", 0)
        if macros:
             cals = cals or macros.get("calories", 0)
             p = p or macros.get("protein", 0)
             c = c or macros.get("carbs", 0)
             f = f or macros.get("fat", 0)
             
        advice = meal_analysis.get("advice", "Keep enjoying healthy meals!")
        
        if profile_id:
            img_url = upload_image(img_bytes, f"dermaassess/users/{profile_id}/meals")
            supabase_client.table("weight_logs").insert({
                "user_id": profile_id, "weight_kg": weight, "meal_description": ", ".join(food_items),
                "calories_estimate": cals, "protein_g": p, "carbs_g": c, "fat_g": f, "meal_image_url": img_url
            }).execute()
            supabase_client.table("profiles").update({"weight": weight}).eq("id", profile_id).execute()
            await notify_user(profile_id, "weight_logged", {"weight_kg": weight, "meal_description": ", ".join(food_items), "calories": cals, "ai_advice": advice})
            
        await message.reply_text(f"✅ *Weight & Meal Logged*\n\n⚖️ Weight: {weight}kg\n🍽️ {', '.join(food_items)}\n🔥 ~{cals} kcal\n\n*Macros:*\nProtein: {p}g | Carbs: {c}g | Fat: {f}g\n\n💡 {advice}", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await message.reply_text("Sorry, error logging meal.")
>>>>>>> 3efa2a2850a1b0535bb86f92f3a35fd5c8ece0cc
