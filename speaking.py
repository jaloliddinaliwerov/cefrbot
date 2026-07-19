import os
import datetime
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from database import DBContext, SpeakingTask, SpeakingSubmission, User, UserAchievement
from states import SpeakingState

router = Router()

def get_speaking_parts_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="Part 1: Interview", callback_data="speaking_part:1")],
        [InlineKeyboardButton(text="Part 2: Cue Card", callback_data="speaking_part:2")],
        [InlineKeyboardButton(text="Part 3: Discussion", callback_data="speaking_part:3")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="speaking_back_main")]
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

        markup = []
        for task in tasks:
            markup.append([InlineKeyboardButton(
                text=f"{task.title} ({task.level})",
                callback_data=f"speaking_task:{task.id}:{part}"
            )])
        markup.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="speaking_back_parts")])
        
        await callback.message.delete()
        await callback.message.answer(
            f"🗣️ **Speaking - Part {part}**\n\nIshlash uchun topshiriqni tanlang:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=markup),
            parse_mode="Markdown"
        )
        await callback.answer()

@router.callback_query(F.data == "speaking_back_parts")
async def back_to_speaking_parts_cb(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.message.answer(
        "🗣️ **Speaking bo'limi**\n\nIltimos, ishlashni xohlagan qismingizni tanlang:",
        reply_markup=get_speaking_parts_keyboard()
    )

@router.callback_query(F.data.startswith("speaking_task:"))
async def start_speaking_task(callback: types.CallbackQuery, state: FSMContext):
    _, task_id_str, part_str = callback.data.split(":")
    task_id = int(task_id_str)
    part = int(part_str)
    
    async with DBContext() as session:
        stmt = select(SpeakingTask).where(SpeakingTask.id == task_id)
        res = await session.execute(stmt)
        task = res.scalar_one_or_none()
        
        if not task:
            await callback.answer("Topshiriq topilmadi.", show_alert=True)
            return

        await state.set_state(SpeakingState.submitting)
        await state.update_data(task_id=task.id, prompt=task.prompt, part=part, task_title=task.title, task_level=task.level)

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
    task_title = state_data.get("task_title", "Speaking")
    task_level = state_data.get("task_level", "B2")

    loading_msg = await message.answer(
        "📥 **Ovozli xabar qabul qilindi!**\n\n"
        "✍️ Nutqingiz matni tayyorlanmoqda..."
    )

    temp_dir = "temp"
    os.makedirs(temp_dir, exist_ok=True)
    voice_path = os.path.join(temp_dir, f"voice_{message.from_user.id}_{task_id}.ogg")

    transcription = ""
    submission_id = None

    try:
        # Download voice file from Telegram
        file_info = await bot.get_file(message.voice.file_id)
        await bot.download_file(file_info.file_path, voice_path)

        # AI: Only transcribe, do NOT score
        try:
            from ai_service import transcribe_speaking
            transcription = await transcribe_speaking(voice_path, prompt)
        except Exception as e:
            transcription = f"(Transkripsiya xatosi: {e})"

        # Save submission to DB — ungraded
        async with DBContext() as session:
            submission = SpeakingSubmission(
                user_id=message.from_user.id,
                task_id=task_id,
                voice_file_id=message.voice.file_id,
                transcription=transcription,
                feedback_json=None,
                score=None,
                admin_graded=False,
                admin_feedback=None,
                submitted_at=datetime.datetime.utcnow()
            )
            session.add(submission)

            # XP for submitting
            user_stmt = select(User).where(User.id == message.from_user.id)
            user_res = await session.execute(user_stmt)
            user = user_res.scalar_one_or_none()
            if user:
                user.xp += 20  # Submission XP (partial — full XP after graded)

                # Check speaking_pro achievement
                ach_stmt = select(UserAchievement).where(
                    UserAchievement.user_id == user.id,
                    UserAchievement.achievement_id == "speaking_pro"
                )
                ach_res = await session.execute(ach_stmt)
                if not ach_res.scalar_one_or_none():
                    new_ach = UserAchievement(user_id=user.id, achievement_id="speaking_pro")
                    session.add(new_ach)
                    user.xp += 100
                    await message.answer(
                        "🎉 **Yangi Yutuq Ochildi!**\n🏆 Notiq (Speaking bo'limida birinchi topshiriq!) | +100 XP",
                        parse_mode="Markdown"
                    )

            await session.commit()
            submission_id = submission.id

        # Notify user — waiting for admin
        try:
            await loading_msg.delete()
        except Exception:
            pass
        await state.clear()

        await message.answer(
            f"✅ **Speaking topshirig'ingiz qabul qilindi!**\n\n"
            f"📌 **Topshiriq:** {task_title} (Part {part} — {task_level})\n\n"
            f"📝 **Nutqingiz matni (transkripsiya):**\n_{transcription}_\n\n"
            f"⏳ **Admin tez orada ovozingizni eshitib, baho qo'yadi.**\n"
            f"Baho qo'yilganda siz darhol bildirishnoma olasiz! +20 XP qo'shildi.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🗣️ Boshqa topshiriqlar", callback_data="speaking_back_main")]
            ])
        )

        # Notify ALL admins with voice + grading button
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        admin_ids = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip().isdigit()]

        user_name = message.from_user.full_name or "Foydalanuvchi"
        username = f"@{message.from_user.username}" if message.from_user.username else f"ID: {message.from_user.id}"

        admin_caption = (
            f"🎙️ **Yangi Speaking Topshirig'i!**\n\n"
            f"👤 **O'quvchi:** {user_name} ({username})\n"
            f"📌 **Topshiriq:** {task_title} (Part {part} — {task_level})\n\n"
            f"📝 **Topshiriq matni:**\n_{prompt}_\n\n"
            f"📋 **Transkripsiya:**\n_{transcription}_\n\n"
            f"⬇️ Ovozni eshitib, pastdagi tugma orqali baho qo'ying:"
        )

        grade_btn = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"📝 Baho qo'yish (#{submission_id})",
                callback_data=f"admin_grade_speaking:{submission_id}:{message.from_user.id}"
            )]
        ])

        for admin_id in admin_ids:
            try:
                # Send voice directly via file_id (more reliable than forward)
                await bot.send_voice(
                    chat_id=admin_id,
                    voice=message.voice.file_id,
                    caption=admin_caption,
                    parse_mode="Markdown",
                    reply_markup=grade_btn
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to notify admin {admin_id}: {e}")


    except Exception as e:
        try:
            await loading_msg.delete()
        except Exception:
            pass
        await message.answer(f"❌ Ovozli faylni qayta ishlashda xatolik yuz berdi: {e}")
    finally:
        if os.path.exists(voice_path):
            try:
                os.remove(voice_path)
            except Exception:
                pass

# ─── Admin grading flow ───────────────────────────────────────────────

from aiogram.fsm.state import State, StatesGroup

class AdminGradingState(StatesGroup):
    waiting_for_score = State()
    waiting_for_feedback = State()

@router.callback_query(F.data.startswith("admin_grade_speaking:"))
async def admin_start_grading(callback: types.CallbackQuery, state: FSMContext):
    """Admin presses 'Baho qo'yish' button"""
    user_id_str = str(callback.from_user.id)
    admin_ids = os.getenv("ADMIN_IDS", "").split(",")
    if user_id_str not in admin_ids:
        await callback.answer("Siz admin emassiz!", show_alert=True)
        return

    parts = callback.data.split(":")
    submission_id = int(parts[1])
    student_user_id = int(parts[2])

    await state.set_state(AdminGradingState.waiting_for_score)
    await state.update_data(submission_id=submission_id, student_user_id=student_user_id)

    await callback.message.answer(
        f"📝 **Speaking #{submission_id} — Baholash**\n\n"
        f"CEFR Speaking mezonlari asosida umumiy ball kiriting.\n\n"
        f"🎯 **Ball shkalasi (0-100):**\n"
        f"• **90-100** → C2 (Mutaxassis darajasi)\n"
        f"• **76-89** → C1 (Ilg'or)\n"
        f"• **61-75** → B2 (O'rta-ilg'or)\n"
        f"• **46-60** → B1 (O'rta)\n"
        f"• **31-45** → A2 (Boshlang'ich-o'rta)\n"
        f"• **0-30**  → A1 (Boshlang'ich)\n\n"
        f"✏️ **Faqat raqam yuboring (0-100):**",
        parse_mode="Markdown"
    )
    await callback.answer()

@router.message(AdminGradingState.waiting_for_score)
async def admin_receive_score(message: types.Message, state: FSMContext):
    """Admin sends score number"""
    try:
        score = int(message.text.strip())
        if not (0 <= score <= 100):
            await message.answer("❌ Ball 0 dan 100 gacha bo'lishi kerak. Qaytadan yozing:")
            return
    except ValueError:
        await message.answer("❌ Faqat raqam yuboring (masalan: 75). Qaytadan yozing:")
        return

    await state.update_data(score=score)
    await state.set_state(AdminGradingState.waiting_for_feedback)

    # Suggest CEFR level
    if score >= 90:
        level = "C2"
    elif score >= 76:
        level = "C1"
    elif score >= 61:
        level = "B2"
    elif score >= 46:
        level = "B1"
    elif score >= 31:
        level = "A2"
    else:
        level = "A1"

    await message.answer(
        f"✅ **Ball:** {score}/100 → **{level}** darajasi\n\n"
        f"📝 Endi o'quvchi uchun qisqa izoh/tavsiya yozing.\n"
        f"_(Masalan: Grammatika yaxshi, ammo talaffuzga ko'proq e'tibor bering. Faol gapiring!)_",
        parse_mode="Markdown"
    )

@router.message(AdminGradingState.waiting_for_feedback)
async def admin_receive_feedback(message: types.Message, state: FSMContext, bot: Bot):
    """Admin sends feedback text — save and notify student"""
    feedback_text = message.text.strip()
    data = await state.get_data()
    submission_id = data.get("submission_id")
    student_user_id = data.get("student_user_id")
    score = data.get("score")

    # Determine CEFR level from score
    if score >= 90:
        level = "C2"
    elif score >= 76:
        level = "C1"
    elif score >= 61:
        level = "B2"
    elif score >= 46:
        level = "B1"
    elif score >= 31:
        level = "A2"
    else:
        level = "A1"

    try:
        async with DBContext() as session:
            stmt = select(SpeakingSubmission).where(SpeakingSubmission.id == submission_id)
            res = await session.execute(stmt)
            submission = res.scalar_one_or_none()

            if not submission:
                await message.answer("❌ Topshiriq bazada topilmadi.")
                await state.clear()
                return

            submission.score = score
            submission.admin_feedback = feedback_text
            submission.admin_graded = True
            submission.evaluated_at = datetime.datetime.utcnow()
            submission.feedback_json = {"level": level, "score": score, "admin_feedback": feedback_text}

            # Give remaining XP to student (30 more for graded)
            user_stmt = select(User).where(User.id == student_user_id)
            user_res = await session.execute(user_stmt)
            student = user_res.scalar_one_or_none()
            if student:
                student.xp += 30

            await session.commit()

        await state.clear()

        # Confirm to admin
        await message.answer(
            f"✅ **Baho saqlandi!**\n\n"
            f"🆔 Submission: #{submission_id}\n"
            f"🎯 Ball: **{score}/100** ({level})\n"
            f"💬 Izoh: {feedback_text}",
            parse_mode="Markdown"
        )

        # Notify student
        student_msg = (
            f"🎉 **Speaking natijangiz tayyor!**\n\n"
            f"📌 Topshirig'ingiz admin tomonidan baholandi.\n\n"
            f"🎯 **Ball: {score}/100**\n"
            f"📊 **CEFR Darajasi: {level}**\n\n"
            f"💬 **Admin izohi:**\n_{feedback_text}_\n\n"
            f"+30 XP qo'shildi! 🚀"
        )
        try:
            await bot.send_message(
                chat_id=student_user_id,
                text=student_msg,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🗣️ Yana speaking", callback_data="speaking_back_main")]
                ])
            )
        except Exception:
            await message.answer("⚠️ O'quvchiga xabar yuborishda xatolik (u botni bloklagan bo'lishi mumkin).")

    except Exception as e:
        await message.answer(f"❌ Bazaga saqlashda xatolik: {e}")
        await state.clear()

@router.message(SpeakingState.submitting)
async def process_speaking_invalid(message: types.Message):
    await message.answer("⚠️ Iltimos, faqat ovozli xabar (Voice message) yuboring. Matn yoki fayllar qabul qilinmaydi.")
