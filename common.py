import datetime
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from sqlalchemy import select
from database import DBContext, User

router = Router()

import os

def get_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="📖 Reading"), KeyboardButton(text="🎧 Listening")],
        [KeyboardButton(text="✍️ Writing"), KeyboardButton(text="🗣️ Speaking")],
        [KeyboardButton(text="👤 Profil & Natijalar"), KeyboardButton(text="🏆 Leaderboard")],
        [KeyboardButton(text="🔥 Daily Challenge"), KeyboardButton(text="🎓 Mock Exam")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

@router.message(CommandStart())
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    is_premium = message.from_user.is_premium or False

    async with DBContext() as session:
        # Check if user exists
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
            # Update user info if changed
            user.username = username
            user.first_name = first_name
            user.is_premium = is_premium
            
            # Check Streak
            today = datetime.date.today()
            yesterday = today - datetime.timedelta(days=1)
            
            if user.last_active == yesterday:
                user.streak += 1
                user.last_active = today
                await session.commit()
                welcome_text = f"Qaytganingizdan xursandmiz, {first_name}! Ketma-ket kirish (Streak): {user.streak} kun! 🔥"
            elif user.last_active != today:
                user.streak = 1  # Reset streak
                user.last_active = today
                await session.commit()
                welcome_text = f"Qaytganingizdan xursandmiz, {first_name}! Yangi streak boshlandi! 🚀"
            else:
                welcome_text = f"Salom {first_name}! Qanday dars qilamiz bugun?"

    await message.answer(welcome_text, reply_markup=get_main_keyboard())

@router.message(Command("help"))
async def help_cmd(message: types.Message):
    help_text = (
        "📚 **CEFR Bot Yo'riqnomasi**:\n\n"
        "1. **Reading**: Matn va savollarni olasiz. Javoblarni `1-A, 2-C, 3-B` shaklida yuboring.\n"
        "2. **Listening**: Audioni eshiting va savollarga javob bering.\n"
        "3. **Writing**: Mavzu bo'yicha insho yozing, sun'iy intellekt xatolar va tavsiyalarni beradi.\n"
        "4. **Speaking**: Savol bo'yicha ovoz yozib yuboring (Voice), AI uni matnga o'girib baholaydi.\n"
        "5. **Profil**: Natijalar, XP yutuqlari va xato ishlangan savollarni qayta ishlash.\n"
        "6. **Mock Exam**: Haqiqiy imtihon topshirib o'z darajangizni aniqlang."
    )
    await message.answer(help_text, reply_markup=get_main_keyboard())

@router.message(F.text == "Asosiy Menyu")
@router.message(F.text == "🔙 Orqaga")
async def back_to_menu(message: types.Message):
    await message.answer("Asosiy menyuga qaytdingiz.", reply_markup=get_main_keyboard())
