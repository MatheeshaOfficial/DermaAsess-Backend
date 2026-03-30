from pyrogram import filters
from bot.client import bot
from pyrogram.enums import ParseMode
from database import supabase_client
from services.notification_service import notify_user

@bot.on_message(filters.command("weight") & filters.private)
async def weight_command_handler(client, message):
    try:
        telegram_id = message.from_user.id
        supabase_client.table("bot_users").update({"current_state": "awaiting_weight_input"}).eq("telegram_id", telegram_id).execute()
        
        await message.reply_text(
            "📊 <b>Weight Tracker</b>\n\nWhat is your current weight in kg?\n<i>(e.g. type: 68.5)</i>", 
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        print(e)
        await message.reply_text("Sorry, try again later.")
