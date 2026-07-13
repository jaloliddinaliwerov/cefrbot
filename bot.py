import asyncio
import os
from aiogram import Bot, Dispatcher, Router, F, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from dotenv import load_dotenv

load_dotenv()

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()
router = Router()

# Web sayt manzilingiz
SITE_URL = "https://cerfbotweb.vercel.com"

@router.message(CommandStart())
async def start(message: types.Message):
    # Oddiy foydalanuvchi
    if str(message.from_user.id) not in os.getenv("ADMIN_IDS", "").split(","):
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Test ishlash", web_app=WebAppInfo(url=SITE_URL))]
        ])
        await message.answer("Salom! Testlarni saytimizda ishlang:", reply_markup=markup)
    else:
        # Admin
        await message.answer("Salom Admin! Material qo'shish uchun bazaga kiring.")

async def main():
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
