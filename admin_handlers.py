from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from config import ADMIN_IDS

admin_router = Router()

class AddMaterialState(StatesGroup):
    choosing_section = State()
    choosing_part = State()
    sending_content = State()
    sending_questions = State()
    sending_answers = State()
    confirming = State()

@admin_router.message(Command("add_material"))
async def cmd_add_material(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Sizda admin huquqi yo'q!")
        return
    
    kb = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Reading"), types.KeyboardButton(text="Listening")],
            [types.KeyboardButton(text="Bekor qilish")]
        ], resize_keyboard=True
    )
    await message.answer("Qaysi bo'limga material qo'shamiz?", reply_markup=kb)
    await state.set_state(AddMaterialState.choosing_section)

@admin_router.message(F.text == "Bekor qilish")
async def cancel_fsm(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Amaliyot bekor qilindi.", reply_markup=types.ReplyKeyboardRemove())

@admin_router.message(AddMaterialState.choosing_section, F.text.in_(["Reading", "Listening"]))
async def section_chosen(message: types.Message, state: FSMContext):
    await state.update_data(section=message.text)
    kb = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Part 1"), types.KeyboardButton(text="Part 2")],
            [types.KeyboardButton(text="Bekor qilish")]
        ], resize_keyboard=True
    )
    await message.answer(f"{message.text} tanlandi. Endi Partni tanlang:", reply_markup=kb)
    await state.set_state(AddMaterialState.choosing_part)

@admin_router.message(AddMaterialState.choosing_part, F.text.startswith("Part"))
async def part_chosen(message: types.Message, state: FSMContext):
    await state.update_data(part=message.text)
    user_data = await state.get_data()
    msg = "Audio faylni yuboring:" if user_data['section'] == "Listening" else "Asosiy matnni yuboring:"
    await message.answer(msg, reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(AddMaterialState.sending_content)

@admin_router.message(AddMaterialState.sending_content)
async def content_received(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    if user_data['section'] == "Listening" and message.audio:
        await state.update_data(content=message.audio.file_id)
    else:
        await state.update_data(content=message.text)
        
    await message.answer("Test savollarini yuboring (1..., 2...):")
    await state.set_state(AddMaterialState.sending_questions)

@admin_router.message(AddMaterialState.sending_questions)
async def questions_received(message: types.Message, state: FSMContext):
    await state.update_data(questions=message.text)
    await message.answer("To'g'ri javoblarni yuboring (Masalan: 1-A, 2-B):")
    await state.set_state(AddMaterialState.sending_answers)

@admin_router.message(AddMaterialState.sending_answers)
async def answers_received(message: types.Message, state: FSMContext):
    await state.update_data(answers=message.text)
    data = await state.get_data()
    
    summary = (
        f"📝 <b>Tasdiqlang:</b>\n"
        f"Bo'lim: {data['section']} | Qism: {data['part']}\n"
        f"Javoblar: {data['answers']}"
    )
    
    kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="Saqlash"), types.KeyboardButton(text="Bekor qilish")]],
        resize_keyboard=True
    )
    await message.answer(summary, reply_markup=kb, parse_mode="HTML")
    await state.set_state(AddMaterialState.confirming)

@admin_router.message(AddMaterialState.confirming, F.text == "Saqlash")
async def save_to_db(message: types.Message, state: FSMContext):
    data = await state.get_data()
    # TODO: Ma'lumotlar bazasiga yozish kodi shu yerda bo'ladi
    await message.answer("✅ Material saqlandi!", reply_markup=types.ReplyKeyboardRemove())
    await state.clear()
