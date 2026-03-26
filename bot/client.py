from pyrogram import Client
import os
from dotenv import load_dotenv

load_dotenv()

bot = Client(
    name="dermaassess_bot",
    api_id=int(os.getenv("API_ID", "0")),
    api_hash=os.getenv("API_HASH", ""),
    bot_token=os.getenv("BOT_TOKEN", ""),
    in_memory=True
)
