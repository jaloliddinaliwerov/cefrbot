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
    
    # Web URL is Vercel address
    web_url = os.getenv("WEB_APP_URL") or "https://cerfbotweb.vercel.com"
    web_url = web_url.strip().rstrip("/")
    if not web_url.startswith("http"):
        web_url = f"https://{web_url}"
        
    # Backend URL is Railway address
    backend_url = os.getenv("SITE_URL", "").strip().rstrip("/")
    if not backend_url.startswith("http"):
        backend_url = f"https://{backend_url}"
        
    admin_link = f"{web_url}?token={token}&api_url={backend_url}#admin"
    
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

def contains_custom_emoji(message: types.Message) -> bool:
    if message.entities:
        for entity in message.entities:
            if entity.type == "custom_emoji":
                return True
    if message.caption_entities:
        for entity in message.caption_entities:
            if entity.type == "custom_emoji":
                return True
    return False

@router.message(contains_custom_emoji)
async def admin_custom_emoji_handler(message: types.Message):
    user_id_str = str(message.from_user.id)
    admin_ids = os.getenv("ADMIN_IDS", "").split(",")
    if user_id_str not in admin_ids:
        return
    
    custom_emojis = []
    if message.entities:
        for entity in message.entities:
            if entity.type == "custom_emoji":
                emoji_symbol = message.text[entity.offset:entity.offset + entity.length]
                custom_emojis.append((emoji_symbol, entity.custom_emoji_id))
                
    if message.caption_entities:
        for entity in message.caption_entities:
            if entity.type == "custom_emoji":
                emoji_symbol = message.caption[entity.offset:entity.offset + entity.length]
                custom_emojis.append((emoji_symbol, entity.custom_emoji_id))
                
    if custom_emojis:
        reply_text = "💎 **Custom Premium Emoji Aniqlandi:**\n\n"
        for sym, emoji_id in custom_emojis:
            reply_text += (
                f"• Emojining o'zi: {sym}\n"
                f"  Emoji ID: `{emoji_id}`\n"
                f"  Ishlatish uchun kod: `<tg-emoji emoji-id=\"{emoji_id}\">{sym}</tg-emoji>`\n\n"
            )
        reply_text += "💡 Ushbu HTML kodni bot xabarlarida (parse_mode='HTML' bo'lganda) ishlatishingiz mumkin."
        await message.answer(reply_text, parse_mode="Markdown")
