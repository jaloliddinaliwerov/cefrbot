from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from database import DBContext, WritingTask, WritingSubmission, User, UserAchievement
from states import WritingState
from ai_service import evaluate_writing

router = Router()

@router.message(F.text == "✍️ Writing")
async def writing_menu(message: types.Message):
    async with DBContext() as session:
        stmt = select(WritingTask).where(WritingTask.is_mock == False)
        res = await session.execute(stmt)
        tasks = res.scalars().all()
        
        if not tasks:
            await message.answer("Hozircha Writing topshiriqlari mavjud emas. Admin panel orqali qo'shing.")
            return

        markup = []
        for task in tasks:
            markup.append([InlineKeyboardButton(
                text=f"{task.title} ({task.level})", 
                callback_data=f"writing_task:{task.id}"
            )])
        markup.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="writing_back_main")])
        
        await message.answer(
            "✍️ **Writing bo'limi**\n\nQuyidagi mavzulardan birini tanlang va insho yozishni boshlang:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=markup)
        )

@router.callback_query(F.data == "writing_back_main")
async def back_to_main_menu_cb(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("Asosiy menyudasiz.", reply_markup=types.ReplyKeyboardRemove())
    from common import get_main_keyboard
    await callback.message.answer("Darslarni tanlang:", reply_markup=get_main_keyboard())

@router.callback_query(F.data.startswith("writing_task:"))
async def select_writing_task(callback: types.CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split(":")[1])
    
    async with DBContext() as session:
        stmt = select(WritingTask).where(WritingTask.id == task_id)
        res = await session.execute(stmt)
        task = res.scalar_one_or_none()
        
        if not task:
            await callback.answer("Topshiriq topilmadi.", show_alert=True)
            return

        await state.set_state(WritingState.submitting)
        await state.update_data(task_id=task.id, prompt=task.prompt)

        await callback.message.delete()
        task_text = (
            f"✍️ **Writing Task ({task.level})**\n\n"
            f"📌 **{task.title}**\n\n"
            f"📝 **Prompt:**\n{task.prompt}\n\n"
            f"⚠️ **Ko'rsatma:**\n"
            f"Inshongizni ushbu chatga oddiy matn ko'rinishida yuboring. "
            f"Kamida 100-150 ta so'z yozishga harakat qiling."
        )
        
        await callback.message.answer(task_text, parse_mode="Markdown")
        await callback.answer()

@router.message(WritingState.submitting, F.text)
async def process_writing_submission(message: types.Message, state: FSMContext):
    state_data = await state.get_data()
    task_id = state_data.get("task_id")
    prompt = state_data.get("prompt")
    essay_text = message.text

    if len(essay_text.split()) < 10:
        await message.answer("⚠️ Insho juda qisqa. Iltimos kamida 10 ta so'zdan iborat matn yuboring.")
        return

    loading_msg = await message.answer("🤖 **Sun'iy intellekt inshongizni tekshirmoqda...**\nIltimos, biroz kuting (10-15 soniya).")

    # Evaluate using AI
    feedback = await evaluate_writing(essay_text, prompt)
    
    # Save to database
    score = feedback.get("score", 0)
    async with DBContext() as session:
        submission = WritingSubmission(
            user_id=message.from_user.id,
            task_id=task_id,
            text=essay_text,
            feedback_json=feedback,
            score=score
        )
        session.add(submission)

        # Update User XP
        user_stmt = select(User).where(User.id == message.from_user.id)
        user_res = await session.execute(user_stmt)
        user = user_res.scalar_one_or_none()
        if user:
            user.xp += 50  # 50 XP for writing task
            
            # Check/unlock writing_pro achievement
            ach_stmt = select(UserAchievement).where(
                UserAchievement.user_id == user.id,
                UserAchievement.achievement_id == "writing_pro"
            )
            ach_res = await session.execute(ach_stmt)
            if not ach_res.scalar_one_or_none():
                new_ach = UserAchievement(user_id=user.id, achievement_id="writing_pro")
                session.add(new_ach)
                user.xp += 100
                await message.answer("🎉 **Yangi Yutuq Ochildi!**\n🏆 Ijodkor (Writing bo'limida birinchi topshiriq!) | +100 XP")

        await session.commit()

    # Format feedback report
    report = f"📊 **Writing Tahlili va Natijasi**:\n\n"
    report += f"📈 **Taxminiy Daraja:** {feedback.get('level', 'B2')}\n"
    report += f"🎯 **Ball (Score):** {score}/100\n\n"
    
    report += "🔍 **Grammatik Xatolar:**\n"
    errors = feedback.get("grammar_errors", [])
    if errors:
        for idx, err in enumerate(errors, 1):
            report += f"{idx}. {err}\n"
    else:
        report += "Tabriklaymiz, jiddiy grammatik xatolar topilmadi! 🎉\n"
        
    report += f"\n📚 **Lug'at boyligi (Vocabulary):**\n{feedback.get('vocab', '')}\n"
    report += f"\n🧱 **Matn tuzilishi (Structure):**\n{feedback.get('structure', '')}\n"
    report += f"\n💡 **Maslahat va Tavsiyalar:**\n{feedback.get('advice', '')}\n"

    # Delete loading message and send report
    await loading_msg.delete()
    await state.clear()
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✍️ Boshqa topshiriqlar", callback_data="writing_back_main")
        ]
    ])
    await message.answer(report, reply_markup=markup, parse_mode="Markdown")
