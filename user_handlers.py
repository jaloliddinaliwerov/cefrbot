from aiogram import Router, F, types
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
    builder.adjust(2, 2, 1)

    await message.answer(
        f"Assalomu alaykum, {message.from_user.first_name}!\n"
        f"Kerakli bo'limni tanlang:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

# 1. Reading bo'limi uchun (F.text orqali ushlaymiz)
@user_router.message(F.text == "📖 Reading")
async def open_reading(message: types.Message):
    builder = ReplyKeyboardBuilder()
    for i in range(1, 6):
        builder.add(types.KeyboardButton(text=f"Part {i}"))
    builder.add(types.KeyboardButton(text="⬅️ Asosiy menyu"))
    builder.adjust(2, 2, 1, 1)
    
    await message.answer("Reading bo'limi. Qaysi Partni ishlashni xohlaysiz?", 
                         reply_markup=builder.as_markup(resize_keyboard=True))

# 2. Asosiy menyuga qaytish tugmasi
@user_router.message(F.text == "⬅️ Asosiy menyu")
async def back_to_main(message: types.Message):
    await cmd_start(message) # Start komandasiga qaytarib yuboramiz

# 3. Boshqa tugmalar uchun vaqtinchalik javoblar (Kelajakda bularni to'ldirasiz)
@user_router.message(F.text == "🎧 Listening")
async def open_listening(message: types.Message):
    await message.answer("Listening bo'limi tez orada qo'shiladi! 🚧")

@user_router.message(F.text == "✍️ Writing")
async def open_writing(message: types.Message):
    await message.answer("Writing bo'limi tez orada qo'shiladi! 🚧")

@user_router.message(F.text == "🗣 Speaking")
async def open_speaking(message: types.Message):
    await message.answer("Speaking bo'limi tez orada qo'shiladi! 🚧")

@user_router.message(F.text == "👤 Profil va Natijalar")
async def open_profile(message: types.Message):
    await message.answer("Sizning profilingiz: Hozircha ma'lumotlar yo'q. 📊")

# 4. Catch-all (Tushunarsiz xabar yoki noma'lum tugma bosilganda ishlaydi)
# BU QATOR DOIM ENG PASTDA BO'LISHI KERAK
@user_router.message()
async def unknown_message(message: types.Message):
    await message.answer("Kechirasiz, bu buyruqni tushunmadim. Iltimos, menyudagi tugmalardan foydalaning. 👇")
