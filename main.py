import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN

# Routerlarni chaqirib olamiz
from admin_handlers import admin_router
from user_handlers import user_router

# Loglarni terminalda ko'rib turish uchun
logging.basicConfig(level=logging.INFO)

async def main():
    # Bot va Dispatcher obyektlari
    bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
    dp = Dispatcher()

    # Routerlarni ulash (ketma-ketligiga e'tibor bering, admin birinchi turishi yaxshi)
    dp.include_router(admin_router)
    dp.include_router(user_router)

    print("Bot muvaffaqiyatli ishga tushdi...")
    
    # Botni polling rejimida ishga tushiramiz (eski xabarlarni o'tkazib yuborish bilan)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot to'xtatildi!")
