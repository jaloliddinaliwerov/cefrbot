from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import ReplyKeyboardBuilder

user_router = Router()

@user_router.message(CommandStart())
async def cmd_start(message: types.Message):
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="📖 Reading"))
    builder.add(types.KeyboardButton(text="🎧 Listening"))
    builder.add(types.KeyboardButton(text="✍️ Writing"))
    builder.add(types.KeyboardButton(text="🗣 Speaking"))
    builder.add(types.KeyboardButton(text="👤 Profil va Natijalar"))
    builder.adjust(2, 2, 1) # Tugmalarni 2 ta dan qilib joylashtirish

    await message.answer(
        f"Assalomu alaykum, {message.from_user.first_name}!\n"
        f"CEFR Preparation Botga xush kelibsiz. O'zingizga kerakli bo'limni tanlang:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

# Bo'limlarga kirish (Hozircha faqat Reading uchun namuna)
@user_router.message(lambda message: message.text == "📖 Reading")
async def open_reading(message: types.Message):
    builder = ReplyKeyboardBuilder()
    for i in range(1, 6):
        builder.add(types.KeyboardButton(text=f"Part {i}"))
    builder.add(types.KeyboardButton(text="⬅️ Asosiy menyu"))
    builder.adjust(2, 2, 1, 1)
    
    await message.answer("Reading bo'limi. Qaysi Partni ishlashni xohlaysiz?", 
                         reply_markup=builder.as_markup(resize_keyboard=True))

@user_router.message(lambda message: message.text == "⬅️ Asosiy menyu")
async def back_to_main(message: types.Message):
    await cmd_start(message)
