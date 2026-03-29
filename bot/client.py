from pyrogram import Client
from config import API_HASH, API_ID, BOT_TOKEN


bot = Client(
    name="dermaassess_bot",
    api_id=int(API_ID),
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)
