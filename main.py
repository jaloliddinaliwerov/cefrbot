import asyncio
import os
import uvicorn
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

load_dotenv()

# Initialize Bot and Dispatcher
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in environment variables.")

import re
from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.methods import SendMessage, EditMessageText

EMOJIS_TO_REPLACE = [
    "📖", "🎧", "✍️", "🗣️", "👤", "🏆", "🔥", "🎓", "⚡️", "🎯",
    "🎖️", "✅", "❌", "🚀", "📚", "📝", "🧱", "📣", "💡", "🎉",
    "🥇", "🥈", "🥉", "👑", "💎", "🌟", "⚙️", "🔄", "🏠", "🔙",
    "💳", "🎨"
]

def md_to_html(text: str) -> str:
    if not text:
        return text
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'_(.*?)_', r'<i>\1</i>', text)
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    return text

def wrap_emojis_with_premium(text: str) -> str:
    if not text:
        return text
    for emoji in EMOJIS_TO_REPLACE:
        if emoji in text:
            text = text.replace(emoji, f'<tg-emoji emoji-id="7489288727785635936">{emoji}</tg-emoji>')
    return text

class EmojiAPIMiddleware(BaseRequestMiddleware):
    async def __call__(self, make_request, bot, method):
        if isinstance(method, (SendMessage, EditMessageText)):
            if method.text:
                orig_parse_mode = method.parse_mode
                parse_mode_str = orig_parse_mode.value if hasattr(orig_parse_mode, "value") else orig_parse_mode
                
                if parse_mode_str in ("Markdown", "MarkdownV2", None):
                    method.text = md_to_html(method.text)
                    method.parse_mode = "HTML"
                    if hasattr(method, "__fields_set__"):
                        method.__fields_set__.add("parse_mode")
                method.text = wrap_emojis_with_premium(method.text)
        return await make_request(bot, method)

bot = Bot(token=BOT_TOKEN)
bot.session.middleware(EmojiAPIMiddleware())
dp = Dispatcher()

# Import handlers and FastAPI app
from database import init_db
from api import app

# Import bot routers
from common import router as common_router
from reading import router as reading_router
from listening import router as listening_router
from writing import router as writing_router
from speaking import router as speaking_router
from profile import router as profile_router
from mock import router as mock_router
from admin import router as admin_router

# Include routers in dispatcher
dp.include_router(common_router)
dp.include_router(reading_router)
dp.include_router(listening_router)
dp.include_router(writing_router)
dp.include_router(speaking_router)
dp.include_router(profile_router)
dp.include_router(mock_router)
dp.include_router(admin_router)

async def run_bot():
    print("Starting Telegram Bot (Polling)...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

async def run_api():
    port = int(os.getenv("PORT", 8000))
    print(f"Starting FastAPI Web Server on port {port}...")
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    # 1. Initialize Database & Seed Default Data
    print("Initializing Database...")
    await init_db()
    
    # 2. Start Bot and FastAPI concurrently
    await asyncio.gather(
        run_bot(),
        run_api()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Application stopped manually.")
