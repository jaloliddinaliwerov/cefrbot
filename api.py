from fastapi import FastAPI, Depends, HTTPException, Header, status, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from sqlalchemy import select, delete, desc, func
import os

from database import (
    DBContext, User, Question, UserProgress, UserIncorrectQuestion,
    WritingTask, WritingSubmission, SpeakingTask, SpeakingSubmission,
    MockExam, MockPurchase, Achievement, UserAchievement, BotSettings
)
from admin import verify_admin_token

app = FastAPI(title="CEFR Bot Backend API")

# Enable CORS for Vercel and local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify Vercel domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- ADMIN DEPENDENCY -----------------
async def get_current_admin(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing"
        )
    
    token = authorization.replace("Bearer ", "").strip()
    if not verify_admin_token(token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin token"
        )
    return token

# ----------------- PYDANTIC SCHEMAS -----------------
class QuestionCreate(BaseModel):
    section: str
    part: int
    title: str
    text: Optional[str] = None
    audio_url: Optional[str] = None
    questions_json: List[Dict[str, Any]]
    is_mock: Optional[bool] = False
    is_daily: Optional[bool] = False

class WritingTaskCreate(BaseModel):
    title: str
    prompt: str
    level: str
    is_mock: Optional[bool] = False

class SpeakingTaskCreate(BaseModel):
    title: str
    prompt: str
    part: int
    level: str
    is_mock: Optional[bool] = False

class MockExamCreate(BaseModel):
    title: str
    price: int
    questions_ids: List[int]
    writing_ids: List[int]
    speaking_ids: List[int]
    active: Optional[bool] = True

# ----------------- PUBLIC ENDPOINTS -----------------

@app.get("/api/leaderboard")
async def get_leaderboard():
    async with DBContext() as session:
        stmt = select(User).order_by(desc(User.xp)).limit(20)
        res = await session.execute(stmt)
        users = res.scalars().all()
        return [
            {
                "id": u.id,
                "first_name": u.first_name + (" 👑" if getattr(u, "is_premium", False) else ""),
                "username": u.username,
                "xp": u.xp,
                "streak": u.streak,
                "is_premium": getattr(u, "is_premium", False)
            } for u in users
        ]

@app.get("/api/stats/{user_id}")
async def get_user_stats(user_id: int):
    async with DBContext() as session:
        # User details
        u_stmt = select(User).where(User.id == user_id)
        u_res = await session.execute(u_stmt)
        user = u_res.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        # Practice stats
        prog_stmt = select(
            func.count(UserProgress.id),
            func.avg(UserProgress.score * 100.0 / UserProgress.max_score)
        ).where(UserProgress.user_id == user_id)
        prog_res = await session.execute(prog_stmt)
        tests_count, avg_test_score = prog_res.first()
        
        # Writing stats
        w_stmt = select(
            func.count(WritingSubmission.id),
            func.avg(WritingSubmission.score)
        ).where(WritingSubmission.user_id == user_id)
        w_res = await session.execute(w_stmt)
        writing_count, avg_writing_score = w_res.first()
        
        # Speaking stats
        s_stmt = select(
            func.count(SpeakingSubmission.id),
            func.avg(SpeakingSubmission.score)
        ).where(SpeakingSubmission.user_id == user_id)
        s_res = await session.execute(s_stmt)
        speaking_count, avg_speaking_score = s_res.first()
        
        # Incorrect questions bank
        inc_stmt = select(func.count(UserIncorrectQuestion.id)).where(UserIncorrectQuestion.user_id == user_id)
        inc_res = await session.execute(inc_stmt)
        incorrect_count = inc_res.scalar() or 0
        
        # Achievements
        ach_stmt = select(Achievement).join(UserAchievement).where(UserAchievement.user_id == user_id)
        ach_res = await session.execute(ach_stmt)
        achievements = ach_res.scalars().all()

        return {
            "user": {
                "id": user.id,
                "first_name": user.first_name,
                "username": user.username,
                "xp": user.xp,
                "streak": user.streak,
                "joined_at": user.joined_at
            },
            "stats": {
                "tests_completed": tests_count or 0,
                "average_test_score": float(avg_test_score or 0.0),
                "writings_completed": writing_count or 0,
                "average_writing_score": float(avg_writing_score or 0.0),
                "speakings_completed": speaking_count or 0,
                "average_speaking_score": float(avg_speaking_score or 0.0),
                "incorrect_questions_count": incorrect_count
            },
            "achievements": [
                {"id": a.id, "name": a.name, "description": a.description, "xp_reward": a.xp_reward}
                for a in achievements
            ]
        }

@app.get("/api/mock-exams")
async def get_mock_exams():
    async with DBContext() as session:
        stmt = select(MockExam).where(MockExam.active == True)
        res = await session.execute(stmt)
        mocks = res.scalars().all()
        return [
            {
                "id": m.id,
                "title": m.title,
                "price": m.price,
                "questions_count": len(m.questions_ids or []),
                "writing_count": len(m.writing_ids or []),
                "speaking_count": len(m.speaking_ids or [])
            } for m in mocks
        ]

# ----------------- ADMIN ENDPOINTS -----------------

@app.get("/api/admin/questions")
async def admin_get_questions(admin: str = Depends(get_current_admin)):
    async with DBContext() as session:
        stmt = select(Question)
        res = await session.execute(stmt)
        questions = res.scalars().all()
        return questions

@app.post("/api/admin/questions", status_code=201)
async def admin_add_question(q: QuestionCreate, admin: str = Depends(get_current_admin)):
    async with DBContext() as session:
        question = Question(
            section=q.section,
            part=q.part,
            title=q.title,
            text=q.text,
            audio_url=q.audio_url,
            questions_json=q.questions_json,
            is_mock=q.is_mock,
            is_daily=q.is_daily
        )
        session.add(question)
        await session.commit()
        return {"status": "success", "id": question.id}

@app.delete("/api/admin/questions/{q_id}")
async def admin_delete_question(q_id: int, admin: str = Depends(get_current_admin)):
    async with DBContext() as session:
        stmt = delete(Question).where(Question.id == q_id)
        await session.execute(stmt)
        await session.commit()
        return {"status": "success"}

@app.put("/api/admin/questions/{q_id}")
async def admin_update_question(q_id: int, q: QuestionCreate, admin: str = Depends(get_current_admin)):
    async with DBContext() as session:
        stmt = select(Question).where(Question.id == q_id)
        res = await session.execute(stmt)
        question = res.scalar_one_or_none()
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")
        question.section = q.section
        question.part = q.part
        question.title = q.title
        question.text = q.text
        question.audio_url = q.audio_url
        question.questions_json = q.questions_json
        question.is_mock = q.is_mock
        question.is_daily = q.is_daily
        await session.commit()
        return {"status": "success"}

@app.get("/api/admin/writing-tasks")
async def admin_get_writings(admin: str = Depends(get_current_admin)):
    async with DBContext() as session:
        stmt = select(WritingTask)
        res = await session.execute(stmt)
        return res.scalars().all()

@app.post("/api/admin/writing-tasks", status_code=201)
async def admin_add_writing(w: WritingTaskCreate, admin: str = Depends(get_current_admin)):
    async with DBContext() as session:
        task = WritingTask(
            title=w.title,
            prompt=w.prompt,
            level=w.level,
            is_mock=w.is_mock
        )
        session.add(task)
        await session.commit()
        return {"status": "success", "id": task.id}

@app.delete("/api/admin/writing-tasks/{w_id}")
async def admin_delete_writing(w_id: int, admin: str = Depends(get_current_admin)):
    async with DBContext() as session:
        stmt = delete(WritingTask).where(WritingTask.id == w_id)
        await session.execute(stmt)
        await session.commit()
        return {"status": "success"}

@app.put("/api/admin/writing-tasks/{w_id}")
async def admin_update_writing(w_id: int, w: WritingTaskCreate, admin: str = Depends(get_current_admin)):
    async with DBContext() as session:
        stmt = select(WritingTask).where(WritingTask.id == w_id)
        res = await session.execute(stmt)
        task = res.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Writing task not found")
        task.title = w.title
        task.prompt = w.prompt
        task.level = w.level
        task.is_mock = w.is_mock
        await session.commit()
        return {"status": "success"}

@app.get("/api/admin/speaking-tasks")
async def admin_get_speakings(admin: str = Depends(get_current_admin)):
    async with DBContext() as session:
        stmt = select(SpeakingTask)
        res = await session.execute(stmt)
        return res.scalars().all()

@app.post("/api/admin/speaking-tasks", status_code=201)
async def admin_add_speaking(s: SpeakingTaskCreate, admin: str = Depends(get_current_admin)):
    async with DBContext() as session:
        task = SpeakingTask(
            title=s.title,
            prompt=s.prompt,
            part=s.part,
            level=s.level,
            is_mock=s.is_mock
        )
        session.add(task)
        await session.commit()
        return {"status": "success", "id": task.id}

@app.delete("/api/admin/speaking-tasks/{s_id}")
async def admin_delete_speaking(s_id: int, admin: str = Depends(get_current_admin)):
    async with DBContext() as session:
        stmt = delete(SpeakingTask).where(SpeakingTask.id == s_id)
        await session.execute(stmt)
        await session.commit()
        return {"status": "success"}

@app.put("/api/admin/speaking-tasks/{s_id}")
async def admin_update_speaking(s_id: int, s: SpeakingTaskCreate, admin: str = Depends(get_current_admin)):
    async with DBContext() as session:
        stmt = select(SpeakingTask).where(SpeakingTask.id == s_id)
        res = await session.execute(stmt)
        task = res.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Speaking task not found")
        task.title = s.title
        task.prompt = s.prompt
        task.part = s.part
        task.level = s.level
        task.is_mock = s.is_mock
        await session.commit()
        return {"status": "success"}

@app.get("/api/admin/mock-exams")
async def admin_get_mocks(admin: str = Depends(get_current_admin)):
    async with DBContext() as session:
        stmt = select(MockExam)
        res = await session.execute(stmt)
        return res.scalars().all()

@app.post("/api/admin/mock-exams", status_code=201)
async def admin_add_mock(m: MockExamCreate, admin: str = Depends(get_current_admin)):
    async with DBContext() as session:
        mock = MockExam(
            title=m.title,
            price=m.price,
            questions_ids=m.questions_ids,
            writing_ids=m.writing_ids,
            speaking_ids=m.speaking_ids,
            active=m.active
        )
        session.add(mock)
        await session.commit()
        return {"status": "success", "id": mock.id}

@app.delete("/api/admin/mock-exams/{m_id}")
async def admin_delete_mock(m_id: int, admin: str = Depends(get_current_admin)):
    async with DBContext() as session:
        stmt = delete(MockExam).where(MockExam.id == m_id)
        await session.execute(stmt)
        await session.commit()
        return {"status": "success"}

@app.put("/api/admin/mock-exams/{m_id}")
async def admin_update_mock(m_id: int, m: MockExamCreate, admin: str = Depends(get_current_admin)):
    async with DBContext() as session:
        stmt = select(MockExam).where(MockExam.id == m_id)
        res = await session.execute(stmt)
        mock = res.scalar_one_or_none()
        if not mock:
            raise HTTPException(status_code=404, detail="Mock exam not found")
        mock.title = m.title
        mock.price = m.price
        mock.questions_ids = m.questions_ids
        mock.writing_ids = m.writing_ids
        mock.speaking_ids = m.speaking_ids
        mock.active = m.active
        await session.commit()
        return {"status": "success"}

import shutil

# Make sure uploads folder exists
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.post("/api/admin/upload-audio")
async def upload_audio(file: UploadFile = File(...), admin: str = Depends(get_current_admin)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".mp3", ".wav", ".ogg", ".m4a", ".mp4"):
        raise HTTPException(
            status_code=400,
            detail="Faqat audio/video formatidagi fayllarni yuklash mumkin (.mp3, .wav, .ogg, .m4a, .mp4)"
        )
    
    import uuid
    new_filename = f"{uuid.uuid4()}{ext}"
    filepath = os.path.join("uploads", new_filename)
    
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return {"status": "success", "url": f"/uploads/{new_filename}"}

from fastapi.responses import StreamingResponse
from fastapi import Query
import httpx

@app.get("/api/admin/users")
async def admin_get_users(admin: str = Depends(get_current_admin)):
    async with DBContext() as session:
        stmt = select(User).order_by(User.xp.desc())
        res = await session.execute(stmt)
        users = res.scalars().all()
        return [
            {
                "id": u.id,
                "first_name": u.first_name,
                "username": u.username,
                "xp": u.xp,
                "streak": u.streak,
                "is_premium": getattr(u, "is_premium", False)
            } for u in users
        ]

@app.get("/api/admin/speaking-submissions")
async def admin_get_speaking_submissions(admin: str = Depends(get_current_admin)):
    async with DBContext() as session:
        stmt = select(SpeakingSubmission, User, SpeakingTask).join(
            User, SpeakingSubmission.user_id == User.id
        ).join(
            SpeakingTask, SpeakingSubmission.task_id == SpeakingTask.id
        ).order_by(SpeakingSubmission.submitted_at.desc())
        
        res = await session.execute(stmt)
        rows = res.all()
        
        return [
            {
                "id": sub.id,
                "user_name": u.first_name or "Foydalanuvchi",
                "user_username": u.username,
                "task_title": task.title,
                "task_part": task.part,
                "task_level": task.level,
                "voice_file_id": sub.voice_file_id,
                "transcription": sub.transcription,
                "score": sub.score,
                "submitted_at": sub.submitted_at.strftime("%Y-%m-%d %H:%M") if sub.submitted_at else ""
            } for sub, u, task in rows
        ]

@app.get("/api/admin/voice/{file_id}")
async def get_voice_file(file_id: str, token: str = Query(...)):
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        bot_token = os.getenv("BOT_TOKEN")
        file_info_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
        async with httpx.AsyncClient() as client:
            res = await client.get(file_info_url)
            if res.status_code != 200:
                raise HTTPException(status_code=400, detail="Telegram'dan ovozli faylni olishda xatolik")
            file_path = res.json()["result"]["file_path"]
            download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
            
            async def stream_audio():
                async with client.stream("GET", download_url) as stream_res:
                    async for chunk in stream_res.iter_bytes():
                        yield chunk
            return StreamingResponse(stream_audio(), media_type="audio/ogg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─── Settings endpoints ───────────────────────────────────────────────

class SettingUpdate(BaseModel):
    value: str

@app.get("/api/admin/settings")
async def get_settings(admin: str = Depends(get_current_admin)):
    """Get all bot settings (card number, etc.)"""
    async with DBContext() as session:
        res = await session.execute(select(BotSettings))
        settings = res.scalars().all()
        return {s.key: s.value for s in settings}

@app.put("/api/admin/settings/{key}")
async def update_setting(key: str, body: SettingUpdate, admin: str = Depends(get_current_admin)):
    """Create or update a setting by key."""
    async with DBContext() as session:
        res = await session.execute(select(BotSettings).where(BotSettings.key == key))
        setting = res.scalar_one_or_none()
        if setting:
            setting.value = body.value
        else:
            setting = BotSettings(key=key, value=body.value)
            session.add(setting)
        await session.commit()
    return {"status": "success", "key": key, "value": body.value}

# ─── Pending payments endpoints ───────────────────────────────────────

@app.get("/api/admin/pending-payments")
async def get_pending_payments(admin: str = Depends(get_current_admin)):
    """Get all pending mock exam purchases."""
    async with DBContext() as session:
        stmt = select(MockPurchase, User, MockExam).join(
            User, MockPurchase.user_id == User.id
        ).join(
            MockExam, MockPurchase.mock_id == MockExam.id
        ).where(MockPurchase.status == "pending").order_by(MockPurchase.purchased_at.desc())
        res = await session.execute(stmt)
        rows = res.all()
        return [
            {
                "id": p.id,
                "user_id": p.user_id,
                "user_name": u.first_name or "Foydalanuvchi",
                "user_username": u.username,
                "mock_title": m.title,
                "mock_price": m.price,
                "screenshot_file_id": p.screenshot_file_id,
                "purchased_at": p.purchased_at.strftime("%Y-%m-%d %H:%M") if p.purchased_at else ""
            } for p, u, m in rows
        ]

@app.post("/api/admin/approve-purchase/{purchase_id}/{user_id}")
async def approve_purchase(purchase_id: int, user_id: int, admin: str = Depends(get_current_admin)):
    """Approve a pending mock purchase and notify user via Telegram."""
    import httpx
    async with DBContext() as session:
        p_stmt = select(MockPurchase).where(MockPurchase.id == purchase_id)
        p_res = await session.execute(p_stmt)
        purchase = p_res.scalar_one_or_none()
        if not purchase:
            raise HTTPException(status_code=404, detail="Purchase not found")
        if purchase.status == "completed":
            return {"status": "already_completed"}

        purchase.status = "completed"
        m_stmt = select(MockExam).where(MockExam.id == purchase.mock_id)
        m_res = await session.execute(m_stmt)
        mock = m_res.scalar_one_or_none()
        await session.commit()

    mock_title = mock.title if mock else "Mock Exam"
    bot_token = os.getenv("BOT_TOKEN", "")
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    "chat_id": user_id,
                    "text": f"🎉 *To'lovingiz tasdiqlandi!*\n\n🎓 *{mock_title}* mockiga kirish ruxsati berildi.\nEndi Mock Exam bo'limidan boshlashingiz mumkin! 🚀",
                    "parse_mode": "Markdown"
                }
            )
    except Exception:
        pass
    return {"status": "approved"}

@app.post("/api/admin/reject-purchase/{purchase_id}/{user_id}")
async def reject_purchase(purchase_id: int, user_id: int, admin: str = Depends(get_current_admin)):
    """Reject a pending mock purchase and notify user via Telegram."""
    import httpx
    async with DBContext() as session:
        p_stmt = select(MockPurchase).where(MockPurchase.id == purchase_id)
        p_res = await session.execute(p_stmt)
        purchase = p_res.scalar_one_or_none()
        if not purchase:
            raise HTTPException(status_code=404, detail="Purchase not found")

        purchase.status = "rejected"
        purchase.reject_reason = "Admin tomonidan rad etildi"
        await session.commit()

    bot_token = os.getenv("BOT_TOKEN", "")
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    "chat_id": user_id,
                    "text": "❌ *To'lovingiz tasdiqlanmadi.*\n\nSabab: to'lov cheki noto'g'ri yoki miqdor mos kelmadi.\nQaytadan to'g'ri miqdorda o'tkazing va yangi chek yuboring.",
                    "parse_mode": "Markdown"
                }
            )
    except Exception:
        pass
    return {"status": "rejected"}

# Serve frontend static assets if they exist (local testing / simple deployment)
if os.path.exists("frontend"):
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
