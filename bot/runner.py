from bot.client import bot

async def start_bot():
    from bot.handlers import register_all_handlers
    register_all_handlers()
    await bot.start()
    me = await bot.get_me()
    print(f"Bot started: @{me.username}")

async def stop_bot():
    await bot.stop()
