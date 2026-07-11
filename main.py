import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties # <-- Shu qator qo'shildi
from config import BOT_TOKEN

# Routerlarni chaqirib olamiz
from admin_handlers import admin_router
from user_handlers import user_router

# Loglarni terminalda ko'rib turish uchun
logging.basicConfig(level=logging.INFO)

async def main():
    # Bot va Dispatcher obyektlari (Shu yer o'zgardi)
    bot = Bot(
        token=BOT_TOKEN, 
        default=DefaultBotProperties(parse_mode='HTML') # <-- parse_mode yangicha usulda yozildi
    )
    dp = Dispatcher()

    # Routerlarni ulash
    dp.include_router(admin_router)
    dp.include_router(user_router)

    print("Bot muvaffaqiyatli ishga tushdi...")
    
    # Botni polling rejimida ishga tushiramiz
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot to'xtatildi!")
