from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types.web_app_info import WebAppInfo
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from config import ADMIN_IDS, WEBAPP_URL

bot_router = Router()

@bot_router.message(CommandStart())
async def cmd_start(message: types.Message):
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="📖 Reading"))
    builder.add(types.KeyboardButton(text="🎧 Listening"))
    builder.add(types.KeyboardButton(text="👤 Profil"))
    
    # Faqat adminlarga Admin Panel tugmasi chiqadi
    if message.from_user.id in ADMIN_IDS:
        admin_url = f"{WEBAPP_URL}/admin"
        builder.add(types.KeyboardButton(
            text="⚙️ Admin Panel", 
            web_app=WebAppInfo(url=admin_url)
        ))
        
    builder.adjust(2, 1, 1)

    await message.answer(
        f"Assalomu alaykum, {message.from_user.first_name}!\nCEFR Botga xush kelibsiz.",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

@bot_router.message(F.text == "📖 Reading")
async def show_reading_parts(message: types.Message):
    # Foydalanuvchi Web App ni ochishi uchun Inline tugma yaratamiz
    test_url = f"{WEBAPP_URL}/test/reading/1" # Reading Part 1 uchun URL
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Part 1 ni ishlash", web_app=WebAppInfo(url=test_url))]
    ])
    
    await message.answer("Reading Part 1:\nQuyidagi tugmani bosib testni boshlang👇", reply_markup=markup)
