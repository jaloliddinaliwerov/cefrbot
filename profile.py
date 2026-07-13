import datetime
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, func, desc
from database import DBContext, User, UserProgress, UserIncorrectQuestion, WritingSubmission, SpeakingSubmission, UserAchievement, Achievement, Question
from states import ReadingState

router = Router()

@router.message(F.text == "👤 Profil & Natijalar")
async def profile_menu(message: types.Message):
    user_id = message.from_user.id
    
    async with DBContext() as session:
        # Fetch user
        stmt = select(User).where(User.id == user_id)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()
        
        if not user:
            await message.answer("Siz ro'yxatdan o'tmagansiz. Iltimos /start buyrug'ini bosing.")
            return
            
        # Stats calculations
        # Reading & Listening Progress
        progress_stmt = select(
            func.count(UserProgress.id),
            func.avg(UserProgress.score * 100.0 / UserProgress.max_score)
        ).where(UserProgress.user_id == user_id)
        prog_res = await session.execute(progress_stmt)
        tests_count, avg_test_score = prog_res.first()
        
        # Writing Progress
        w_stmt = select(
            func.count(WritingSubmission.id),
            func.avg(WritingSubmission.score)
        ).where(WritingSubmission.user_id == user_id)
        w_res = await session.execute(w_stmt)
        writing_count, avg_writing_score = w_res.first()
        
        # Speaking Progress
        s_stmt = select(
            func.count(SpeakingSubmission.id),
            func.avg(SpeakingSubmission.score)
        ).where(SpeakingSubmission.user_id == user_id)
        s_res = await session.execute(s_stmt)
        speaking_count, avg_speaking_score = s_res.first()
        
        # Unlocked achievements
        ach_stmt = select(Achievement).join(UserAchievement).where(UserAchievement.user_id == user_id)
        ach_res = await session.execute(ach_stmt)
        achievements = ach_res.scalars().all()
        
        # Incorrect questions count
        inc_stmt = select(func.count(UserIncorrectQuestion.id)).where(UserIncorrectQuestion.user_id == user_id)
        inc_res = await session.execute(inc_stmt)
        incorrect_count = inc_res.scalar() or 0

    # Format text
    joined_date = user.joined_at.strftime("%Y-%m-%d")
    
    is_premium_user = getattr(user, "is_premium", False)
    premium_badge = ' <tg-emoji emoji-id="7489288727785635936">👑</tg-emoji> (Premium 2x XP)' if is_premium_user else ""
    
    profile_text = (
        f"👤 <b>Foydalanuvchi Profili</b>\n\n"
        f"🏷️ <b>Ism:</b> {user.first_name}{premium_badge}\n"
        f"🔑 <b>Telegram ID:</b> <code>{user.id}</code>\n"
        f"📅 <b>A'zolik sanasi:</b> {joined_date}\n\n"
        f"🔥 <b>Kunlik Streak:</b> {user.streak} kun\n"
        f"⚡️ <b>Jami XP:</b> {user.xp} XP\n\n"
        f"📊 <b>Muvaffaqiyatlar ko'rsatkichi:</b>\n"
        f"• 📖/🎧 Testlar soni: {tests_count or 0} ta (O'rtacha: {float(avg_test_score or 0.0):.1f}%)\n"
        f"• ✍️ Writing topshiriqlar: {writing_count or 0} ta (O'rtacha baho: {float(avg_writing_score or 0.0):.1f}/100)\n"
        f"• 🗣️ Speaking topshiriqlar: {speaking_count or 0} ta (O'rtacha baho: {float(avg_speaking_score or 0.0):.1f}/100)\n\n"
        f"🏆 <b>Yutuqlar ({len(achievements)} ta):</b>\n"
    )
    
    if achievements:
        for ach in achievements:
            profile_text += f"🎖️ <b>{ach.name}</b> - {ach.description}\n"
    else:
        profile_text += "Hozircha yutuqlar yo'q. Testlarni ishlashda davom eting! 💪\n"

    markup = []
    
    # If there are errors, offer to review them
    if incorrect_count > 0:
        markup.append([InlineKeyboardButton(
            text=f"❌ Xatolarni qayta ishlash ({incorrect_count})", 
            callback_data="profile_retake_incorrect"
        )])
        
    markup.append([
        InlineKeyboardButton(text="🔄 Yangilash", callback_data="profile_refresh"),
        InlineKeyboardButton(text="🏠 Menu", callback_data="reading_back_main")
    ])
    
    await message.answer(profile_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=markup), parse_mode="HTML")

@router.callback_query(F.data == "profile_refresh")
async def refresh_profile(callback: types.CallbackQuery):
    await callback.message.delete()
    await profile_menu(callback.message)
    await callback.answer()

@router.message(F.text == "🏆 Leaderboard")
async def leaderboard_menu(message: types.Message):
    async with DBContext() as session:
        # Get top 10 users by XP
        stmt = select(User).order_by(desc(User.xp)).limit(10)
        res = await session.execute(stmt)
        top_users = res.scalars().all()
        
        # Get current user rank
        user_id = message.from_user.id
        rank_stmt = select(func.count(User.id)).where(User.xp > select(User.xp).where(User.id == user_id).scalar_subquery())
        rank_res = await session.execute(rank_stmt)
        user_rank = (rank_res.scalar() or 0) + 1

    leaderboard_text = "🏆 <b>CEFR Peshqadamlar Jadvali (Top 10)</b>\n\n"
    
    medal_emojis = {1: "🥇", 2: "🥈", 3: "🥉"}
    
    for idx, user in enumerate(top_users, 1):
        medal = medal_emojis.get(idx, f" {idx}. ")
        name = user.first_name or "Foydalanuvchi"
        if getattr(user, "is_premium", False):
            name += ' <tg-emoji emoji-id="7489288727785635936">👑</tg-emoji>'
        leaderboard_text += f"{medal} <b>{name}</b> - {user.xp} XP (Streak: {user.streak}🔥)\n"
        
    leaderboard_text += f"\n\n👤 <b>Sizning o'rningiz:</b> {user_rank}-o'rin"
    
    await message.answer(leaderboard_text, parse_mode="HTML")

@router.message(F.text == "🔥 Daily Challenge")
async def daily_challenge_menu(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    # We will pick a reading question with ID based on the day of the year
    day_of_year = datetime.datetime.now().timetuple().tm_yday
    
    async with DBContext() as session:
        # Count all questions
        count_stmt = select(func.count(Question.id)).where(Question.is_mock == False)
        res = await session.execute(count_stmt)
        total_questions = res.scalar() or 0
        
        if total_questions == 0:
            await message.answer("⚠️ Hozircha Daily Challenge mavjud emas.")
            return
            
        # Get question index
        target_idx = day_of_year % total_questions
        stmt = select(Question).where(Question.is_mock == False).offset(target_idx).limit(1)
        res = await session.execute(stmt)
        question = res.scalar_one_or_none()
        
        if not question:
            await message.answer("⚠️ Xatolik yuz berdi. Daily Challenge topilmadi.")
            return

        # Check if already completed today
        today_start = datetime.datetime.combine(datetime.date.today(), datetime.time.min)
        done_stmt = select(UserProgress).where(
            UserProgress.user_id == user_id,
            UserProgress.question_id == question.id,
            UserProgress.completed_at >= today_start
        )
        done_res = await session.execute(done_stmt)
        is_done = done_res.scalar_one_or_none()
        
        if is_done:
            await message.answer("🌟 **Siz bugungi Daily Challengeni bajarib bo'ldingiz!**\nYangi topshiriq uchun ertaga qaytib kiring. Rahmat! 😊")
            return

        # Start test as Daily Challenge
        # FSM details
        await state.set_state(ReadingState.answering)
        await state.update_data(question_id=question.id, part=question.part, is_daily=True)

        q_text = f"🔥 **KUNLIK VAZIFA (Daily Challenge)**\n"
        q_text += f"Bugungi vazifa: **Reading - Part {question.part}** (+20 Bonus XP)\n\n"
        q_text += f"📌 **{question.title}**\n\n"
        if question.text:
            q_text += f"{question.text}\n\n"
            
        q_text += "📝 **Savollar:**\n"
        for idx, q_item in enumerate(question.questions_json, 1):
            q_text += f"\n**{idx}. {q_item['q']}**\n"
            for opt in q_item.get('options', []):
                q_text += f"   {opt}\n"
                
        q_text += "\n✍️ Javoblaringizni `1-A, 2-C` ko'rinishida yuboring:"
        
        await message.answer(q_text, parse_mode="Markdown")

@router.callback_query(F.data == "profile_retake_incorrect")
async def retake_incorrect_question(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    async with DBContext() as session:
        # Get the first incorrect question
        stmt = select(UserIncorrectQuestion).where(UserIncorrectQuestion.user_id == user_id).limit(1)
        res = await session.execute(stmt)
        entry = res.scalar_one_or_none()
        
        if not entry:
            await callback.answer("Tabriklaymiz! Sizda hech qanday xato ishlangan savollar qolmagan! 🎉", show_alert=True)
            return
            
        # Get Question details
        q_stmt = select(Question).where(Question.id == entry.question_id)
        q_res = await session.execute(q_stmt)
        question = q_res.scalar_one_or_none()
        
        if not question:
            # Question deleted, clean up entry
            await session.delete(entry)
            await session.commit()
            await callback.answer("Savol ma'lumotlar bazasidan o'chirilgan.", show_alert=True)
            return

        # Prepare retake
        # FSM details
        await state.set_state(ReadingState.answering)
        await state.update_data(question_id=question.id, part=question.part, is_incorrect_retake=True)
        
        await callback.message.delete()
        
        q_text = f"🔄 **Xatolarni Qayta Ishlash**\n"
        q_text += f"Qism: **{question.section.capitalize()} Part {question.part}**\n\n"
        q_text += f"📌 **{question.title}**\n\n"
        if question.text:
            q_text += f"{question.text}\n\n"
            
        q_text += "📝 **Savollar:**\n"
        for idx, q_item in enumerate(question.questions_json, 1):
            # Tell them which they got wrong if available in entry.wrong_answers_json
            is_wrong = str(idx) in entry.wrong_answers_json or idx in entry.wrong_answers_json
            mark = "❌ (Avval xato qilganingiz)" if is_wrong else "✅"
            q_text += f"\n**{idx}. {q_item['q']} {mark}**\n"
            for opt in q_item.get('options', []):
                q_text += f"   {opt}\n"
                
        q_text += "\n✍️ Javoblarni qaytadan yuboring:"
        
        await callback.message.answer(q_text, parse_mode="Markdown")
        await callback.answer()
