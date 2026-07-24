import datetime
import os
from aiogram import Router, F, types, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo
)
from sqlalchemy import select
from database import DBContext, User

router = Router()

def parse_telegram_message_link(link: str):
    import re
    if not link:
        return None, None
    link = link.strip()
    
    # 1. Match private channel or supergroup message links
    # Format: t.me/c/CHAT_ID/MSG_ID or t.me/c/CHAT_ID/TOPIC_ID/MSG_ID
    private_match = re.search(r'(?:t\.me/c/|telegram\.me/c/)(\d+)/(\d+)(?:/(\d+))?', link)
    if private_match:
        chat_id_str = private_match.group(1)
        # If there are 3 groups of digits, group(3) is MSG_ID and group(2) is TOPIC_ID
        if private_match.group(3):
            msg_id = int(private_match.group(3))
        else:
            msg_id = int(private_match.group(2))
        
        chat_id_val = f"-100{chat_id_str}"
        try:
            return int(chat_id_val), msg_id
        except ValueError:
            return chat_id_val, msg_id
            
    # 2. Match public channel or supergroup message links (excluding "/c/")
    # Format: t.me/username/MSG_ID or t.me/username/TOPIC_ID/MSG_ID
    public_match = re.search(r'(?:t\.me/|telegram\.me/)(?!c/)([^/]+)/(\d+)(?:/(\d+))?', link)
    if public_match:
        chat = public_match.group(1)
        # If there are 3 groups of digits, group(3) is MSG_ID
        if public_match.group(3):
            msg_id = int(public_match.group(3))
        else:
            msg_id = int(public_match.group(2))
            
        if not chat.startswith("-100") and not chat.isdigit():
            chat = f"@{chat}"
        else:
            try:
                chat = int(chat)
            except ValueError:
                pass
        return chat, msg_id
        
    return None, None

# ─── Channel subscription helpers ────────────────────────────────────────────

def get_required_channel() -> str:
    """Returns the required channel username from env (e.g. @mychannel)."""
    ch = os.getenv("REQUIRED_CHANNEL", "").strip()
    if ch and not ch.startswith("@"):
        ch = "@" + ch
    return ch

async def check_subscription(bot: Bot, user_id: int) -> bool:
    """
    Returns True if the user is subscribed to the required channel,
    or if no channel is configured.
    """
    channel = get_required_channel()
    if not channel:
        return True  # No channel configured — allow all

    try:
        member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
        return member.status not in ("left", "kicked", "banned")
    except Exception:
        # If bot is not admin in the channel or channel not found — allow anyway
        return True

def subscription_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown when user is not yet subscribed."""
    channel = get_required_channel()
    channel_url = f"https://t.me/{channel.lstrip('@')}" if channel else "https://t.me"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📢 Kanalga obuna bo'lish", url=channel_url)],
        [InlineKeyboardButton(text="✅ Obuna bo'ldim — Tekshirish", callback_data="check_subscription")]
    ])

# ─── Main keyboard ────────────────────────────────────────────────────────────

def get_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="📖 Reading"), KeyboardButton(text="🎧 Listening")],
        [KeyboardButton(text="✍️ Writing"), KeyboardButton(text="🗣️ Speaking")],
        [KeyboardButton(text="🤖 AI Speaking (Sesame)", web_app=WebAppInfo(url="https://app.sesame.com/"))],
        [KeyboardButton(text="👤 Profil & Natijalar"), KeyboardButton(text="🏆 Leaderboard")],
        [KeyboardButton(text="🔥 Daily Challenge"), KeyboardButton(text="🎓 Mock Exam")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# ─── /start handler ───────────────────────────────────────────────────────────

@router.message(CommandStart())
async def start_cmd(message: types.Message, bot: Bot):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    is_premium = message.from_user.is_premium or False

    # ── Majburiy obuna tekshiruvi ──
    channel = get_required_channel()
    if channel:
        is_subscribed = await check_subscription(bot, user_id)
        if not is_subscribed:
            await message.answer(
                f"👋 Salom, {first_name}!\n\n"
                f"🔒 Botdan foydalanish uchun avval quyidagi kanalga obuna bo'ling:\n\n"
                f"📢 <b>{channel}</b>\n\n"
                f"Obuna bo'lgach, <b>✅ Obuna bo'ldim — Tekshirish</b> tugmasini bosing.",
                reply_markup=subscription_keyboard(),
                parse_mode="HTML"
            )
            return

    # ── Foydalanuvchini ro'yxatdan o'tkazish yoki yangilash ──
    async with DBContext() as session:
        stmt = select(User).where(User.id == user_id)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()

        if not user:
            user = User(
                id=user_id,
                username=username,
                first_name=first_name,
                is_premium=is_premium,
                joined_at=datetime.datetime.utcnow(),
                streak=1,
                last_active=datetime.date.today()
            )
            session.add(user)
            await session.commit()
            welcome_text = (
                f"Salom {first_name}! CEFR Tayyorgarlik botiga xush kelibsiz!\n\n"
                f"Bu yerda siz Reading, Listening, Writing va Speaking ko'nikmalaringizni oshirishingiz, "
                f"haftalik Mock Exam topshirishingiz va statistika orqali rivojlanishingizni kuzatishingiz mumkin."
            )
        else:
            user.username = username
            user.first_name = first_name
            user.is_premium = is_premium

            today = datetime.date.today()
            yesterday = today - datetime.timedelta(days=1)

            if user.last_active == yesterday:
                user.streak += 1
                user.last_active = today
                await session.commit()
                welcome_text = f"Qaytganingizdan xursandmiz, {first_name}! Ketma-ket kirish (Streak): {user.streak} kun! 🔥"
            elif user.last_active != today:
                user.streak = 1
                user.last_active = today
                await session.commit()
                welcome_text = f"Qaytganingizdan xursandmiz, {first_name}! Yangi streak boshlandi! 🚀"
            else:
                welcome_text = f"Salom {first_name}! Qanday dars qilamiz bugun?"

    await message.answer(welcome_text, reply_markup=get_main_keyboard())

# ─── "Tekshirish" callback ────────────────────────────────────────────────────

@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: types.CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    first_name = callback.from_user.first_name

    is_subscribed = await check_subscription(bot, user_id)

    if is_subscribed:
        await callback.message.delete()
        # Register user if not yet in DB
        username = callback.from_user.username
        is_premium = callback.from_user.is_premium or False

        async with DBContext() as session:
            stmt = select(User).where(User.id == user_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()

            if not user:
                user = User(
                    id=user_id,
                    username=username,
                    first_name=first_name,
                    is_premium=is_premium,
                    joined_at=datetime.datetime.utcnow(),
                    streak=1,
                    last_active=datetime.date.today()
                )
                session.add(user)
                await session.commit()

        await callback.message.answer(
            f"✅ Rahmat! Obuna tasdiqlandi.\n\n"
            f"Salom {first_name}! CEFR Tayyorgarlik botiga xush kelibsiz! 🎓\n\n"
            f"Quyidagi bo'limlardan birini tanlang:",
            reply_markup=get_main_keyboard()
        )
    else:
        channel = get_required_channel()
        await callback.answer(
            f"❌ Siz hali {channel} kanaliga obuna bo'lmadingiz! Iltimos, avval obuna bo'ling.",
            show_alert=True
        )

# ─── Boshqa xabarlar uchun obuna filter ──────────────────────────────────────

@router.message(Command("help"))
async def help_cmd(message: types.Message, bot: Bot):
    # Check subscription for /help too
    channel = get_required_channel()
    if channel:
        if not await check_subscription(bot, message.from_user.id):
            await message.answer(
                f"🔒 Botdan foydalanish uchun avval {channel} kanaliga obuna bo'ling.",
                reply_markup=subscription_keyboard()
            )
            return

    help_text = (
        "📚 **CEFR Bot Yo'riqnomasi**:\n\n"
        "1. **Reading**: Matn va savollarni olasiz. Javoblarni `1-A, 2-C, 3-B` shaklida yuboring.\n"
        "2. **Listening**: Audioni eshiting va savollarga javob bering.\n"
        "3. **Writing**: Mavzu bo'yicha insho yozing, sun'iy intellekt xatolar va tavsiyalarni beradi.\n"
        "4. **Speaking**: Savol bo'yicha ovoz yozib yuboring (Voice), admin uni baholaydi.\n"
        "5. **Profil**: Natijalar, XP yutuqlari va xato ishlangan savollarni qayta ishlash.\n"
        "6. **Mock Exam**: Haqiqiy imtihon topshirib o'z darajangizni aniqlang."
    )
    await message.answer(help_text, reply_markup=get_main_keyboard())

@router.message(F.text == "Asosiy Menyu")
@router.message(F.text == "🔙 Orqaga")
async def back_to_menu(message: types.Message):
    await message.answer("Asosiy menyuga qaytdingiz.", reply_markup=get_main_keyboard())
