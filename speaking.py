import os
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from database import DBContext, SpeakingTask, SpeakingSubmission, User, UserAchievement
from states import SpeakingState
from ai_service import evaluate_speaking

router = Router()

def get_speaking_parts_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="Part 1: Interview", callback_data="speaking_part:1"),
        ],
        [
            InlineKeyboardButton(text="Part 2: Cue Card", callback_data="speaking_part:2"),
        ],
        [
            InlineKeyboardButton(text="Part 3: Discussion", callback_data="speaking_part:3"),
        ],
        [
            InlineKeyboardButton(text="🔙 Orqaga", callback_data="speaking_back_main")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@router.message(F.text == "🗣️ Speaking")
async def speaking_menu(message: types.Message):
    await message.answer(
        "🗣️ **Speaking bo'limi**\n\nIltimos, ishlashni xohlagan qismingizni tanlang:",
        reply_markup=get_speaking_parts_keyboard()
    )

@router.callback_query(F.data == "speaking_back_main")
async def back_to_main_menu_cb(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("Asosiy menyudasiz.", reply_markup=types.ReplyKeyboardRemove())
    from common import get_main_keyboard
    await callback.message.answer("Darslarni tanlang:", reply_markup=get_main_keyboard())

@router.callback_query(F.data.startswith("speaking_part:"))
async def select_speaking_part(callback: types.CallbackQuery, state: FSMContext):
    part = int(callback.data.split(":")[1])
    
    async with DBContext() as session:
        stmt = select(SpeakingTask).where(
            SpeakingTask.part == part,
            SpeakingTask.is_mock == False
        )
        res = await session.execute(stmt)
        tasks = res.scalars().all()
        
        if not tasks:
            await callback.answer(f"Hozircha Part {part} uchun speaking topshiriqlari mavjud emas.", show_alert=True)
            return

        task = tasks[0]
        await state.set_state(SpeakingState.submitting)
        await state.update_data(task_id=task.id, prompt=task.prompt, part=part)

        await callback.message.delete()
        task_text = (
            f"🗣️ **Speaking - Part {part} ({task.level})**\n\n"
            f"📌 **{task.title}**\n\n"
            f"📝 **Mavzu / Savol:**\n{task.prompt}\n\n"
            f"🎙️ **Ko'rsatma:**\n"
            f"Ushbu xabarga javoban ovozli xabar (Voice Message) yuboring. "
            f"Kamida 1 daqiqa gapirishga harakat qiling."
        )
        
        await callback.message.answer(task_text, parse_mode="Markdown")
        await callback.answer()

@router.message(SpeakingState.submitting, F.voice)
async def process_speaking_submission(message: types.Message, state: FSMContext, bot: Bot):
    state_data = await state.get_data()
    task_id = state_data.get("task_id")
    prompt = state_data.get("prompt")
    part = state_data.get("part")

    loading_msg = await message.answer("📥 **Ovozli xabar yuklab olinmoqda va tahlil qilinmoqda...**\nBu jarayon 20-30 soniya vaqt olishi mumkin.")

    # Generate a unique path for the voice file
    temp_dir = "temp"
    os.makedirs(temp_dir, exist_ok=True)
    voice_path = os.path.join(temp_dir, f"voice_{message.from_user.id}_{task_id}.ogg")

    try:
        # Download file from Telegram
        file_info = await bot.get_file(message.voice.file_id)
        await bot.download_file(file_info.file_path, voice_path)

        # Call AI Evaluation
        feedback = await evaluate_speaking(voice_path, prompt)

        # Save to DB
        score = feedback.get("score", 0)
        async with DBContext() as session:
            submission = SpeakingSubmission(
                user_id=message.from_user.id,
                task_id=task_id,
                voice_file_id=message.voice.file_id,
                transcription=feedback.get("transcription", ""),
                feedback_json=feedback,
                score=score
            )
            session.add(submission)

            # Update XP
            user_stmt = select(User).where(User.id == message.from_user.id)
            user_res = await session.execute(user_stmt)
            user = user_res.scalar_one_or_none()
            if user:
                user.xp += 50
                
                # Check achievement speaking_pro
                ach_stmt = select(UserAchievement).where(
                    UserAchievement.user_id == user.id,
                    UserAchievement.achievement_id == "speaking_pro"
                )
                ach_res = await session.execute(ach_stmt)
                if not ach_res.scalar_one_or_none():
                    new_ach = UserAchievement(user_id=user.id, achievement_id="speaking_pro")
                    session.add(new_ach)
                    user.xp += 100
                    await message.answer("🎉 **Yangi Yutuq Ochildi!**\n🏆 Notiq (Speaking bo'limida birinchi topshiriq!) | +100 XP")

            await session.commit()

        # Format speaking feedback report
        report = f"🗣️ **Speaking Tahlili va Natijasi**:\n\n"
        report += f"📈 **Taxminiy Daraja:** {feedback.get('level', 'B2')}\n"
        report += f"🎯 **Ball (Score):** {score}/100\n\n"
        
        report += f"📝 **Transkripsiya (Nutqingiz matni):**\n_{feedback.get('transcription', '')}_\n\n"
        report += f"🧱 **Grammatika (Grammar):**\n{feedback.get('grammar', '')}\n\n"
        report += f"📣 **Talaffuz (Pronunciation):**\n{feedback.get('pronunciation', '')}\n\n"
        report += f"⚡️ **Ravonlik (Fluency):**\n{feedback.get('fluency', '')}\n\n"
        report += f"📚 **Lug'at (Vocabulary):**\n{feedback.get('vocab', '')}\n\n"
        report += f"💡 **Tavsiyalar:**\n{feedback.get('advice', '')}\n"

        await loading_msg.delete()
        await state.clear()
        
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🗣️ Boshqa topshiriqlar", callback_data="speaking_back_main")
            ]
        ])
        await message.answer(report, reply_markup=markup, parse_mode="Markdown")

    except Exception as e:
        await loading_msg.delete()
        await message.answer(f"❌ Ovozli faylni tahlil qilishda xatolik yuz berdi: {e}")
    finally:
        # Clean up local file
        if os.path.exists(voice_path):
            try:
                os.remove(voice_path)
            except Exception:
                pass

@router.message(SpeakingState.submitting)
async def process_speaking_invalid(message: types.Message):
    await message.answer("⚠️ Iltimos, faqat ovozli xabar (Voice message) yuboring. Matn yoki fayllar qabul qilinmaydi.")
