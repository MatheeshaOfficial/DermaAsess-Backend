import asyncio
from bot.client import bot
from pyrogram.errors import FloodWait

async def _start_bot_loop():
    from bot.handlers import register_all_handlers
    register_all_handlers()
    while True:
        try:
            await bot.start()
            me = await bot.get_me()
            print(f"Bot started: @{me.username}")
            break
        except FloodWait as e:
            wait_time = e.value
            print(f"\n[Telegram Bot] Rate limited by Telegram (FLOOD_WAIT_X).")
            print(f"[Telegram Bot] Background task sleeping for {wait_time}s (~{int(wait_time/60)} mins) and will auto-reconnect.")
            print(f"[Telegram Bot] The rest of your FastAPI server is fully operational now.\n")
            await asyncio.sleep(wait_time + 5)
        except Exception as e:
            print(f"[Telegram Bot] Failed to start: {e}")
            break

async def start_bot():
    from bot.scheduler import start_scheduler
    start_scheduler()
    # Run the connection flow entirely in the background so it never blocks or crashes FastAPI startup
    asyncio.create_task(_start_bot_loop())

async def stop_bot():
    try:
        await bot.stop()
    except Exception:
        pass
