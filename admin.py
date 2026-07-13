import os
import hashlib
from aiogram import Router, F, types
from aiogram.filters import Command
from database import DBContext

router = Router()

def get_admin_token(user_id: int) -> str:
    bot_token = os.getenv("BOT_TOKEN", "default_secret")
    token_hash = hashlib.sha256(f"{user_id}:{bot_token}".encode()).hexdigest()[:16]
    return f"{user_id}:{token_hash}"

def verify_admin_token(token: str) -> bool:
    if not token or ":" not in token:
        return False
    try:
        user_id_str, token_hash = token.split(":")
        user_id = int(user_id_str)
        
        # Verify user is admin
        admin_ids = os.getenv("ADMIN_IDS", "").split(",")
        if user_id_str not in admin_ids:
            return False
            
        bot_token = os.getenv("BOT_TOKEN", "default_secret")
        expected_hash = hashlib.sha256(f"{user_id}:{bot_token}".encode()).hexdigest()[:16]
        return token_hash == expected_hash
    except Exception:
        return False

@router.message(Command("admin"))
async def admin_cmd(message: types.Message):
    user_id = str(message.from_user.id)
    admin_ids = os.getenv("ADMIN_IDS", "").split(",")
    
    if user_id not in admin_ids:
        await message.answer("⚠️ Kechirasiz, siz admin emassiz.")
        return
        
    token = get_admin_token(message.from_user.id)
    site_url = os.getenv("SITE_URL", "https://cerfbotweb.vercel.com").strip().rstrip("/")
    if not site_url.startswith("http"):
        site_url = f"https://{site_url}"
    admin_link = f"{site_url}?token={token}#admin"
    
    text = (
        "👑 **Admin Panelga Xush Kelibsiz!**\n\n"
        "Siz quyidagi tugma orqali Web Admin Panelga kirishingiz mumkin. "
        "U yerda yangi darslar, Reading/Listening matnlari, audio fayllar, "
        "Writing/Speaking topshiriqlari va Mock Examlar qo'sha olasiz.\n\n"
        "🔗 **Havola:**"
    )
    
    markup = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⚙️ Web Admin Panel", web_app=types.WebAppInfo(url=admin_link))]
    ])
    
    await message.answer(text, reply_markup=markup, parse_mode="Markdown")
