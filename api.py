from fastapi import FastAPI, Depends, HTTPException, Header, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from sqlalchemy import select, delete, desc, func
import os

from database import (
    DBContext, User, Question, UserProgress, UserIncorrectQuestion,
    WritingTask, WritingSubmission, SpeakingTask, SpeakingSubmission,
    MockExam, MockPurchase, Achievement, UserAchievement
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
                "first_name": u.first_name,
                "username": u.username,
                "xp": u.xp,
                "streak": u.streak
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
            is_mock=q.is_mock
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

# Serve frontend static assets if they exist (local testing / simple deployment)
if os.path.exists("frontend"):
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
