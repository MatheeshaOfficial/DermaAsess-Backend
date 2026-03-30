from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram.enums import ParseMode
from database import supabase_client
import logging

scheduler = AsyncIOScheduler()

async def send_daily_weight_prompt():
    from bot.client import bot
    try:
        logging.info("[Scheduler] Running daily morning weight prompt...")
        # Get all onboarded users
        resp = supabase_client.table("bot_users").select("telegram_id, current_state").eq("onboarded", True).execute()
        users = resp.data if resp.data else []
        
        count = 0
        for u in users:
            telegram_id = u.get("telegram_id")
            # If user is in middle of onboarding/something else, skip to be safe, or just overwrite current state
            # Here we just forcefully ask for weight unless they're in a specific flow.
            # But "idle" or "awaiting_weight_input" is best.
            if u.get("current_state") in ["idle", "awaiting_weight_input"]:
                supabase_client.table("bot_users").update({"current_state": "awaiting_weight_input"}).eq("telegram_id", telegram_id).execute()
                try:
                    await bot.send_message(
                        chat_id=telegram_id,
                        text="🌅 <b>Good morning!</b>\n\nIt's time for your daily check-in.\nWhat is your current weight today in kg?\n<i>(e.g. type: 68.5)</i>",
                        parse_mode=ParseMode.HTML
                    )
                    count += 1
                except Exception as e:
                    logging.warning(f"[Scheduler] Could not send to {telegram_id}: {e}")
                    
        logging.info(f"[Scheduler] Sent morning prompt to {count} users.")
    except Exception as e:
        logging.error(f"[Scheduler] Task failed: {e}")

def start_scheduler():
    # Run every day at 8:00 AM server time
    scheduler.add_job(send_daily_weight_prompt, 'cron', hour=8, minute=0)
    scheduler.start()
    logging.info("[Scheduler] APScheduler started for daily morning weight check-ins.")
