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
        reply_markup=get_parts_keyboard()
    )

@router.callback_query(F.data == "reading_back_main")
async def back_to_main_menu_cb(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("Asosiy menyudasiz.", reply_markup=types.ReplyKeyboardRemove())
    # Send start commands to restore ReplyKeyboard
    from common import get_main_keyboard
    await callback.message.answer("Darslarni tanlang:", reply_markup=get_main_keyboard())

@router.callback_query(F.data.startswith("reading_part:"))
async def select_reading_part(callback: types.CallbackQuery, state: FSMContext):
    part = int(callback.data.split(":")[1])
    
    async with DBContext() as session:
        # Find a question for this part
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

        # Choose the first one (or randomly, let's pick first)
        question = questions[0]
        
        await start_reading_test(callback.message, question, part, state)
        await callback.answer()

async def start_reading_test(message: types.Message, question: Question, part: int, state: FSMContext):
    # Set FSM state
    await state.set_state(ReadingState.answering)
    await state.update_data(question_id=question.id, part=part)

    # Format question text
    q_text = f"📖 **Reading - Part {part}**\n\n"
    q_text += f"📌 **{question.title}**\n\n"
    q_text += f"{question.text}\n\n"
    q_text += "📝 **Savollar:**\n"
    
    for idx, q_item in enumerate(question.questions_json, 1):
        q_text += f"\n**{idx}. {q_item['q']}**\n"
        for opt in q_item.get('options', []):
            q_text += f"   {opt}\n"
            
    q_text += (
        "\n✍️ **Javoblaringizni bitta xabar shaklida yuboring.**\n"
        "Masalan: `1-A, 2-C, 3-B` (Harflar kattaligi muhim emas)"
    )
    
    await message.answer(q_text, parse_mode="Markdown")

def parse_user_answers(text: str) -> dict:
    # Pattern to match: 1-A or 1:A or 1.A or 1 A
    pattern = re.compile(r"(\d+)[\s\-:.]*([A-Da-d])")
    matches = pattern.findall(text)
    return {int(q_num): ans.upper() for q_num, ans in matches}

@router.message(ReadingState.answering, F.text)
async def process_reading_answers(message: types.Message, state: FSMContext):
    state_data = await state.get_data()
    question_id = state_data.get("question_id")
    part = state_data.get("part")
    
    user_answers = parse_user_answers(message.text)
    
    if not user_answers:
        await message.answer(
            "⚠️ Javobingiz formati noto'g'ri. Iltimos quyidagi formatda yuboring:\n"
            "Masalan: `1-A, 2-C, 3-B`"
        )
        return

    async with DBContext() as session:
        # Retrieve the question
        stmt = select(Question).where(Question.id == question_id)
        res = await session.execute(stmt)
        question = res.scalar_one_or_none()
        
        if not question:
            await message.answer("Xatolik yuz berdi: Test topilmadi.")
            await state.clear()
            return
            
        questions_list = question.questions_json
        total_questions = len(questions_list)
        
        # Check Answers
        correct_count = 0
        wrong_answers = {}
        result_details = []
        
        for idx, q_item in enumerate(questions_list, 1):
            correct_ans = q_item["answer"].upper().strip()
            # If option has prefixes like "A: Option text", extract "A"
            if len(correct_ans) > 1 and ":" in correct_ans:
                correct_ans = correct_ans.split(":")[0].strip()
                
            user_ans = user_answers.get(idx, "").upper().strip()
            
            if user_ans == correct_ans:
                correct_count += 1
                result_details.append(f"✅ {idx}-savol: To'g'ri")
            else:
                wrong_answers[idx] = user_ans
                result_details.append(f"❌ {idx}-savol: Noto'g'ri (Siz: {user_ans or 'Javob berilmadi'}, To'g'ri: {correct_ans})")

        # Score calculations
        percentage = (correct_count / total_questions) * 100
        is_daily = state_data.get("is_daily", False)
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
            # Check if already in bank
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

            # Perfect score
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
                    await message.answer("🎉 **Yangi Yutuq Ochildi!**\n🏆 A'lochi (Testdan 100% natija!) | +150 XP")

        await session.commit()
        
    # Output results
    res_msg = f"📊 **Test Natijasi**:\n\n"
    res_msg += "\n".join(result_details) + "\n\n"
    if is_daily:
        res_msg += "🌟 **Daily Challenge muvaffaqiyatli topshirildi! (+20 Bonus XP)**\n"
    res_msg += f"📈 **Umumiy natija:** {percentage:.1f}%\n"

    res_msg += f"🎯 **To'g'ri javoblar:** {correct_count}/{total_questions}\n"
    res_msg += f"⚡️ **XP to'plandi:** +{xp_earned} XP\n"
    
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
    
    await state.clear()
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
