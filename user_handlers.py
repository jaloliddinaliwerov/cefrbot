from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types.web_app_info import WebAppInfo
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from config import ADMIN_IDS, WEBAPP_URL

# MANA SHU QATOR XATOLIKNI TO'G'RILAYDI
user_router = Router()

# ==========================================
# PREMIUM EMOJILAR (ID larini o'zgartirishingiz mumkin)
# ==========================================
PREMIUM_EMOJIS = {
    "hello": "7489288727785635936",   # 👋
    "reading": "7489288727785635936", # 📖
    "listening": "7489288727785635936", # 🎧
    "writing": "7489288727785635936", # ✍️
    "speaking": "7489288727785635936", # 🗣
    "profile": "7489288727785635936", # 👤
    "admin": "7489288727785635936",   # ⚙️
}

def custom_emoji(emoji_id: str, fallback: str) -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

# ==========================================
# ASOSIY MENU (START)
# ==========================================
@user_router.message(CommandStart())
async def cmd_start(message: types.Message):
    builder = ReplyKeyboardBuilder()
    
    # Tugmalarda oddiy emoji qoladi
    builder.add(types.KeyboardButton(text="📖 Reading"))
    builder.add(types.KeyboardButton(text="🎧 Listening"))
    builder.add(types.KeyboardButton(text="✍️ Writing"))
    builder.add(types.KeyboardButton(text="🗣 Speaking"))
    builder.add(types.KeyboardButton(text="👤 Profil va Natijalar"))
    
    # Admin tugmasi
    if message.from_user.id in ADMIN_IDS:
        admin_url = f"{WEBAPP_URL}/admin"
        builder.add(types.KeyboardButton(
            text="⚙️ Admin Panel", 
            web_app=WebAppInfo(url=admin_url)
        ))
        
    builder.adjust(2, 2, 1, 1)

    hello_emoji = custom_emoji(PREMIUM_EMOJIS["hello"], "👋")
    
    await message.answer(
        f"Assalomu alaykum, {message.from_user.first_name}! {hello_emoji}\n"
        f"CEFR Botga xush kelibsiz. O'zingizga kerakli bo'limni tanlang:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

# ==========================================
# 1. READING BO'LIMI
# ==========================================
@user_router.message(F.text == "📖 Reading")
async def show_reading_parts(message: types.Message):
    test_url = f"{WEBAPP_URL}/test/reading/1" 
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Part 1 ni ishlash", web_app=WebAppInfo(url=test_url))]
    ])
    
    reading_emoji = custom_emoji(PREMIUM_EMOJIS["reading"], "📖")
    
    await message.answer(
        f"{reading_emoji} <b>Reading bo'limi:</b>\n\n"
        f"Testni boshlash uchun quyidagi tugmani bosing 👇", 
        reply_markup=markup
    )

# ==========================================
# 2. LISTENING BO'LIMI
# ==========================================
@user_router.message(F.text == "🎧 Listening")
async def show_listening_parts(message: types.Message):
    test_url = f"{WEBAPP_URL}/test/listening/1" 
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎧 Part 1 ni ishlash", web_app=WebAppInfo(url=test_url))]
    ])
    
    list_emoji = custom_emoji(PREMIUM_EMOJIS["listening"], "🎧")
    
    await message.answer(
        f"{list_emoji} <b>Listening bo'limi:</b>\n\n"
        f"Audioni eshitish va test ishlash uchun tugmani bosing 👇", 
        reply_markup=markup
    )

# ==========================================
# 3. WRITING BO'LIMI
# ==========================================
@user_router.message(F.text == "✍️ Writing")
async def show_writing_parts(message: types.Message):
    write_emoji = custom_emoji(PREMIUM_EMOJIS["writing"], "✍️")
    await message.answer(
        f"{write_emoji} <b>Writing bo'limi:</b>\n\n"
        f"Sizga CEFR formatidagi mavzu beriladi. Matnni shu yerga yozib yuboring (Tez orada AI tekshiruvi qo'shiladi)."
    )

# ==========================================
# 4. SPEAKING BO'LIMI
# ==========================================
@user_router.message(F.text == "🗣 Speaking")
async def show_speaking_parts(message: types.Message):
    speak_emoji = custom_emoji(PREMIUM_EMOJIS["speaking"], "🗣")
    await message.answer(
        f"{speak_emoji} <b>Speaking bo'limi:</b>\n\n"
        f"Savol yuborilgach, ovozli xabar (Voice) orqali javob qaytaring (Tez orada AI tekshiruvi qo'shiladi)."
    )

# ==========================================
# 5. PROFIL BO'LIMI
# ==========================================
@user_router.message(F.text == "👤 Profil va Natijalar")
async def show_profile(message: types.Message):
    prof_emoji = custom_emoji(PREMIUM_EMOJIS["profile"], "👤")
    await message.answer(
        f"{prof_emoji} <b>Sizning profilingiz:</b>\n\n"
        f"📊 Umumiy balingiz: 0 XP\n"
        f"🔥 Ketma-ket kirish: 1 kun\n\n"
        f"<i>Batafsil statistika tez orada faollashadi...</i>"
    )

# ==========================================
# CATCH-ALL (Tushunarsiz xabarlar uchun)
# ==========================================
@user_router.message()
async def unknown_message(message: types.Message):
    await message.answer("Kechirasiz, men sizni tushunmadim. Iltimos, pastdagi menyu tugmalaridan foydalaning 👇")
