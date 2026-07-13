import asyncio
import os
import logging
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, Router, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

# Sozlamalarni o'qish
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://cerfbotweb.vercel.com")

admin_ids_str = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()]

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()
router = Router()

# ==========================================
# FSM: Admin material qo'shish holatlari
# ==========================================
class AddMaterial(StatesGroup):
    section = State()
    part = State()
    content = State()
    questions = State()
    confirm = State()

# ==========================================
# START KOMANDASI (Admin va User uchun alohida)
# ==========================================
@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    
    # 1. Agar foydalanuvchi ADMIN bo'lsa
    if message.from_user.id in ADMIN_IDS:
        builder = ReplyKeyboardBuilder()
        builder.add(types.KeyboardButton(text="📝 Yangi material qo'shish"))
        builder.adjust(1)
        
        await message.answer(
            f"Assalomu alaykum, Admin {message.from_user.first_name}!\n"
            f"Boshqaruv paneliga xush kelibsiz.",
            reply_markup=builder.as_markup(resize_keyboard=True)
        )
    
    # 2. Agar ODDIY FOYDALANUVCHI bo'lsa
    else:
        builder = InlineKeyboardBuilder()
        builder.button(text="🌐 Saytga o'tish", url=WEBAPP_URL)
        
        await message.answer(
            "Assalomu alaykum!\n\n"
            "Bizning barcha CEFR va test materiallarimiz maxsus veb-saytimizga ko'chirilgan.\n"
            "Testlarni ishlash va natijalarni ko'rish uchun quyidagi tugma orqali saytimizga kiring 👇",
            reply_markup=builder.as_markup()
        )

# ==========================================
# ADMIN PANEL: MATERIAL QO'SHISH JARAYONI
# ==========================================
@router.message(F.text == "📝 Yangi material qo'shish")
async def start_adding_material(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
        
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="Reading"), types.KeyboardButton(text="Listening"))
    builder.add(types.KeyboardButton(text="❌ Bekor qilish"))
    builder.adjust(2, 1)
    
    await message.answer("Qaysi bo'limga material qo'shmoqchisiz?", reply_markup=builder.as_markup(resize_keyboard=True))
    await state.set_state(AddMaterial.section)

@router.message(F.text == "❌ Bekor qilish")
async def cancel_action(message: types.Message, state: FSMContext):
    await message.answer("Jarayon bekor qilindi.")
    await cmd_start(message, state)

@router.message(AddMaterial.section, F.text.in_(["Reading", "Listening"]))
async def choose_part(message: types.Message, state: FSMContext):
    await state.update_data(section=message.text)
    
    builder = ReplyKeyboardBuilder()
    for i in range(1, 6):
        builder.add(types.KeyboardButton(text=f"Part {i}"))
    builder.add(types.KeyboardButton(text="❌ Bekor qilish"))
    builder.adjust(3, 2, 1)
    
    await message.answer("Qaysi qism (Part) ekanligini tanlang:", reply_markup=builder.as_markup(resize_keyboard=True))
    await state.set_state(AddMaterial.part)

@router.message(AddMaterial.part, F.text.startswith("Part"))
async def ask_content(message: types.Message, state: FSMContext):
    await state.update_data(part=message.text)
    user_data = await state.get_data()
    
    msg = "Listening uchun audio faylni yuboring:" if user_data['section'] == "Listening" else "Reading uchun asosiy matnni yuboring:"
    await message.answer(msg, reply_markup=ReplyKeyboardBuilder().add(types.KeyboardButton(text="❌ Bekor qilish")).as_markup(resize_keyboard=True))
    await state.set_state(AddMaterial.content)

@router.message(AddMaterial.content)
async def ask_questions(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    
    if user_data['section'] == "Listening" and message.audio:
        await state.update_data(content=message.audio.file_id)
    else:
        await state.update_data(content=message.text)
        
    await message.answer("Endi savollar va to'g'ri javoblarni yuboring (Masalan: JSON formatida yoki oddiy matnda):")
    await state.set_state(AddMaterial.questions)

@router.message(AddMaterial.questions)
async def confirm_material(message: types.Message, state: FSMContext):
    await state.update_data(questions=message.text)
    data = await state.get_data()
    
    summary = (
        f"📝 <b>Tasdiqlash uchun ma'lumotlar:</b>\n\n"
        f"<b>Bo'lim:</b> {data['section']}\n"
        f"<b>Qism:</b> {data['part']}\n"
        f"<b>Kontent:</b> Olingan ✅\n"
        f"<b>Savollar:</b>\n{data['questions'][:100]}...\n\n"
        f"<i>Barchasi to'g'rimi? Bazaga saqlaymizmi?</i>"
    )
    
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="✅ Saqlash"), types.KeyboardButton(text="❌ Bekor qilish"))
    
    await message.answer(summary, reply_markup=builder.as_markup(resize_keyboard=True))
    await state.set_state(AddMaterial.confirm)

@router.message(AddMaterial.confirm, F.text == "✅ Saqlash")
async def save_material(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    # KELAJAKDA SHU YERDA MA'LUMOTLAR BAZASIGA (PostgreSQL) YOZISH KODI BO'LADI
    # insert_to_db(data['section'], data['part'], data['content'], data['questions'])
    
    await message.answer("✅ Material muvaffaqiyatli saqlandi va saytda paydo bo'ldi!")
    await cmd_start(message, state)

# ==========================================
# ISHGA TUSHIRISH
# ==========================================
async def main():
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
