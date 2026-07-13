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

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Import handlers and FastAPI app
from database import init_db
from api import app

# Import bot routers
from handlers.common import router as common_router
from handlers.reading import router as reading_router
from handlers.listening import router as listening_router
from handlers.writing import router as writing_router
from handlers.speaking import router as speaking_router
from handlers.profile import router as profile_router
from handlers.mock import router as mock_router
from handlers.admin import router as admin_router

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
