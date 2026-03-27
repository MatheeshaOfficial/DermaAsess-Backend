import os
import httpx
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.client import bot
from database import supabase_client
from config import BACKEND_URL, FRONTEND_URL


@bot.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    try:
        # ── Check for deep-link login ──
        if len(message.command) > 1 and message.command[1].startswith("login_"):
            session_token = message.command[1].replace("login_", "", 1)
            
            # The bot can just call the self-hosted backend.
            backend_url = BACKEND_URL
            api_endpoint = f"{backend_url.rstrip('/')}/api/auth/telegram-complete"
            
            try:
                async with httpx.AsyncClient() as http_client:
                    resp = await http_client.post(
                        api_endpoint,
                        json={
                            "session_token": session_token,
                            "telegram_id": message.from_user.id,
                            "first_name": message.from_user.first_name,
                            "username": message.from_user.username
                        },
                        timeout=10.0
                    )
                
                if resp.status_code == 200 and resp.json().get("success"):
                    frontend_url = FRONTEND_URL
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("Open DermaAssess", url=frontend_url)]
                    ])
                    await message.reply_text(
                        "✅ Login successful! Return to DermaAssess website. It will log you in automatically in a few seconds.",
                        reply_markup=keyboard
                    )
                else:
                    print(f"Backend login failed: {resp.status_code} - {resp.text}")
                    await message.reply_text("❌ Login session invalid or expired. Please go back to the website and try again.")
            except Exception as req_err:
                print(f"Error calling backend login endpoint: {req_err}")
                await message.reply_text("❌ Login session invalid or expired. Please go back to the website and try again.")
            
            return

        telegram_id = message.from_user.id
        
        response = supabase_client.table("bot_users").select("*").eq("telegram_id", telegram_id).execute()
        
        if not response.data:
            prof_resp = supabase_client.table("profiles").insert({
                "telegram_id": telegram_id,
                "notification_channel": "telegram"
            }).execute()
            profile_id = prof_resp.data[0]["id"]
            
            supabase_client.table("bot_users").insert({
                "telegram_id": telegram_id,
                "first_name": message.from_user.first_name,
                "telegram_username": message.from_user.username,
                "profile_id": profile_id,
                "current_state": "awaiting_age",
                "onboarded": False
            }).execute()
            
            await message.reply_text(
                "👋 **Welcome to DermaAssess AI!**\n\n"
                "I'm your personal AI health assistant. I can help you:\n"
                "🔬 Analyse skin concerns from photos\n"
                "💊 Read and safety-check prescriptions\n"
                "🤖 Answer health questions 24/7\n"
                "📊 Track your weight and nutrition\n"
                "🌐 Log in to the web app at dermaassess.vercel.app\n\n"
                "Let's set up your health profile first.\n"
                "**How old are you?** (type a number)"
            )
        else:
            bot_user = response.data[0]
            profile_id = bot_user.get("profile_id")
            
            # Self-healing: if the user was somehow created without a profile record
            if not profile_id:
                prof_resp = supabase_client.table("profiles").insert({
                    "telegram_id": telegram_id,
                    "notification_channel": "telegram"
                }).execute()
                profile_id = prof_resp.data[0]["id"]
                supabase_client.table("bot_users").update({
                    "profile_id": profile_id, 
                    "onboarded": False, 
                    "current_state": "awaiting_age"
                }).eq("telegram_id", telegram_id).execute()
                
                await message.reply_text("We need to rebuild your profile database connection. *How old are you?* (type a number)")
                return

            if bot_user.get("onboarded"):
                await message.reply_text(
                    f"Welcome back, {bot_user.get('first_name')}! 👋\n\n"
                    "What would you like to do?\n"
                    "📸 Send a skin photo for triage\n"
                    "/medi — scan a prescription\n"
                    "/weight — log your weight\n"
                    "/profile — view your profile\n"
                    "Or just ask me a health question!"
                )
            else:
                supabase_client.table("bot_users").update({"current_state": "awaiting_age"}).eq("telegram_id", telegram_id).execute()
                await message.reply_text("Please continue setup. *How old are you?* (type a number)")
    except Exception as e:
        print(f"Start error: {e}")
        await message.reply_text("Sorry, something went wrong. Please try again or send /start")

@bot.on_message(filters.command("help") & filters.private)
async def help_handler(client, message):
    try:
        await message.reply_text(
            "📋 **Command List**\n\n"
            "/start - Start or restart the bot\n"
            "/medi - Scan a prescription\n"
            "/weight - Log your weight\n"
            "/profile - View your profile\n"
            "/history - View recent skin assessments\n"
            "/cancel - Cancel current action\n\n"
            "Just send me a photo to analyze your skin, or send a message to chat with DermaBot!"
        )
    except Exception:
        await message.reply_text("Sorry, try again later.")
