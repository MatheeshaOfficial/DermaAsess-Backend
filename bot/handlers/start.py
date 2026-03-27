from pyrogram import filters
from bot.client import bot
from database import supabase_client


@bot.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    try:
        telegram_id = message.from_user.id
        
        response = supabase_client.table("bot_users").select("*").eq("telegram_id", telegram_id).execute()
        
        if not response.data:
            supabase_client.table("bot_users").insert({
                "telegram_id": telegram_id,
                "first_name": message.from_user.first_name,
                "telegram_username": message.from_user.username,
                "current_state": "awaiting_age",
                "onboarded": False
            }).execute()
            
            await message.reply_text(
                "👋 *Welcome to DermaAssess AI!*\n\n"
                "I'm your personal AI health assistant. I can help you:\n"
                "🔬 Analyse skin concerns from photos\n"
                "💊 Read and safety-check prescriptions\n"
                "🤖 Answer health questions 24/7\n"
                "📊 Track your weight and nutrition\n"
                "🌐 Log in to the web app at dermaassess.vercel.app\n\n"
                "Let's set up your health profile first.\n"
                "*How old are you?* (type a number)"
            )
        else:
            bot_user = response.data[0]
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
                await message.reply_text("Please continue setup. Send a message to continue.")
    except Exception as e:
        print(f"Start error: {e}")
        await message.reply_text("Sorry, something went wrong. Please try again or send /start")

@bot.on_message(filters.command("help") & filters.private)
async def help_handler(client, message):
    try:
        await message.reply_text(
            "📋 *Command List*\n\n"
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
