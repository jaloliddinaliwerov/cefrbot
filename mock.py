import os
import datetime
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from sqlalchemy import select
from database import DBContext, MockExam, MockPurchase, Question, WritingTask, SpeakingTask, User, UserAchievement, UserProgress, BotSettings
from states import MockState
from ai_service import evaluate_writing, evaluate_speaking

router = Router()

class MockPaymentState(StatesGroup):
    waiting_screenshot = State()  # User sends payment screenshot

async def get_card_number() -> str:
    """Get card number from BotSettings table."""
    async with DBContext() as session:
        res = await session.execute(select(BotSettings).where(BotSettings.key == "card_number"))
        setting = res.scalar_one_or_none()
        return setting.value if setting and setting.value else "Karta raqami sozlanmagan. Admin bilan bog'laning."


@router.message(F.text == "🎓 Mock Exam")
async def mock_exam_menu(message: types.Message):
    user_id = message.from_user.id
    
    async with DBContext() as session:
        stmt = select(MockExam).where(MockExam.active == True)
        res = await session.execute(stmt)
        mocks = res.scalars().all()
        
        if not mocks:
            await message.answer("Hozircha faol Mock imtihonlar mavjud emas.")
            return
            
        markup = []
        for mock in mocks:
            # Check if purchased
            p_stmt = select(MockPurchase).where(
                MockPurchase.user_id == user_id,
                MockPurchase.mock_id == mock.id,
                MockPurchase.status == "completed"
            )
            p_res = await session.execute(p_stmt)
            purchased = p_res.scalar_one_or_none()
            
            status_str = "🔓 Ochildi" if purchased or mock.price == 0 else f"🔒 Pullik ({mock.price} UZS)"
            markup.append([InlineKeyboardButton(
                text=f"{mock.title} - {status_str}",
                callback_data=f"mock_view:{mock.id}"
            )])
            
        markup.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="mock_back_main")])
        
        await message.answer(
            "🎓 **CEFR Mock Imtihonlar bo'limi**\n\n"
            "Mock imtihoni Reading, Listening, Writing va Speaking bo'limlaridan iborat bo'lib, "
            "sizning haqiqiy CEFR darajangizni aniqlab beradi.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=markup)
        )

@router.callback_query(F.data == "mock_back_main")
async def back_to_main_menu_cb(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("Asosiy menyudasiz.", reply_markup=types.ReplyKeyboardRemove())
    from common import get_main_keyboard
    await callback.message.answer("Darslarni tanlang:", reply_markup=get_main_keyboard())

@router.callback_query(F.data.startswith("mock_view:"))
async def view_mock_exam(callback: types.CallbackQuery):
    mock_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    async with DBContext() as session:
        stmt = select(MockExam).where(MockExam.id == mock_id)
        res = await session.execute(stmt)
        mock = res.scalar_one_or_none()
        
        if not mock:
            await callback.answer("Imtihon topilmadi.", show_alert=True)
            return
            
        p_stmt = select(MockPurchase).where(
            MockPurchase.user_id == user_id,
            MockPurchase.mock_id == mock.id,
            MockPurchase.status == "completed"
        )
        p_res = await session.execute(p_stmt)
        purchased = p_res.scalar_one_or_none()

    markup = []
    
    # Check if they already own it
    if purchased or mock.price == 0:
        markup.append([InlineKeyboardButton(text="▶️ Imtihonni Boshlash", callback_data=f"mock_start:{mock.id}")])
    else:
        markup.append([InlineKeyboardButton(text=f"💳 Sotib olish ({mock.price:,} UZS)", callback_data=f"mock_buy:{mock.id}")])
    markup.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="mock_back_list")])

    
    details_text = (
        f"🎓 **{mock.title}**\n\n"
        f"💰 **Narxi:** {mock.price} UZS\n"
        f"📋 **Imtihon tarkibi:**\n"
        f"• Reading: Savollar to'plami\n"
        f"• Listening: Audio tahlil va savollar\n"
        f"• Writing: Insho topshirig'i\n"
        f"• Speaking: Ovozli javob tahlili\n\n"
        f"⚠️ **Diqqat!** Imtihonni boshlaganingizdan keyin uni oxirigacha topshirishingiz lozim. "
        f"Ovoz yozish uchun tinch joyda bo'ling."
    )
    
    await callback.message.delete()
    await callback.message.answer(details_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=markup))
    await callback.answer()

@router.callback_query(F.data == "mock_back_list")
async def back_to_mock_list(callback: types.CallbackQuery):
    await callback.message.delete()
    await mock_exam_menu(callback.message)
    await callback.answer()

# ─── Card Payment Flow ───────────────────────────────────────────────

@router.callback_query(F.data.startswith("mock_buy:"))
async def buy_mock_show_card(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Show card number and ask user to send payment screenshot."""
    mock_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    async with DBContext() as session:
        # Check existing pending/completed purchase
        p_stmt = select(MockPurchase).where(
            MockPurchase.user_id == user_id,
            MockPurchase.mock_id == mock_id,
            MockPurchase.status.in_(["completed", "pending"])
        )
        p_res = await session.execute(p_stmt)
        existing = p_res.scalar_one_or_none()
        if existing:
            if existing.status == "completed":
                await callback.answer("Siz ushbu mockni allaqachon sotib olgansiz!", show_alert=True)
            else:
                await callback.answer("Sizning to'lovingiz hali admin tomonidan tasdiqlanmagan. Kuting.", show_alert=True)
            return

        stmt = select(MockExam).where(MockExam.id == mock_id)
        res = await session.execute(stmt)
        mock = res.scalar_one_or_none()
        if not mock:
            await callback.answer("Mock topilmadi.", show_alert=True)
            return

    card_number = await get_card_number()

    await state.set_state(MockPaymentState.waiting_screenshot)
    await state.update_data(mock_id=mock_id, mock_title=mock.title, mock_price=mock.price)

    await callback.message.delete()
    await callback.message.answer(
        f"💳 **To'lov ma'lumotlari**\n\n"
        f"📌 **Mock:** {mock.title}\n"
        f"💰 **Narxi:** {mock.price:,} UZS\n\n"
        f"🏦 **Karta raqami:**\n"
        f"`{card_number}`\n\n"
        f"📋 **Ko'rsatma:**\n"
        f"1. Yuqoridagi karta raqamiga {mock.price:,} UZS o'tkazing\n"
        f"2. To'lov chekini (screenshot) shu chatga yuboring\n"
        f"3. Admin tekshirib, kirish ruxsatini beradi\n\n"
        f"⏳ Odatda 5-30 daqiqa ichida tasdiqlanadi.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="mock_back_list")]
        ])
    )
    await callback.answer()

@router.message(MockPaymentState.waiting_screenshot, F.photo)
async def receive_payment_screenshot(message: types.Message, state: FSMContext, bot: Bot):
    """User sends payment screenshot — save and notify admins."""
    data = await state.get_data()
    mock_id = data.get("mock_id")
    mock_title = data.get("mock_title")
    mock_price = data.get("mock_price")
    user_id = message.from_user.id

    # Get best quality photo
    photo = message.photo[-1]
    file_id = photo.file_id

    async with DBContext() as session:
        purchase = MockPurchase(
            user_id=user_id,
            mock_id=mock_id,
            status="pending",
            screenshot_file_id=file_id,
            purchased_at=datetime.datetime.utcnow()
        )
        session.add(purchase)
        await session.commit()
        purchase_id = purchase.id

    await state.clear()

    await message.answer(
        f"✅ **Chekingiz qabul qilindi!**\n\n"
        f"📌 {mock_title}\n"
        f"⏳ Admin tez orada tekshiradi va kirish beradi.\n\n"
        f"Tasdiqlanganda xabar olasiz!",
        parse_mode="Markdown"
    )

    # Notify all admins
    admin_ids_str = os.getenv("ADMIN_IDS", "")
    admin_ids = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip().isdigit()]

    user_name = message.from_user.full_name or "Foydalanuvchi"
    username = f"@{message.from_user.username}" if message.from_user.username else f"ID: {user_id}"

    price_val = mock_price if mock_price is not None else 0
    caption = (
        f"💳 **Yangi to'lov so'rovi!**\n\n"
        f"👤 {user_name} ({username})\n"
        f"🎓 Mock: **{mock_title}**\n"
        f"💰 Narxi: {price_val:,} UZS\n"
        f"🆔 Purchase ID: #{purchase_id}\n\n"
        f"To'lov chekini tekshiring va qaror qiling:"
    )
    approve_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"mock_approve:{purchase_id}:{user_id}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"mock_reject:{purchase_id}:{user_id}")
        ]
    ])

    for admin_id in admin_ids:
        try:
            await bot.send_photo(
                chat_id=admin_id,
                photo=file_id,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=approve_kb
            )
        except Exception:
            pass

@router.message(MockPaymentState.waiting_screenshot)
async def payment_wrong_format(message: types.Message):
    await message.answer(
        "📸 Iltimos, faqat **rasm (screenshot)** yuboring!\n"
        "To'lov chekining skrinshotini yubormasangiz, to'lovingiz tasdiqlanmaydi.",
        parse_mode="Markdown"
    )

# ─── Admin approve / reject ───────────────────────────────────────────

@router.callback_query(F.data.startswith("mock_approve:"))
async def admin_approve_payment(callback: types.CallbackQuery, bot: Bot):
    user_id_str = str(callback.from_user.id)
    admin_ids = os.getenv("ADMIN_IDS", "").split(",")
    if user_id_str not in admin_ids:
        await callback.answer("Siz admin emassiz!", show_alert=True)
        return

    parts = callback.data.split(":")
    purchase_id = int(parts[1])
    student_id = int(parts[2])

    async with DBContext() as session:
        p_stmt = select(MockPurchase).where(MockPurchase.id == purchase_id)
        p_res = await session.execute(p_stmt)
        purchase = p_res.scalar_one_or_none()
        if not purchase:
            await callback.answer("To'lov topilmadi!", show_alert=True)
            return
        if purchase.status == "completed":
            await callback.answer("Bu to'lov allaqachon tasdiqlangan.", show_alert=True)
            return

        purchase.status = "completed"
        mock_stmt = select(MockExam).where(MockExam.id == purchase.mock_id)
        mock_res = await session.execute(mock_stmt)
        mock = mock_res.scalar_one_or_none()
        await session.commit()

    mock_title = mock.title if mock else "Mock Exam"

    # Edit admin message
    await callback.message.edit_caption(
        caption=callback.message.caption + "\n\n✅ **TASDIQLANDI** — " + callback.from_user.full_name,
        parse_mode="Markdown",
        reply_markup=None
    )
    await callback.answer("Tasdiqlandi!")

    # Notify student
    try:
        await bot.send_message(
            chat_id=student_id,
            text=f"🎉 **To'lovingiz tasdiqlandi!**\n\n"
                 f"🎓 **{mock_title}** mockiga kirish ruxsati berildi.\n"
                 f"Endi Mock Exam bo'limidan boshlashingiz mumkin! 🚀",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎓 Mock Exanga o'tish", callback_data=f"mock_view:{purchase.mock_id}")]
            ])
        )
    except Exception:
        pass

@router.callback_query(F.data.startswith("mock_reject:"))
async def admin_reject_payment(callback: types.CallbackQuery, bot: Bot):
    user_id_str = str(callback.from_user.id)
    admin_ids = os.getenv("ADMIN_IDS", "").split(",")
    if user_id_str not in admin_ids:
        await callback.answer("Siz admin emassiz!", show_alert=True)
        return

    parts = callback.data.split(":")
    purchase_id = int(parts[1])
    student_id = int(parts[2])

    async with DBContext() as session:
        p_stmt = select(MockPurchase).where(MockPurchase.id == purchase_id)
        p_res = await session.execute(p_stmt)
        purchase = p_res.scalar_one_or_none()
        if not purchase:
            await callback.answer("To'lov topilmadi!", show_alert=True)
            return

        purchase.status = "rejected"
        purchase.reject_reason = "Admin tomonidan rad etildi"
        await session.commit()

    await callback.message.edit_caption(
        caption=callback.message.caption + "\n\n❌ **RAD ETILDI** — " + callback.from_user.full_name,
        parse_mode="Markdown",
        reply_markup=None
    )
    await callback.answer("Rad etildi.")

    try:
        await bot.send_message(
            chat_id=student_id,
            text="❌ **To'lovingiz tasdiqlanmadi.**\n\n"
                 "Sabab: to'lov cheki noto'g'ri yoki miqdor mos kelmadi.\n"
                 "Qaytadan to'g'ri miqdorda o'tkazing va yangi chek yuboring.",
            parse_mode="Markdown"
        )
    except Exception:
        pass


# ----------------- RUNNING MOCK EXAM -----------------

@router.callback_query(F.data.startswith("mock_start:"))
async def start_mock_exam(callback: types.CallbackQuery, state: FSMContext):
    mock_id = int(callback.data.split(":")[1])
    
    async with DBContext() as session:
        stmt = select(MockExam).where(MockExam.id == mock_id)
        res = await session.execute(stmt)
        mock = res.scalar_one_or_none()
        
        if not mock:
            await callback.answer("Mock topilmadi.", show_alert=True)
            return
            
        reading_ids = mock.questions_ids or []
        writing_ids = mock.writing_ids or []
        speaking_ids = mock.speaking_ids or []
        
        # Listening questions are also stored in questions_ids table.
        # Let's filter them out based on section
        all_q_stmt = select(Question).where(Question.id.in_(reading_ids))
        all_q_res = await session.execute(all_q_stmt)
        all_qs = all_q_res.scalars().all()
        
        mock_readings = [q.id for q in all_qs if q.section == "reading"]
        mock_listenings = [q.id for q in all_qs if q.section == "listening"]
        
    # Store everything in FSM
    await state.set_state(MockState.answering_reading)
    await state.update_data(
        mock_id=mock_id,
        reading_ids=mock_readings,
        listening_ids=mock_listenings,
        writing_ids=writing_ids,
        speaking_ids=speaking_ids,
        current_idx=0,
        results_reading={},
        results_listening={},
        writing_text="",
        speaking_file_id=""
    )
    
    await callback.message.delete()
    await callback.message.answer(
        "📝 **MOCK IMTIHON BOSHLANDI**\n\n"
        "**1-bo'lim: Reading (O'qish)**\n"
        "Sizga o'qish matnlari va savollar yuboriladi. Javoblaringizni diqqat bilan yuboring."
    )
    
    # Run the first Reading question
    await send_next_mock_reading(callback.message, state)
    await callback.answer()

async def send_next_mock_reading(message: types.Message, state: FSMContext):
    data = await state.get_data()
    reading_ids = data["reading_ids"]
    idx = data["current_idx"]
    
    if idx >= len(reading_ids):
        # Reading finished, proceed to Listening!
        await state.update_data(current_idx=0) # reset index for listening
        await state.set_state(MockState.answering_listening)
        await message.answer(
            "✅ **Reading bo'limi yakunlandi.**\n\n"
            "**2-bo'lim: Listening (Eshitish)**\n"
            "Keyingi bosqichda sizga audio fayl va uning savollari yuboriladi."
        )
        await send_next_mock_listening(message, state)
        return
        
    # Retrieve reading question
    q_id = reading_ids[idx]
    async with DBContext() as session:
        stmt = select(Question).where(Question.id == q_id)
        res = await session.execute(stmt)
        question = res.scalar_one_or_none()
        
    # Format message
    q_text = f"📖 **Reading Task {idx + 1}**\n\n"
    q_text += f"📌 **{question.title}**\n\n"
    q_text += f"{question.text}\n\n"
    q_text += "📝 **Savollar:**\n"
    for q_idx, q_item in enumerate(question.questions_json, 1):
        q_text += f"\n**{q_idx}. {q_item['q']}**\n"
        for opt in q_item.get('options', []):
            q_text += f"   {opt}\n"
    q_text += "\n✍️ Javoblaringizni `1-A, 2-C` ko'rinishida yozib yuboring:"
    
    await message.answer(q_text, parse_mode="Markdown")

# Regex to parse answers
import re
def parse_answers(text: str) -> dict:
    pattern = re.compile(r"(\d+)[\s\-:.]*([A-Da-d])")
    matches = pattern.findall(text)
    return {int(q_num): ans.upper() for q_num, ans in matches}

@router.message(MockState.answering_reading, F.text)
async def process_mock_reading(message: types.Message, state: FSMContext):
    data = await state.get_data()
    reading_ids = data["reading_ids"]
    idx = data["current_idx"]
    results = data["results_reading"]
    
    user_answers = parse_answers(message.text)
    if not user_answers:
        await message.answer("⚠️ Noto'g'ri format. Iltimos, javoblarni `1-A, 2-C` shaklida yuboring.")
        return
        
    q_id = reading_ids[idx]
    async with DBContext() as session:
        stmt = select(Question).where(Question.id == q_id)
        res = await session.execute(stmt)
        question = res.scalar_one_or_none()
        
    # Grade this part
    correct_count = 0
    total = len(question.questions_json)
    
    for q_idx, q_item in enumerate(question.questions_json, 1):
        correct_ans = q_item["answer"].upper().strip()
        if len(correct_ans) > 1 and ":" in correct_ans:
            correct_ans = correct_ans.split(":")[0].strip()
        user_ans = user_answers.get(q_idx, "").upper().strip()
        if user_ans == correct_ans:
            correct_count += 1
            
    results[q_id] = {"correct": correct_count, "total": total}
    
    # Update and check next
    await state.update_data(results_reading=results, current_idx=idx + 1)
    await send_next_mock_reading(message, state)

# ----------------- LISTENING SECTION -----------------

async def send_next_mock_listening(message: types.Message, state: FSMContext):
    data = await state.get_data()
    listening_ids = data["listening_ids"]
    idx = data["current_idx"]
    
    if idx >= len(listening_ids):
        # Listening finished, proceed to Writing!
        await state.set_state(MockState.submitting_writing)
        await message.answer(
            "✅ **Listening bo'limi yakunlandi.**\n\n"
            "**3-bo'lim: Writing (Yozish)**\n"
            "Keyingi bosqichda sizga yozma topshiriq yuboriladi."
        )
        await send_mock_writing(message, state)
        return
        
    q_id = listening_ids[idx]
    async with DBContext() as session:
        stmt = select(Question).where(Question.id == q_id)
        res = await session.execute(stmt)
        question = res.scalar_one_or_none()
        
    await message.answer(f"🎧 **Listening Task {idx + 1}**\n📌 **{question.title}**\nAudio yuklanmoqda, iltimos kuting...")
    
    try:
        if question.audio_url:
            await message.answer_audio(audio=question.audio_url, caption="Audio fayl.")
        else:
            await message.answer("⚠️ Audio yuklash imkoni bo'lmadi.")
    except Exception:
        await message.answer("⚠️ Audio yuklash imkoni bo'lmadi.")
        
    q_text = "📝 **Savollar:**\n"
    for q_idx, q_item in enumerate(question.questions_json, 1):
        q_text += f"\n**{q_idx}. {q_item['q']}**\n"
        for opt in q_item.get('options', []):
            q_text += f"   {opt}\n"
    q_text += "\n✍️ Javoblarni `1-A, 2-C` ko'rinishida yozib yuboring:"
    
    await message.answer(q_text, parse_mode="Markdown")

@router.message(MockState.answering_listening, F.text)
async def process_mock_listening(message: types.Message, state: FSMContext):
    data = await state.get_data()
    listening_ids = data["listening_ids"]
    idx = data["current_idx"]
    results = data["results_listening"]
    
    user_answers = parse_answers(message.text)
    if not user_answers:
        await message.answer("⚠️ Noto'g'ri format. Iltimos, javoblarni `1-A, 2-C` shaklida yuboring.")
        return
        
    q_id = listening_ids[idx]
    async with DBContext() as session:
        stmt = select(Question).where(Question.id == q_id)
        res = await session.execute(stmt)
        question = res.scalar_one_or_none()
        
    correct_count = 0
    total = len(question.questions_json)
    
    for q_idx, q_item in enumerate(question.questions_json, 1):
        correct_ans = q_item["answer"].upper().strip()
        if len(correct_ans) > 1 and ":" in correct_ans:
            correct_ans = correct_ans.split(":")[0].strip()
        user_ans = user_answers.get(q_idx, "").upper().strip()
        if user_ans == correct_ans:
            correct_count += 1
            
    results[q_id] = {"correct": correct_count, "total": total}
    
    await state.update_data(results_listening=results, current_idx=idx + 1)
    await send_next_mock_listening(message, state)

# ----------------- WRITING SECTION -----------------

async def send_mock_writing(message: types.Message, state: FSMContext):
    data = await state.get_data()
    writing_ids = data["writing_ids"]
    
    if not writing_ids:
        # Skip writing if not configured
        await state.set_state(MockState.submitting_speaking)
        await message.answer("Writing topshiriqlari yo'q. Speaking bo'limiga o'tamiz.")
        await send_mock_speaking(message, state)
        return
        
    w_id = writing_ids[0]
    async with DBContext() as session:
        stmt = select(WritingTask).where(WritingTask.id == w_id)
        res = await session.execute(stmt)
        task = res.scalar_one_or_none()
        
    q_text = (
        f"✍️ **Writing Topsirig'i ({task.level})**\n\n"
        f"📌 **{task.title}**\n\n"
        f"📝 **Prompt:**\n{task.prompt}\n\n"
        f"⚠️ Insho matnini shu chatga yozib yuboring (kamida 150 ta so'z):"
    )
    
    await state.update_data(writing_task_id=task.id, writing_prompt=task.prompt)
    await message.answer(q_text, parse_mode="Markdown")

@router.message(MockState.submitting_writing, F.text)
async def process_mock_writing(message: types.Message, state: FSMContext):
    essay_text = message.text
    if len(essay_text.split()) < 10:
        await message.answer("⚠️ Insho juda qisqa. Kamida 10 ta so'zdan iborat matn yuboring.")
        return
        
    await state.update_data(writing_text=essay_text)
    
    await state.set_state(MockState.submitting_speaking)
    await message.answer(
        "✅ **Writing bo'limi yakunlandi.**\n\n"
        "**4-bo'lim: Speaking (Gapirish)**\n"
        "Keyingi bosqichda sizga og'zaki mavzu yuboriladi."
    )
    await send_mock_speaking(message, state)

# ----------------- SPEAKING SECTION -----------------

async def send_mock_speaking(message: types.Message, state: FSMContext):
    data = await state.get_data()
    speaking_ids = data["speaking_ids"]
    
    if not speaking_ids:
        # End mock exam directly
        await grade_mock_exam(message, state, None)
        return
        
    s_id = speaking_ids[0]
    async with DBContext() as session:
        stmt = select(SpeakingTask).where(SpeakingTask.id == s_id)
        res = await session.execute(stmt)
        task = res.scalar_one_or_none()
        
    q_text = (
        f"🗣️ **Speaking Topshirig'i ({task.level})**\n\n"
        f"📌 **{task.title}**\n\n"
        f"📝 **Mavzu:**\n{task.prompt}\n\n"
        f"🎙️ Iltimos, 1-2 daqiqalik ovozli xabar (Voice message) yuboring:"
    )
    
    await state.update_data(speaking_task_id=task.id, speaking_prompt=task.prompt)
    await message.answer(q_text, parse_mode="Markdown")

@router.message(MockState.submitting_speaking, F.voice)
async def process_mock_speaking(message: types.Message, state: FSMContext, bot: Bot):
    await state.update_data(speaking_file_id=message.voice.file_id)
    await grade_mock_exam(message, state, bot)

@router.message(MockState.submitting_speaking)
async def process_mock_speaking_invalid(message: types.Message):
    await message.answer("⚠️ Iltimos, faqat ovozli xabar (Voice message) yuboring.")

# ----------------- GRADING AND RESULTS -----------------

async def grade_mock_exam(message: types.Message, state: FSMContext, bot: Bot):
    await message.answer("📥 **Imtihon topshirildi!**\nSun'iy intellekt javoblaringizni tekshirmoqda, iltimos kuting (1-2 daqiqa)...")
    
    data = await state.get_data()
    results_reading = data["results_reading"]
    results_listening = data["results_listening"]
    writing_text = data["writing_text"]
    writing_prompt = data.get("writing_prompt", "")
    speaking_file_id = data["speaking_file_id"]
    speaking_prompt = data.get("speaking_prompt", "")
    
    # 1. Evaluate Reading & Listening
    total_reading_correct = sum(v["correct"] for v in results_reading.values())
    total_reading_questions = sum(v["total"] for v in results_reading.values()) or 1
    reading_percentage = (total_reading_correct / total_reading_questions) * 100
    
    total_listening_correct = sum(v["correct"] for v in results_listening.values())
    total_listening_questions = sum(v["total"] for v in results_listening.values()) or 1
    listening_percentage = (total_listening_correct / total_listening_questions) * 100
    
    # 2. Evaluate Writing via AI
    writing_feedback = {}
    if writing_text:
        writing_feedback = await evaluate_writing(writing_text, writing_prompt)
        
    writing_score = writing_feedback.get("score", 50) # Fallback score
    
    # 3. Evaluate Speaking via AI
    speaking_feedback = {}
    if speaking_file_id and bot:
        temp_dir = "temp"
        os.makedirs(temp_dir, exist_ok=True)
        voice_path = os.path.join(temp_dir, f"mock_voice_{message.from_user.id}.ogg")
        try:
            file_info = await bot.get_file(speaking_file_id)
            await bot.download_file(file_info.file_path, voice_path)
            speaking_feedback = await evaluate_speaking(voice_path, speaking_prompt)
        except Exception as e:
            speaking_feedback = {"score": 50, "level": "B1", "advice": f"Speech grading error: {e}"}
        finally:
            if os.path.exists(voice_path):
                try:
                    os.remove(voice_path)
                except Exception:
                    pass
    else:
        speaking_feedback = {"score": 50, "level": "B1", "advice": "No speech recorded."}
        
    speaking_score = speaking_feedback.get("score", 50)
    
    # 4. Overall calculations
    # Overall score as average of percentages/scores
    overall_score = int((reading_percentage + listening_percentage + writing_score + speaking_score) / 4)
    
    # Map overall score to CEFR level
    if overall_score >= 85:
        overall_level = "C1"
    elif overall_score >= 65:
        overall_level = "B2"
    elif overall_score >= 45:
        overall_level = "B1"
    else:
        overall_level = "A2"
        
    # Save statistics and unlock achievements
    async with DBContext() as session:
        user_stmt = select(User).where(User.id == message.from_user.id)
        user_res = await session.execute(user_stmt)
        user = user_res.scalar_one_or_none()
        
        if user:
            user.xp += 300  # Bonus for mock exam completion!
            
            # Unlock mock_master achievement
            ach_stmt = select(UserAchievement).where(
                UserAchievement.user_id == user.id,
                UserAchievement.achievement_id == "mock_master"
            )
            ach_res = await session.execute(ach_stmt)
            if not ach_res.scalar_one_or_none():
                new_ach = UserAchievement(user_id=user.id, achievement_id="mock_master")
                session.add(new_ach)
                user.xp += 200
                await message.answer("🎉 **MOCK IMTIHON MASTERI!**\n🏆 Mock Eksperti yutug'i ochildi! | +200 XP")
                
        # Register progress entries
        for q_id, v in results_reading.items():
            progress = UserProgress(
                user_id=message.from_user.id,
                question_id=q_id,
                score=v["correct"],
                max_score=v["total"]
            )
            session.add(progress)
            
        for q_id, v in results_listening.items():
            progress = UserProgress(
                user_id=message.from_user.id,
                question_id=q_id,
                score=v["correct"],
                max_score=v["total"]
            )
            session.add(progress)
            
        await session.commit()
        
    # Format scorecard
    scorecard = (
        f"🏆 **CEFR MOCK IMTIHON SERTIFIKATI** 🏆\n\n"
        f"👤 **O'quvchi:** {message.from_user.first_name}\n"
        f"📅 **Sana:** {datetime.date.today().strftime('%Y-%m-%d')}\n"
        f"🎓 **Yakuniy CEFR daraja:** ✨**{overall_level}**✨\n"
        f"🎯 **Umumiy ball:** {overall_score}/100\n\n"
        f"📊 **Bo'limlar kesimida natijalar:**\n"
        f"• 📖 **Reading:** {total_reading_correct}/{total_reading_questions} to'g'ri ({reading_percentage:.1f}%)\n"
        f"• 🎧 **Listening:** {total_listening_correct}/{total_listening_questions} to'g'ri ({listening_percentage:.1f}%)\n"
        f"• ✍️ **Writing:** {writing_score}/100 (Daraja: {writing_feedback.get('level', 'B2')})\n"
        f"• 🗣️ **Speaking:** {speaking_score}/100 (Daraja: {speaking_feedback.get('level', 'B2')})\n\n"
        f"💡 **AI Ekspert Tavsiyasi:**\n"
        f"Writing: _{writing_feedback.get('advice', '')}_\n\n"
        f"Speaking: _{speaking_feedback.get('advice', '')}_\n\n"
        f"⚡️ +300 XP hisobingizga qo'shildi!"
    )
    
    await state.clear()
    
    # Return to menu buttons
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Asosiy Menyu", callback_data="mock_back_main")]
    ])
    await message.answer(scorecard, reply_markup=markup, parse_mode="Markdown")
