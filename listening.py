import re
import os
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from database import DBContext, Question, UserProgress, UserIncorrectQuestion, User, UserAchievement, BotSettings
from states import ListeningState
from answer_utils import parse_answers_universal, check_answers, send_result_messages

router = Router()

def get_listening_parts_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="Part 1", callback_data="listening_part:1"),
            InlineKeyboardButton(text="Part 2", callback_data="listening_part:2"),
        ],
        [
            InlineKeyboardButton(text="Part 3", callback_data="listening_part:3"),
            InlineKeyboardButton(text="Part 4", callback_data="listening_part:4"),
        ],
        [
            InlineKeyboardButton(text="Part 5", callback_data="listening_part:5"),
        ],
        [
            InlineKeyboardButton(text="🔙 Orqaga", callback_data="listening_back_main")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@router.message(F.text == "🎧 Listening")
async def listening_menu(message: types.Message):
    await message.answer(
        "🎧 *Listening bo'limi*\n\nIltimos, ishlashni xohlagan qismingizni tanlang:",
        reply_markup=get_listening_parts_keyboard(),
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "listening_back_main")
async def back_to_main_menu_cb(callback: types.CallbackQuery):
    await callback.message.delete()
    from common import get_main_keyboard
    await callback.message.answer("Darslarni tanlang:", reply_markup=get_main_keyboard())

@router.callback_query(F.data.startswith("listening_part:"))
async def select_listening_part(callback: types.CallbackQuery, state: FSMContext):
    part = int(callback.data.split(":")[1])
    
    async with DBContext() as session:
        stmt = select(Question).where(
            Question.section == "listening",
            Question.part == part,
            Question.is_mock == False
        )
        res = await session.execute(stmt)
        questions = res.scalars().all()
        
        if not questions:
            await callback.answer("Hozircha bu Part uchun listening materiallari mavjud emas.", show_alert=True)
            return

        markup = []
        for q in questions:
            markup.append([InlineKeyboardButton(
                text=f"{q.title}",
                callback_data=f"listening_test:{q.id}:{part}"
            )])
        markup.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="listening_back_parts")])
        
        await callback.message.delete()
        await callback.message.answer(
            f"🎧 *Listening - Part {part}*\n\nIshlash uchun testni tanlang:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=markup),
            parse_mode="Markdown"
        )
        await callback.answer()

@router.callback_query(F.data == "listening_back_parts")
async def back_to_listening_parts_cb(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.message.answer(
        "🎧 *Listening bo'limi*\n\nIltimos, ishlashni xohlagan qismingizni tanlang:",
        reply_markup=get_listening_parts_keyboard(),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("listening_test:"))
async def start_listening_test_cb(callback: types.CallbackQuery, state: FSMContext):
    _, q_id_str, part_str = callback.data.split(":")
    q_id = int(q_id_str)
    part = int(part_str)
    
    async with DBContext() as session:
        stmt = select(Question).where(Question.id == q_id)
        res = await session.execute(stmt)
        question = res.scalar_one_or_none()
        if not question:
            await callback.answer("Test topilmadi.", show_alert=True)
            return
        await callback.message.delete()
        await start_listening_test(callback.message, question, part, state)
        await callback.answer()

async def _send_audio(message: types.Message, audio_url: str, part: int):
    """Send audio file. Returns True if sent successfully."""
    try:
        if audio_url.startswith("/"):
            site_url = os.getenv("SITE_URL", "").strip().rstrip("/")
            if site_url and not site_url.startswith("http"):
                site_url = f"https://{site_url}"
            audio_url = f"{site_url}{audio_url}" if site_url else audio_url
        await message.answer_audio(
            audio=audio_url,
            caption=f"🎧 Listening Part {part} — Audio fayl"
        )
        return True
    except Exception as e:
        await message.answer(f"⚠️ Audio yuklashda xatolik: {e}\nSavollarni matn orqali ishlashingiz mumkin.")
        return False

async def _send_pdf(message: types.Message, pdf_val: str, state: FSMContext) -> bool:
    """Send PDF from channel link or file_id. Returns True on success."""
    if pdf_val.startswith("http") or "t.me" in pdf_val:
        from common import parse_telegram_message_link
        chat_id, msg_id = parse_telegram_message_link(pdf_val)
        if chat_id and msg_id:
            try:
                await message.bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=chat_id,
                    message_id=msg_id
                )
                return True
            except Exception as e:
                await message.answer(
                    f"⚠️ PDF faylni yuborishda xatolik: {e}\n"
                    "Bot kanalda admin ekanligini tekshiring."
                )
                await state.clear()
                return False
        else:
            await message.answer("⚠️ PDF ssilkasi formati noto'g'ri.")
            await state.clear()
            return False
    else:
        try:
            await message.answer_document(document=pdf_val)
            return True
        except Exception as e:
            await message.answer(f"⚠️ PDF faylni yuborishda xatolik: {e}")
            await state.clear()
            return False

def _answer_hint() -> str:
    return (
        "✍️ *Javoblaringizni bitta xabar shaklida yuboring.*\n"
        "Quyidagi formatlarning istalganida yozishingiz mumkin:\n\n"
        "`1-A, 2-C, 3-B`\n"
        "`1. Apple  2. Orange  3. Banana`\n"
        "`1A 2B 3C`\n"
        "`A B C D E` (tartib bo'yicha)\n\n"
        "Javobingizni quyida yozib yuboring:"
    )

async def get_channel_link_for_listening(question: Question, part: int) -> str | None:
    """Get channel post link or configured channel link for this listening part."""
    pdf_val = getattr(question, "pdf_file_id", None)
    if pdf_val and (pdf_val.startswith("http") or "t.me" in pdf_val):
        link = pdf_val.strip()
        if not link.startswith("http"):
            link = f"https://{link}"
        return link

    async with DBContext() as session:
        stmt = select(BotSettings.value).where(BotSettings.key == f"chan_list_{part}")
        res = await session.execute(stmt)
        val = res.scalar_one_or_none()
        if val:
            val = val.strip()
            if val.startswith("@"):
                return f"https://t.me/{val[1:]}"
            elif val.startswith("http"):
                return val
            elif "t.me" in val:
                return f"https://{val}"
            elif val:
                return f"https://t.me/{val}"

    return None

async def start_listening_test(message: types.Message, question: Question, part: int, state: FSMContext):
    await state.set_state(ListeningState.answering)
    await state.update_data(question_id=question.id, part=part)

    # Get channel link for listening material if configured
    chan_link = await get_channel_link_for_listening(question, part)

    # Send audio first (if any), then PDF or text questions
    if question.audio_url:
        await _send_audio(message, question.audio_url, part)

    markup = None
    if chan_link:
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Kanaldan topshiriqni ko'rish", url=chan_link)]
        ])

    # Check for PDF
    pdf_val = getattr(question, "pdf_file_id", None)
    if pdf_val:
        sent_ok = await _send_pdf(message, pdf_val, state)
        if not sent_ok:
            return

        questions_list = question.questions_json or []
        total = len(questions_list)
        q_text = (
            f"🎧 *Listening - Part {part}*\n"
            f"📌 *{question.title}*\n\n"
        )
        if chan_link:
            q_text += f"📢 *Kanal havolasi:* [Savol va audioni kanalda ko'rish]({chan_link})\n\n"

        if total > 0:
            q_text += f"📝 Jami *{total}* ta savol bor.\n\n"
        q_text += _answer_hint()
        await message.answer(q_text, reply_markup=markup, parse_mode="Markdown")
        return

    # Text-based questions (no PDF)
    questions_list = question.questions_json or []
    if not questions_list:
        await message.answer("⚠️ Bu testda savollar topilmadi. Admin bilan bog'laning.")
        await state.clear()
        return

    if not question.audio_url and not chan_link:
        await message.answer("⚠️ Audio fayl topilmadi, savollarga matn asosida javob bering.")

    q_text = f"🎧 *Listening - Part {part}*\n📌 *{question.title}*\n\n"
    if chan_link:
        q_text += f"📢 *Kanal havolasi:* [Savol va audioni kanalda ko'rish]({chan_link})\n\n"

    q_text += "📝 *Savollar:*\n"
    has_options = any(len(q_item.get('options', [])) > 0 for q_item in questions_list)
    
    for idx, q_item in enumerate(questions_list, 1):
        q_text += f"\n*{idx}. {q_item['q']}*\n"
        for opt in q_item.get('options', []):
            q_text += f"   {opt}\n"
            
    if has_options:
        q_text += "\n✍️ Javob formati: `1-A, 2-B, 3-C`"
    else:
        q_text += "\n✍️ Javob formati: `1-Apple, 2-Orange, 3-Banana`"

    if len(q_text) > 4000:
        await message.answer(q_text[:4000], parse_mode="Markdown")
        await message.answer(q_text[4000:] + "\n\n✍️ Javoblarni yozing:", reply_markup=markup, parse_mode="Markdown")
    else:
        await message.answer(q_text, reply_markup=markup, parse_mode="Markdown")

@router.message(ListeningState.answering, F.text)
async def process_listening_answers(message: types.Message, state: FSMContext):
    state_data = await state.get_data()
    question_id = state_data.get("question_id")
    part = state_data.get("part")
    
    user_answers = parse_answers_universal(message.text)
    
    if not user_answers:
        await message.answer(
            "⚠️ Javobingiz formatini aniqlab bo'lmadi.\n"
            "Iltimos quyidagi formatlardan birida yuboring:\n"
            "`1-A, 2-C, 3-B`\n"
            "`1. Apple  2. Orange`\n"
            "`A B C D` (tartib bo'yicha)",
            parse_mode="Markdown"
        )
        return

    xp_earned = 0
    correct_count = 0
    total_questions = 0
    percentage = 0.0

    async with DBContext() as session:
        stmt = select(Question).where(Question.id == question_id)
        res = await session.execute(stmt)
        question = res.scalar_one_or_none()
        
        if not question:
            await message.answer("Xatolik yuz berdi: Test topilmadi.")
            await state.clear()
            return
            
        questions_list = question.questions_json or []
        total_questions = len(questions_list)
        
        if total_questions == 0:
            await message.answer("⚠️ Bu testda savollar topilmadi.")
            await state.clear()
            return
        
        correct_count, result_details, wrong_answers = check_answers(user_answers, questions_list)
        
        percentage = (correct_count / total_questions) * 100
        xp_earned = correct_count * 10

        progress = UserProgress(
            user_id=message.from_user.id,
            question_id=question_id,
            score=correct_count,
            max_score=total_questions,
            wrong_answers_json=wrong_answers,
        )
        session.add(progress)
        
        if wrong_answers:
            wrong_stmt = select(UserIncorrectQuestion).where(
                UserIncorrectQuestion.user_id == message.from_user.id,
                UserIncorrectQuestion.question_id == question_id
            )
            wrong_res = await session.execute(wrong_stmt)
            incorrect_entry = wrong_res.scalar_one_or_none()
            if not incorrect_entry:
                incorrect_entry = UserIncorrectQuestion(
                    user_id=message.from_user.id,
                    question_id=question_id,
                    wrong_answers_json=wrong_answers
                )
                session.add(incorrect_entry)
            else:
                incorrect_entry.wrong_answers_json = wrong_answers
        else:
            del_stmt = select(UserIncorrectQuestion).where(
                UserIncorrectQuestion.user_id == message.from_user.id,
                UserIncorrectQuestion.question_id == question_id
            )
            del_res = await session.execute(del_stmt)
            incorrect_entry = del_res.scalar_one_or_none()
            if incorrect_entry:
                await session.delete(incorrect_entry)

        user_stmt = select(User).where(User.id == message.from_user.id)
        user_res = await session.execute(user_stmt)
        user = user_res.scalar_one_or_none()
        if user:
            if user.is_premium:
                xp_earned *= 2
            user.xp += xp_earned
            
            ach_stmt = select(UserAchievement).where(
                UserAchievement.user_id == user.id,
                UserAchievement.achievement_id == "first_test"
            )
            ach_res = await session.execute(ach_stmt)
            if not ach_res.scalar_one_or_none():
                new_ach = UserAchievement(user_id=user.id, achievement_id="first_test")
                session.add(new_ach)
                user.xp += 50
                await message.answer("🎉 *Yangi Yutuq Ochildi!*\n🏆 Birinchi Qadam | +50 XP", parse_mode="Markdown")

        await session.commit()

    await state.clear()

    # Send breakdown (auto-split)
    await send_result_messages(
        message,
        result_details,
        header="📊 *Listening Natijasi:*"
    )

    summary = (
        f"📈 *Natija:* {percentage:.1f}%\n"
        f"🎯 *To'g'ri:* {correct_count}/{total_questions}\n"
        f"⚡️ *XP:* +{xp_earned} XP"
    )

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Qayta ishlash", callback_data=f"listening_retake:{question_id}"),
            InlineKeyboardButton(text="➡️ Keyingi Part", callback_data=f"listening_next:{part}"),
        ],
        [
            InlineKeyboardButton(text="🏠 Asosiy Menyuga", callback_data="listening_back_main")
        ]
    ])
    await message.answer(summary, reply_markup=markup, parse_mode="Markdown")

@router.callback_query(F.data.startswith("listening_retake:"))
async def retake_listening_test(callback: types.CallbackQuery, state: FSMContext):
    question_id = int(callback.data.split(":")[1])
    async with DBContext() as session:
        stmt = select(Question).where(Question.id == question_id)
        res = await session.execute(stmt)
        question = res.scalar_one_or_none()
        if not question:
            await callback.answer("Savol topilmadi.", show_alert=True)
            return
        await callback.message.delete()
        await start_listening_test(callback.message, question, question.part, state)
        await callback.answer()

@router.callback_query(F.data.startswith("listening_next:"))
async def next_listening_part(callback: types.CallbackQuery, state: FSMContext):
    current_part = int(callback.data.split(":")[1])
    next_part = current_part + 1 if current_part < 5 else 1
    
    async with DBContext() as session:
        stmt = select(Question).where(
            Question.section == "listening",
            Question.part == next_part,
            Question.is_mock == False
        )
        res = await session.execute(stmt)
        questions = res.scalars().all()
        if not questions:
            await callback.answer(f"Part {next_part} uchun testlar mavjud emas.", show_alert=True)
            return
        await callback.message.delete()
        await start_listening_test(callback.message, questions[0], next_part, state)
        await callback.answer()
