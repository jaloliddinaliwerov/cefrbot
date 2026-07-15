import os
import hashlib
from aiogram import Router, F, types, Bot
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
    
    # Web URL is Vercel address (support both WEB_APP_URL and WEBAPP_URL)
    web_url = os.getenv("WEB_APP_URL") or os.getenv("WEBAPP_URL") or "https://cefrbotweb.vercel.app"
    web_url = web_url.strip().rstrip("/")
    if not web_url.startswith("http"):
        web_url = f"https://{web_url}"
        
    # Backend URL is Railway address
    backend_url = os.getenv("SITE_URL", "").strip().rstrip("/")
    if not backend_url.startswith("http"):
        backend_url = f"https://{backend_url}"
        
    admin_link = f"{web_url}?token={token}&api_url={backend_url}"
    
    text = (
        "👑 **Admin Panelga Xush Kelibsiz!**\n\n"
        "Siz quyidagi tugma orqali Web Admin Panelga kirishingiz mumkin.\n\n"
        "🔗 **Havola:**"
    )
    
    markup = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⚙️ Web Admin Panel", web_app=types.WebAppInfo(url=admin_link))],
        [types.InlineKeyboardButton(text="🌐 Brauzerda ochish", url=admin_link)]
    ])
    
    await message.answer(text, reply_markup=markup, parse_mode="Markdown")
    
    # Send token separately so admin can manually paste if WebApp URL fails
    await message.answer(
        f"🔑 **Xavfsizlik Tokeni** (panel ochilmasa, quyidagini nusxalab kiriting):\n\n"
        f"`{token}`\n\n"
        f"🖥️ **Backend API URL:**\n"
        f"`{backend_url}`",
        parse_mode="Markdown"
    )

@router.message(Command("addtest"))
async def addtest_cmd(message: types.Message):
    user_id_str = str(message.from_user.id)
    admin_ids = os.getenv("ADMIN_IDS", "").split(",")
    if user_id_str not in admin_ids:
        return
        
    help_msg = (
        "📥 **Test yuklash yo'riqnomasi:**\n\n"
        "Matnli yoki audio savollarni tezda qo'shish uchun botga maxsus `.json` formatidagi faylni yuboring.\n\n"
        "**Fayl strukturasi namunasi (Reading):**\n"
        "```json\n"
        "{\n"
        "  \"section\": \"reading\",\n"
        "  \"part\": 1,\n"
        "  \"title\": \"History of Tech\",\n"
        "  \"text\": \"Passage text here...\",\n"
        "  \"questions\": [\n"
        "    {\n"
        "      \"q\": \"What is technology?\",\n"
        "      \"options\": [\"Option A\", \"Option B\", \"Option C\", \"Option D\"],\n"
        "      \"answer\": \"A\"\n"
        "    }\n"
        "  ]\n"
        "}\n"
        "```\n\n"
        "💡 *Listening uchun \"text\" o'rniga \"audio_url\" kiritiladi. Faylni tayyorlab botga hujjat (document) ko'rinishida yuboring.*"
    )
    await message.answer(help_msg, parse_mode="Markdown")


import json

@router.message(F.document)
async def handle_json_test_upload(message: types.Message, bot: Bot):
    user_id_str = str(message.from_user.id)
    admin_ids = os.getenv("ADMIN_IDS", "").split(",")
    if user_id_str not in admin_ids:
        return
        
    if not message.document.file_name.endswith(".json"):
        return
        
    status_msg = await message.answer("⌛️ **Fayl tekshirilmoqda va bazaga yuklanmoqda...**")
    temp_file = f"temp_upload_{message.from_user.id}.json"
    
    try:
        file_info = await bot.get_file(message.document.file_id)
        await bot.download_file(file_info.file_path, temp_file)
        
        with open(temp_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        if os.path.exists(temp_file):
            os.remove(temp_file)
        
        section = data.get("section")
        part = data.get("part")
        title = data.get("title")
        questions_raw = data.get("questions", [])
        
        if not section or not part or not title or not questions_raw:
            await status_msg.edit_text("❌ **Xatolik:** JSON faylda `section`, `part`, `title` va `questions` maydonlari bo'lishi shart!")
            return
            
        questions_json = []
        for idx, q_item in enumerate(questions_raw, 1):
            q_text = q_item.get("q")
            options = q_item.get("options", [])
            answer = q_item.get("answer", "")
            
            formatted_opts = []
            prefixes = ["A", "B", "C", "D"]
            for i, opt in enumerate(options):
                opt_str = str(opt).strip()
                prefix = prefixes[i] if i < len(prefixes) else ""
                if len(opt_str) > 1 and opt_str[1] == ":":
                    formatted_opts.append(opt_str)
                else:
                    formatted_opts.append(f"{prefix}: {opt_str}")
                    
            questions_json.append({
                "id": idx,
                "q": q_text,
                "options": formatted_opts,
                "answer": answer.upper().strip()
            })
            
        from database import Question
        async with DBContext() as session:
            new_q = Question(
                section=section.lower(),
                part=int(part),
                title=title,
                text=data.get("text"),
                audio_url=data.get("audio_url"),
                questions_json=questions_json,
                is_mock=False
            )
            session.add(new_q)
            await session.commit()
            
        await status_msg.edit_text(f"✅ **Muvaffaqiyatli yuklandi!**\n\n📌 **Sarlavha:** {title}\n🗂 **Bo'lim:** {section.upper()} (Part {part})\n🎯 **Savollar soni:** {len(questions_json)} ta")
        
    except Exception as e:
        if os.path.exists(temp_file):
            os.remove(temp_file)
        await status_msg.edit_text(f"❌ **Faylni tahlil qilishda xatolik:**\n`{str(e)}`")
