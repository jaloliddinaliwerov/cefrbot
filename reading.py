import re
import random
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from database import DBContext, Question, UserProgress, UserIncorrectQuestion, User, UserAchievement, Achievement
from states import ReadingState

router = Router()

def get_parts_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="Part 1", callback_data="reading_part:1"),
            InlineKeyboardButton(text="Part 2", callback_data="reading_part:2"),
        ],
        [
            InlineKeyboardButton(text="Part 3", callback_data="reading_part:3"),
            InlineKeyboardButton(text="Part 4", callback_data="reading_part:4"),
        ],
        [
            InlineKeyboardButton(text="Part 5", callback_data="reading_part:5"),
        ],
        [
            InlineKeyboardButton(text="🔙 Orqaga", callback_data="reading_back_main")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@router.message(F.text == "📖 Reading")
async def reading_menu(message: types.Message):
    await message.answer(
        "📖 **Reading bo'limi**\n\nIltimos, ishlashni xohlagan qismingizni tanlang:",
        reply_markup=get_parts_keyboard(),
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "reading_back_main")
async def back_to_main_menu_cb(callback: types.CallbackQuery):
    await callback.message.delete()
    from common import get_main_keyboard
    await callback.message.answer("Darslarni tanlang:", reply_markup=get_main_keyboard())

@router.callback_query(F.data.startswith("reading_part:"))
async def select_reading_part(callback: types.CallbackQuery, state: FSMContext):
    part = int(callback.data.split(":")[1])
    
    async with DBContext() as session:
        stmt = select(Question).where(
            Question.section == "reading",
            Question.part == part,
            Question.is_mock == False
        )
        res = await session.execute(stmt)
        questions = res.scalars().all()
        
        if not questions:
            await callback.answer("Hozircha bu Part uchun testlar mavjud emas.", show_alert=True)
            return

        markup = []
        for q in questions:
            markup.append([InlineKeyboardButton(
                text=f"{q.title}",
                callback_data=f"reading_test:{q.id}:{part}"
            )])
        markup.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="reading_back_parts")])
        
        await callback.message.delete()
        await callback.message.answer(
            f"📖 **Reading - Part {part}**\n\nIshlash uchun testni tanlang:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=markup),
            parse_mode="Markdown"
        )
        await callback.answer()

@router.callback_query(F.data == "reading_back_parts")
async def back_to_reading_parts_cb(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.message.answer(
        "📖 **Reading bo'limi**\n\nIltimos, ishlashni xohlagan qismingizni tanlang:",
        reply_markup=get_parts_keyboard(),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("reading_test:"))
async def start_reading_test_cb(callback: types.CallbackQuery, state: FSMContext):
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
        await start_reading_test(callback.message, question, part, state)
        await callback.answer()

async def start_reading_test(message: types.Message, question: Question, part: int, state: FSMContext):
    # Set FSM state
    await state.set_state(ReadingState.answering)
    await state.update_data(question_id=question.id, part=part)

    # Check if there is a direct PDF file attached or linked
    pdf_val = getattr(question, "pdf_file_id", None)
    if pdf_val:
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
                except Exception as e:
                    await message.answer(
                        f"⚠️ PDF faylni yuborishda xatolik: {e}\n"
                        "Bot kanalda admin ekanligini tekshiring."
                    )
                    await state.clear()
                    return
            else:
                await message.answer("⚠️ PDF ssilkasi formati noto'g'ri. Admin panelda havolani tekshiring.")
                await state.clear()
                return
        else:
            # Direct file_id
            try:
                await message.answer_document(
                    document=pdf_val,
                    caption=f"📖 *Reading - Part {part}*\n📌 *{question.title}*",
                    parse_mode="Markdown"
                )
            except Exception as e:
                await message.answer(f"⚠️ PDF faylni yuborishda xatolik: {e}")
                await state.clear()
                return

        questions_list = question.questions_json or []
        total = len(questions_list)
        
        q_text = (
            f"📖 *Reading - Part {part}*\n"
            f"📌 *{question.title}*\n\n"
        )
        if total > 0:
            q_text += f"📝 Jami *{total}* ta savol bor.\n\n"
        q_text += (
            "✍️ *Javoblaringizni bitta xabar shaklida yuboring.*\n"
            "Masalan:\n"
            "`1-A, 2-C, 3-B` (harfli javoblar)\n"
            "yoki\n"
            "`1-Apple, 2-Orange, 3-Banana` (matnli javoblar)\n\n"
            "Javobingizni quyida yozib yuboring:"
        )
        await message.answer(q_text, parse_mode="Markdown")
        return

    # No PDF — show text-based question
    questions_list = question.questions_json or []
    if not questions_list:
        await message.answer("⚠️ Bu testda savollar topilmadi. Admin bilan bog'laning.")
        await state.clear()
        return

    q_text = f"📖 *Reading - Part {part}*\n\n"
    q_text += f"📌 *{question.title}*\n\n"
    if question.text:
        q_text += f"{question.text}\n\n"
    q_text += "📝 *Savollar:*\n"
    
    has_options = any(len(q_item.get('options', [])) > 0 for q_item in questions_list)
    
    for idx, q_item in enumerate(questions_list, 1):
        q_text += f"\n*{idx}. {q_item['q']}*\n"
        for opt in q_item.get('options', []):
            q_text += f"   {opt}\n"
            
    if has_options:
        q_text += (
            "\n✍️ *Javoblaringizni bitta xabar shaklida yuboring.*\n"
            "Masalan: `1-A, 2-C, 3-B` (Harflar kattaligi muhim emas)"
        )
    else:
        q_text += (
            "\n✍️ *Javoblaringizni har bir savol tartib raqami bilan yozib yuboring.*\n"
            "Masalan:\n"
            "`1-Apple`\n"
            "`2-Orange`\n"
            "`3-Banana`\n"
            "(Harflar kattaligi va ortiqcha bo'shliqlar hisobga olinmaydi)"
        )
    await message.answer(q_text, parse_mode="Markdown")

def parse_user_answers(text: str) -> dict:
    """
    Parses answer strings like:
      '1-A, 2-B, 3-C'
      '1. A\n2. B\n3. C'
      '1 A 2 B 3 C'
    Returns {1: 'A', 2: 'B', 3: 'C'}
    """
    answers = {}
    text = text.strip()
    
    # Strategy: find all (number, answer) pairs
    # Pattern: digit(s) followed by separator, then answer value until next digit
    pattern = re.compile(
        r'(?:^|(?<=[\n,;]))\s*(\d+)\s*[\-\.:]\s*([A-Za-z][^0-9\n,;]*?|[^\s\n,;]+)',
        re.MULTILINE
    )
    matches = pattern.findall(text)
    
    if matches:
        for q_num_str, ans_val in matches:
            q_num = int(q_num_str)
            ans_clean = ans_val.strip().rstrip('.,;: ')
            if ans_clean:
                answers[q_num] = ans_clean
        return answers
    
    # Fallback: simple split
    simple_pattern = re.compile(r'(\d+)\s*[\-\.:]\s*(\S+)')
    simple_matches = simple_pattern.findall(text)
    for q_num_str, ans_val in simple_matches:
        answers[int(q_num_str)] = ans_val.strip().rstrip('.,;: ')
    
    return answers

@router.message(ReadingState.answering, F.text)
async def process_reading_answers(message: types.Message, state: FSMContext):
    state_data = await state.get_data()
    question_id = state_data.get("question_id")
    part = state_data.get("part")
    is_daily = state_data.get("is_daily", False)
    
    user_answers = parse_user_answers(message.text)
    
    if not user_answers:
        await message.answer(
            "⚠️ Javobingiz formati noto'g'ri. Iltimos quyidagi formatda yuboring:\n"
            "Masalan: `1-A, 2-C, 3-B` yoki\n"
            "`1-Apple, 2-Orange, 3-Banana`",
            parse_mode="Markdown"
        )
        return

    xp_earned = 0
    correct_count = 0
    total_questions = 0
    percentage = 0.0
    result_details = []

    async with DBContext() as session:
        # Retrieve the question
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
        
        # Check Answers
        wrong_answers = {}
        
        for idx, q_item in enumerate(questions_list, 1):
            q_id_num = q_item.get("id", idx)
            correct_ans = str(q_item.get("answer", "")).strip()
            has_opts = len(q_item.get('options', [])) > 0
            
            user_ans = str(user_answers.get(q_id_num) or user_answers.get(idx) or "").strip()
            
            if has_opts:
                # Extract just the letter from "A: Something" format
                c_letter = correct_ans.split(":")[0].strip() if ":" in correct_ans else correct_ans
                u_letter = user_ans.split(":")[0].strip() if ":" in user_ans else user_ans
                is_correct = (u_letter.upper() == c_letter.upper())
                show_correct = c_letter
            else:
                def clean_str(s):
                    return re.sub(r'[^\w\s]', '', s.lower().strip())
                is_correct = (clean_str(user_ans) == clean_str(correct_ans))
                show_correct = correct_ans
                
            if is_correct:
                correct_count += 1
                result_details.append(f"✅ {q_id_num}-savol: To'g'ri")
            else:
                wrong_answers[str(q_id_num)] = user_ans
                result_details.append(
                    f"❌ {q_id_num}-savol: Noto'g'ri "
                    f"(Siz: {user_ans or 'Javob berilmadi'}, To'g'ri: {show_correct})"
                )

        # Score calculations
        percentage = (correct_count / total_questions) * 100
        xp_earned = correct_count * 10
        if is_daily:
            xp_earned += 20  # Bonus XP for Daily Challenge
        
        # Save progress
        progress = UserProgress(
            user_id=message.from_user.id,
            question_id=question_id,
            score=correct_count,
            max_score=total_questions,
            wrong_answers_json=wrong_answers,
        )
        session.add(progress)
        
        # Save to incorrect questions bank if wrong answers exist
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
            # Delete if previously in bank and now 100% correct
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
            
            # Unlock achievements — First test
            ach_stmt = select(UserAchievement).where(
                UserAchievement.user_id == user.id,
                UserAchievement.achievement_id == "first_test"
            )
            ach_res = await session.execute(ach_stmt)
            if not ach_res.scalar_one_or_none():
                new_ach = UserAchievement(user_id=user.id, achievement_id="first_test")
                session.add(new_ach)
                user.xp += 50
                await message.answer("🎉 *Yangi Yutuq Ochildi!*\n🏆 Birinchi Qadam (Birinchi testni topshirdingiz!) | +50 XP", parse_mode="Markdown")

            # Perfect score achievement
            if percentage == 100:
                perf_stmt = select(UserAchievement).where(
                    UserAchievement.user_id == user.id,
                    UserAchievement.achievement_id == "perfect_score"
                )
                perf_res = await session.execute(perf_stmt)
                if not perf_res.scalar_one_or_none():
                    new_ach = UserAchievement(user_id=user.id, achievement_id="perfect_score")
                    session.add(new_ach)
                    user.xp += 150
                    await message.answer("🎉 *Yangi Yutuq Ochildi!*\n🏆 A'lochi (Testdan 100% natija!) | +150 XP", parse_mode="Markdown")

        await session.commit()
        
    # Output results
    await state.clear()

    res_msg = "📊 *Test Natijasi:*\n\n"
    res_msg += "\n".join(result_details) + "\n\n"
    if is_daily:
        res_msg += "🌟 *Daily Challenge muvaffaqiyatli topshirildi! (+20 Bonus XP)*\n"
    res_msg += f"📈 *Umumiy natija:* {percentage:.1f}%\n"
    res_msg += f"🎯 *To'g'ri javoblar:* {correct_count}/{total_questions}\n"
    res_msg += f"⚡️ *XP to'plandi:* +{xp_earned} XP\n"
    
    # Navigation buttons
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Qayta ishlash", callback_data=f"reading_retake:{question_id}"),
            InlineKeyboardButton(text="➡️ Keyingi Part", callback_data=f"reading_next:{part}"),
        ],
        [
            InlineKeyboardButton(text="🏠 Asosiy Menyuga", callback_data="reading_back_main")
        ]
    ])
    
    await message.answer(res_msg, reply_markup=markup, parse_mode="Markdown")

@router.callback_query(F.data.startswith("reading_retake:"))
async def retake_reading_test(callback: types.CallbackQuery, state: FSMContext):
    question_id = int(callback.data.split(":")[1])
    async with DBContext() as session:
        stmt = select(Question).where(Question.id == question_id)
        res = await session.execute(stmt)
        question = res.scalar_one_or_none()
        
        if not question:
            await callback.answer("Savol topilmadi.", show_alert=True)
            return
            
        await callback.message.delete()
        await start_reading_test(callback.message, question, question.part, state)
        await callback.answer()

@router.callback_query(F.data.startswith("reading_next:"))
async def next_reading_part(callback: types.CallbackQuery, state: FSMContext):
    current_part = int(callback.data.split(":")[1])
    next_part = current_part + 1 if current_part < 5 else 1
    
    async with DBContext() as session:
        stmt = select(Question).where(
            Question.section == "reading",
            Question.part == next_part,
            Question.is_mock == False
        )
        res = await session.execute(stmt)
        questions = res.scalars().all()
        
        if not questions:
            await callback.answer(f"Hozircha Part {next_part} uchun testlar mavjud emas.", show_alert=True)
            return
            
        await callback.message.delete()
        await start_reading_test(callback.message, questions[0], next_part, state)
        await callback.answer()
