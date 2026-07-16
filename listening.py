import re
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from database import DBContext, Question, UserProgress, UserIncorrectQuestion, User, UserAchievement
from states import ListeningState

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
        "🎧 **Listening bo'limi**\n\nIltimos, ishlashni xohlagan qismingizni tanlang:",
        reply_markup=get_listening_parts_keyboard()
    )

@router.callback_query(F.data == "listening_back_main")
async def back_to_main_menu_cb(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("Asosiy menyudasiz.", reply_markup=types.ReplyKeyboardRemove())
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
            f"🎧 **Listening - Part {part}**\n\nIshlash uchun testni tanlang:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=markup),
            parse_mode="Markdown"
        )
        await callback.answer()

@router.callback_query(F.data == "listening_back_parts")
async def back_to_listening_parts_cb(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.message.answer(
        "🎧 **Listening bo'limi**\n\nIltimos, ishlashni xohlagan qismingizni tanlang:",
        reply_markup=get_listening_parts_keyboard()
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
            
        await start_listening_test(callback.message, question, part, state)
        await callback.answer()

async def start_listening_test(message: types.Message, question: Question, part: int, state: FSMContext):
    # Set FSM state
    await state.set_state(ListeningState.answering)
    await state.update_data(question_id=question.id, part=part)

    # Check if there is a direct PDF file attached
    if getattr(question, "pdf_file_id", None):
        await message.answer(f"🎧 **Listening - Part {part}**\n📌 **{question.title}**\n\nAudio yuklanmoqda, iltimos kuting...")
        try:
            if question.audio_url:
                audio_link = question.audio_url
                if audio_link.startswith("/"):
                    import os
                    site_url = os.getenv("SITE_URL", "https://cerfbotweb.vercel.com").strip().rstrip("/")
                    if not site_url.startswith("http"):
                        site_url = f"https://{site_url}"
                    audio_link = f"{site_url}{audio_link}"
                await message.answer_audio(
                    audio=audio_link,
                    caption=f"🎧 Listening Part {part} uchun audio fayl."
                )
        except Exception:
            pass

        await message.answer_document(
            document=question.pdf_file_id,
            caption=f"🎧 **Listening - Part {part}**\n📌 **{question.title}**\n\nSavollar yuqoridagi PDF fayl ichida keltirilgan."
        )
        
        q_text = (
            "✍️ **Javoblaringizni bitta xabar shaklida yuboring.**\n"
            "Masalan:\n"
            "1-A, 2-C, 3-B (yoki matnli javoblar)\n\n"
            "Javobingizni quyida yozib yuboring:"
        )
        await message.answer(q_text, parse_mode="Markdown")
        return

    await message.answer(f"🎧 **Listening - Part {part}**\n📌 **{question.title}**\n\nAudio yuklanmoqda, iltimos kuting...")

    try:
        if question.audio_url:
            audio_link = question.audio_url
            if audio_link.startswith("/"):
                import os
                site_url = os.getenv("SITE_URL", "https://cerfbotweb.vercel.com").strip().rstrip("/")
                if not site_url.startswith("http"):
                    site_url = f"https://{site_url}"
                audio_link = f"{site_url}{audio_link}"
            await message.answer_audio(
                audio=audio_link,
                caption=f"🎧 Listening Part {part} uchun audio fayl."
            )
        else:
            await message.answer("⚠️ Audio fayl topilmadi, quyidagi savollarga matnga asosan javob bering.")
    except Exception as e:
        await message.answer(f"⚠️ Audio faylni yuklashda xatolik yuz berdi. Lekin siz savollarni ishlashingiz mumkin.")

    # Format questions text
    q_text = "📝 **Savollar:**\n"
    has_options = any(len(q_item.get('options', [])) > 0 for q_item in question.questions_json)
    
    for idx, q_item in enumerate(question.questions_json, 1):
        q_text += f"\n**{idx}. {q_item['q']}**\n"
        for opt in q_item.get('options', []):
            q_text += f"   {opt}\n"
            
    if has_options:
        q_text += (
            "\n✍️ **Javoblaringizni bitta xabar shaklida yuboring.**\n"
            "Masalan: `1-A, 2-B` (Harflar kattaligi muhim emas)"
        )
    else:
        q_text += (
            "\n✍️ **Javoblaringizni har bir savol tartib raqami bilan yozib yuboring.**\n"
            "Masalan:\n"
            "1. Apple\n"
            "2. Orange\n"
            "3. Banana\n"
            "(Harflar kattaligi va ortiqcha bo'shliqlar hisobga olinmaydi)"
        )
    
    await message.answer(q_text, parse_mode="Markdown")

def parse_user_answers(text: str) -> dict:
    answers = {}
    parts = re.split(r'(?:^|[\n,;])\s*(\d+)[\s\-:.]+', text.strip())
    
    if len(parts) <= 1:
        pattern = re.compile(r"(\d+)[\s\-:.]*([^\s,;]+)")
        matches = pattern.findall(text)
        return {int(q_num): ans.strip() for q_num, ans in matches}

    i = 1
    while i < len(parts):
        try:
            q_num = int(parts[i])
            ans_val = parts[i+1].strip()
            ans_val = re.sub(r'^[,\s\-:.]+', '', ans_val)
            ans_val = re.sub(r'[,\s\-:.;]+$', '', ans_val)
            answers[q_num] = ans_val
        except (ValueError, IndexError):
            pass
        i += 2
        
    return answers

@router.message(ListeningState.answering, F.text)
async def process_listening_answers(message: types.Message, state: FSMContext):
    state_data = await state.get_data()
    question_id = state_data.get("question_id")
    part = state_data.get("part")
    
    user_answers = parse_user_answers(message.text)
    
    if not user_answers:
        await message.answer(
            "⚠️ Javobingiz formati noto'g'ri. Iltimos quyidagi formatda yuboring:\n"
            "Masalan: `1-A, 2-B` yoki\n"
            "1. Apple\n2. Orange"
        )
        return

    async with DBContext() as session:
        stmt = select(Question).where(Question.id == question_id)
        res = await session.execute(stmt)
        question = res.scalar_one_or_none()
        
        if not question:
            await message.answer("Xatolik yuz berdi: Test topilmadi.")
            await state.clear()
            return
            
        questions_list = question.questions_json
        total_questions = len(questions_list)
        
        correct_count = 0
        wrong_answers = {}
        result_details = []
        
        for idx, q_item in enumerate(questions_list, 1):
            correct_ans = q_item["answer"].strip()
            has_opts = len(q_item.get('options', [])) > 0
            
            user_ans = user_answers.get(idx, "").strip()
            
            if has_opts:
                if len(correct_ans) > 1 and ":" in correct_ans:
                    correct_ans = correct_ans.split(":")[0].strip()
                if len(user_ans) > 1 and ":" in user_ans:
                    user_ans = user_ans.split(":")[0].strip()
                
                is_correct = (user_ans.upper() == correct_ans.upper())
            else:
                def clean_str(s):
                    return re.sub(r'[^\w\s]', '', s.lower().strip())
                is_correct = (clean_str(user_ans) == clean_str(correct_ans))
                
            if is_correct:
                correct_count += 1
                result_details.append(f"✅ {idx}-savol: To'g'ri")
            else:
                wrong_answers[idx] = user_ans
                show_correct = correct_ans.split(":")[0] if has_opts else correct_ans
                result_details.append(f"❌ {idx}-savol: Noto'g'ri (Siz: {user_ans or 'Javob berilmadi'}, To'g'ri: {show_correct})")

        percentage = (correct_count / total_questions) * 100
        xp_earned = correct_count * 10
        
        # Save progress
        progress = UserProgress(
            user_id=message.from_user.id,
            question_id=question_id,
            score=correct_count,
            max_score=total_questions,
            wrong_answers_json=wrong_answers,
        )
        session.add(progress)
        
        # Save to incorrect questions bank
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

        # Update User XP
        user_stmt = select(User).where(User.id == message.from_user.id)
        user_res = await session.execute(user_stmt)
        user = user_res.scalar_one_or_none()
        if user:
            if user.is_premium:
                xp_earned *= 2
            user.xp += xp_earned
            
            # Unlock achievements
            # First test
            ach_stmt = select(UserAchievement).where(
                UserAchievement.user_id == user.id,
                UserAchievement.achievement_id == "first_test"
            )
            ach_res = await session.execute(ach_stmt)
            if not ach_res.scalar_one_or_none():
                new_ach = UserAchievement(user_id=user.id, achievement_id="first_test")
                session.add(new_ach)
                user.xp += 50
                await message.answer("🎉 **Yangi Yutuq Ochildi!**\n🏆 Birinchi Qadam (Birinchi testni topshirdingiz!) | +50 XP")

        await session.commit()
        
    # Output results
    res_msg = f"📊 **Listening Natijasi**:\n\n"
    res_msg += "\n".join(result_details) + "\n\n"
    res_msg += f"📈 **Umumiy natija:** {percentage:.1f}%\n"
    res_msg += f"🎯 **To'g'ri javoblar:** {correct_count}/{total_questions}\n"
    res_msg += f"⚡️ **XP to'plandi:** +{xp_earned} XP\n"
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Qayta ishlash", callback_data=f"listening_retake:{question_id}"),
            InlineKeyboardButton(text="➡️ Keyingi Part", callback_data=f"listening_next:{part}"),
        ],
        [
            InlineKeyboardButton(text="🏠 Asosiy Menyuga", callback_data="listening_back_main")
        ]
    ])
    
    await state.clear()
    await message.answer(res_msg, reply_markup=markup, parse_mode="Markdown")

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
            await callback.answer(f"Hozircha Part {next_part} uchun testlar mavjud emas.", show_alert=True)
            return
            
        await callback.message.delete()
        await start_listening_test(callback.message, questions[0], next_part, state)
        await callback.answer()
