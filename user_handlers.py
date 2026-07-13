from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types.web_app_info import WebAppInfo
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from config import ADMIN_IDS, WEBAPP_URL

bot_router = Router()

# ==========================================
# PREMIUM EMOJI ID LARINI SHU YERGA YOZAMIZ
# ==========================================
# (Pastda bu ID larni qanday topishni ko'rsatganman)
PREMIUM_EMOJIS = {
    "hello": "7489288727785635936",   # 👋
    "reading": "7489288727785635936", # 📖
    "admin": "7489288727785635936",   # ⚙️
    "success": "7489288727785635936"  # ✅
}

# Emojini HTML tegiga o'rab beruvchi yordamchi funksiya
def custom_emoji(emoji_id: str, fallback: str) -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

@bot_router.message(CommandStart())
async def cmd_start(message: types.Message):
    builder = ReplyKeyboardBuilder()
    
    # Tugmalarda oddiy emoji qolishi kerak (Telegram qoidasi)
    builder.add(types.KeyboardButton(text="📖 Reading"))
    builder.add(types.KeyboardButton(text="🎧 Listening"))
    builder.add(types.KeyboardButton(text="👤 Profil"))
    
    if message.from_user.id in ADMIN_IDS:
        admin_url = f"{WEBAPP_URL}/admin"
        builder.add(types.KeyboardButton(
            text="⚙️ Admin Panel", 
            web_app=WebAppInfo(url=admin_url)
        ))
        
    builder.adjust(2, 1, 1)

    # Xabar matnida esa Premium Emojilarni ishlatamiz
    hello_emoji = custom_emoji(PREMIUM_EMOJIS["hello"], "👋")
    
    await message.answer(
        f"Assalomu alaykum, {message.from_user.first_name}! {hello_emoji}\n"
        f"CEFR Botga xush kelibsiz.",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

@bot_router.message(F.text == "📖 Reading")
async def show_reading_parts(message: types.Message):
    test_url = f"{WEBAPP_URL}/test/reading/1" 
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Part 1 ni ishlash", web_app=WebAppInfo(url=test_url))]
    ])
    
    reading_emoji = custom_emoji(PREMIUM_EMOJIS["reading"], "📖")
    
    await message.answer(
        f"{reading_emoji} <b>Reading Part 1:</b>\n"
        f"Quyidagi tugmani bosib testni boshlang👇", 
        reply_markup=markup
    )
