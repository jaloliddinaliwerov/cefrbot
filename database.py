import os
import json
import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Date, Text, ForeignKey, JSON, select, BigInteger
)
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base, relationship

# Determine Database URL
# For Railway PostgreSQL: DATABASE_URL is usually postgres://...
# We need postgresql+asyncpg://... for async SQLAlchemy
db_url = os.getenv("DATABASE_PRIVATE_URL") or os.getenv("DATABASE_URL")
if db_url:
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    db_url = "sqlite+aiosqlite:///cefr_bot.db"

# Create engine and session maker
connect_args = {}
if db_url.startswith("postgresql"):
    connect_args = {"ssl": False}

engine = create_async_engine(
    db_url,
    connect_args=connect_args,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=1800
)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

Base = declarative_base()

# Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(BigInteger, primary_key=True)  # Telegram ID
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    xp = Column(Integer, default=0)
    streak = Column(Integer, default=0)
    last_active = Column(Date, nullable=True)
    joined_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_premium = Column(Boolean, default=False)

class Question(Base):
    __tablename__ = "questions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    section = Column(String(50))  # 'reading', 'listening'
    part = Column(Integer)  # 1-5
    title = Column(String(200))
    text = Column(Text, nullable=True)  # Reading text
    audio_url = Column(String(500), nullable=True)  # Listening audio link or file_id
    pdf_file_id = Column(String(255), nullable=True)  # Telegram document file_id for direct PDF test papers
    questions_json = Column(JSON)  # List of dicts: [{"id": 1, "q": "Question Text", "options": ["A", "B", "C", "D"], "answer": "A"}]
    is_mock = Column(Boolean, default=False)
    is_daily = Column(Boolean, default=False)

class UserProgress(Base):
    __tablename__ = "user_progress"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"))
    question_id = Column(Integer, ForeignKey("questions.id"))
    score = Column(Integer)
    max_score = Column(Integer)
    wrong_answers_json = Column(JSON, nullable=True)  # Store user incorrect choices
    completed_at = Column(DateTime, default=datetime.datetime.utcnow)

class UserIncorrectQuestion(Base):
    __tablename__ = "user_incorrect_questions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"))
    question_id = Column(Integer, ForeignKey("questions.id"))
    wrong_answers_json = Column(JSON, nullable=True)  # Store wrong answers

class WritingTask(Base):
    __tablename__ = "writing_tasks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200))
    prompt = Column(Text)
    level = Column(String(10))  # 'B1', 'B2', 'C1'
    is_mock = Column(Boolean, default=False)

class WritingSubmission(Base):
    __tablename__ = "writing_submissions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"))
    task_id = Column(Integer, ForeignKey("writing_tasks.id"))
    text = Column(Text)
    feedback_json = Column(JSON)  # {"grammar_errors": [], "vocab": "", "structure": "", "level": "B2", "score": 80, "advice": ""}
    score = Column(Integer)
    evaluated_at = Column(DateTime, default=datetime.datetime.utcnow)

class SpeakingTask(Base):
    __tablename__ = "speaking_tasks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200))
    prompt = Column(Text)
    part = Column(Integer)  # 1-3
    level = Column(String(10))  # 'B1', 'B2', 'C1'
    is_mock = Column(Boolean, default=False)

class SpeakingSubmission(Base):
    __tablename__ = "speaking_submissions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"))
    task_id = Column(Integer, ForeignKey("speaking_tasks.id"))
    voice_file_id = Column(String(255))
    transcription = Column(Text, nullable=True)
    feedback_json = Column(JSON, nullable=True)
    score = Column(Integer, nullable=True)      # Admin tomonidan qo'yiladi
    admin_graded = Column(Boolean, default=False)  # Admin baho qo'ydimi?
    admin_feedback = Column(Text, nullable=True)   # Admin izohi
    submitted_at = Column(DateTime, default=datetime.datetime.utcnow)
    evaluated_at = Column(DateTime, nullable=True)

class MockExam(Base):
    __tablename__ = "mock_exams"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200))
    price = Column(Integer, default=0)  # Price in UZS (or Stars)
    questions_ids = Column(JSON)  # [1, 2, ...] list of reading/listening question IDs
    writing_ids = Column(JSON)  # [1, ...] list of writing task IDs
    speaking_ids = Column(JSON)  # [1, ...] list of speaking task IDs
    active = Column(Boolean, default=True)
    channel_link = Column(String(255), nullable=True)  # Telegram channel for mock test PDF
    pdf_file_id = Column(String(255), nullable=True)   # Telegram document file_id for mock PDF
    answers_json = Column(JSON, nullable=True)         # Mapped correct answers for direct PDF mock test

class MockPurchase(Base):
    __tablename__ = "mock_purchases"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"))
    mock_id = Column(Integer, ForeignKey("mock_exams.id"))
    status = Column(String(50), default="pending")  # 'pending', 'completed', 'rejected'
    screenshot_file_id = Column(String(255), nullable=True)  # User's payment screenshot
    reject_reason = Column(Text, nullable=True)             # Admin rejection reason
    purchased_at = Column(DateTime, default=datetime.datetime.utcnow)

class Achievement(Base):
    __tablename__ = "achievements"
    
    id = Column(String(50), primary_key=True)
    name = Column(String(100))
    description = Column(String(255))
    xp_reward = Column(Integer, default=50)

class UserAchievement(Base):
    __tablename__ = "user_achievements"
    
    user_id = Column(BigInteger, ForeignKey("users.id"), primary_key=True)
    achievement_id = Column(String(50), ForeignKey("achievements.id"), primary_key=True)
    unlocked_at = Column(DateTime, default=datetime.datetime.utcnow)

class BotSettings(Base):
    """Key-value store for bot configuration (card number, etc.)"""
    __tablename__ = "bot_settings"
    
    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=True)

# Database helper functions
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    # Auto-migration: Add is_premium column if it doesn't exist
    async with async_session() as session:
        try:
            from sqlalchemy import text
            await session.execute(text("ALTER TABLE users ADD COLUMN is_premium BOOLEAN DEFAULT FALSE;"))
            await session.commit()
        except Exception:
            await session.rollback()

    # Auto-migrate new speaking_submissions columns
    async with async_session() as session:
        for col_sql in [
            "ALTER TABLE speaking_submissions ADD COLUMN admin_graded BOOLEAN DEFAULT FALSE;",
            "ALTER TABLE speaking_submissions ADD COLUMN admin_feedback TEXT;",
            "ALTER TABLE speaking_submissions ADD COLUMN submitted_at TIMESTAMP;",
        ]:
            try:
                from sqlalchemy import text
                await session.execute(text(col_sql))
                await session.commit()
            except Exception:
                await session.rollback()

    # Auto-migrate new mock_purchases columns
    async with async_session() as session:
        for col_sql in [
            "ALTER TABLE mock_purchases ADD COLUMN screenshot_file_id VARCHAR(255);",
            "ALTER TABLE mock_purchases ADD COLUMN reject_reason TEXT;",
        ]:
            try:
                from sqlalchemy import text
                await session.execute(text(col_sql))
                await session.commit()
            except Exception:
                await session.rollback()

    # Auto-migrate is_daily to questions
    async with async_session() as session:
        try:
            from sqlalchemy import text
            await session.execute(text("ALTER TABLE questions ADD COLUMN is_daily BOOLEAN DEFAULT FALSE;"))
            await session.commit()
        except Exception:
            await session.rollback()

    # Auto-migrate pdf_file_id to questions
    async with async_session() as session:
        try:
            from sqlalchemy import text
            await session.execute(text("ALTER TABLE questions ADD COLUMN pdf_file_id VARCHAR(255);"))
            await session.commit()
        except Exception:
            await session.rollback()

    # Auto-migrate mock_exams columns
    async with async_session() as session:
        for col_sql in [
            "ALTER TABLE mock_exams ADD COLUMN channel_link VARCHAR(255);",
            "ALTER TABLE mock_exams ADD COLUMN pdf_file_id VARCHAR(255);",
            "ALTER TABLE mock_exams ADD COLUMN answers_json JSON;",
        ]:
            try:
                from sqlalchemy import text
                await session.execute(text(col_sql))
                await session.commit()
            except Exception:
                await session.rollback()
            
    # Insert default achievements
    async with async_session() as session:
        default_achievements = [
            Achievement(id="first_test", name="Birinchi Qadam", description="Birinchi testni muvaffaqiyatli topshirdingiz!", xp_reward=50),
            Achievement(id="streak_3", name="Faol O'quvchi", description="3 kunlik ketma-ket dars qilish (Streak)!", xp_reward=100),
            Achievement(id="streak_7", name="Chempion", description="7 kunlik ketma-ket dars qilish (Streak)!", xp_reward=250),
            Achievement(id="perfect_score", name="A'lochi", description="Testdan 100% natija ko'rsatdingiz!", xp_reward=150),
            Achievement(id="mock_master", name="Mock Eksperti", description="Birinchi Mock Imtihonni topshirdingiz!", xp_reward=200),
            Achievement(id="writing_pro", name="Ijodkor", description="Yozish bo'limida birinchi topshiriqni yukladingiz!", xp_reward=100),
            Achievement(id="speaking_pro", name="Notiq", description="Gapirish bo'limida birinchi topshiriqni yukladingiz!", xp_reward=100),
        ]
        try:
            for ach in default_achievements:
                await session.merge(ach)
            await session.commit()
        except Exception as e:
            print("Default achievements insertion failed:", e)

        # Seed questions if empty
        try:
            from sqlalchemy import func
            count_stmt = select(func.count(Question.id))
            res = await session.execute(count_stmt)
            q_count = res.scalar()
            if q_count == 0:
                print("Seeding default CEFR questions...")
                
                # Reading Part 1
                q1 = Question(
                    section="reading",
                    part=1,
                    title="History of Computers",
                    text="Charles Babbage, an English mechanical engineer, originated the concept of a programmable computer. Considered the 'father of the computer', he conceptualized and invented the first mechanical computer in the early 19th century. In 1936, Alan Turing invented the Turing machine, which became the foundation for theories about computation.",
                    questions_json=[
                        {"id": 1, "q": "Who is considered the 'father of the computer'?", "options": ["A: Alan Turing", "B: Charles Babbage", "C: John von Neumann", "D: Bill Gates"], "answer": "B"},
                        {"id": 2, "q": "When did Babbage conceptualize the first mechanical computer?", "options": ["A: Early 18th century", "B: Late 20th century", "C: Early 19th century", "D: 1936"], "answer": "C"},
                        {"id": 3, "q": "What did Alan Turing invent in 1936?", "options": ["A: The mechanical computer", "B: The Analytical Engine", "C: The Turing machine", "D: The internet"], "answer": "C"}
                    ]
                )
                
                # Reading Part 2
                q2 = Question(
                    section="reading",
                    part=2,
                    title="Climate Change & Energy",
                    text="Renewable energy utilization is increasing globally. Solar and wind power are leading this green revolution. In 2023, renewable energy represented over 30% of global electricity generation. However, grid capacity and battery storage technology remain key challenges that must be addressed to replace fossil fuels fully.",
                    questions_json=[
                        {"id": 1, "q": "What percentage of global electricity did renewables represent in 2023?", "options": ["A: Under 10%", "B: Over 30%", "C: Exactly 50%", "D: 100%"], "answer": "B"},
                        {"id": 2, "q": "Which energy sources are leading the green revolution?", "options": ["A: Coal and Oil", "B: Nuclear and Hydro", "C: Solar and Wind", "D: Geothermal and Biofuel"], "answer": "C"},
                        {"id": 3, "q": "What is a major challenge for renewable energy?", "options": ["A: High cost", "B: Lack of sunlight", "C: Grid capacity and battery storage", "D: High air pollution"], "answer": "C"}
                    ]
                )

                # Listening Part 1
                q3 = Question(
                    section="listening",
                    part=1,
                    title="English Language Journey",
                    audio_url="https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
                    text="Eshiting va savollarga javob bering:",
                    questions_json=[
                        {"id": 1, "q": "What does the speaker recommend for improving vocabulary?", "options": ["A: Memorizing dictionaries", "B: Reading contextually", "C: Watching movies with subtitles", "D: Speaking with natives"], "answer": "B"},
                        {"id": 2, "q": "How long should you practice daily according to the speaker?", "options": ["A: 10 minutes", "B: 1 hour", "C: At least 30 minutes", "D: 5 hours"], "answer": "C"}
                    ]
                )

                session.add_all([q1, q2, q3])
                await session.commit()
                
            # Seed Writing Tasks if empty
            count_stmt = select(func.count(WritingTask.id))
            res = await session.execute(count_stmt)
            if res.scalar() == 0:
                print("Seeding default Writing Tasks...")
                w1 = WritingTask(
                    title="AI in Education",
                    prompt="Some people believe that artificial intelligence (AI) will revolutionize education, while others fear it will replace teachers and decrease student interaction. Discuss both views and give your opinion. Write at least 150 words.",
                    level="B2"
                )
                w2 = WritingTask(
                    title="Job Application Letter",
                    prompt="You recently saw an advertisement for a job as an English Language Assistant at a summer camp in London. Write a formal letter of application to the camp manager, explaining why you are suitable for the position. Write 150-200 words.",
                    level="C1"
                )
                session.add_all([w1, w2])
                await session.commit()

            # Seed Speaking Tasks if empty
            count_stmt = select(func.count(SpeakingTask.id))
            res = await session.execute(count_stmt)
            if res.scalar() == 0:
                print("Seeding default Speaking Tasks...")
                s1 = SpeakingTask(
                    title="Hometown Description",
                    prompt="Talk about your hometown. Describe what it looks like, what people do there, and what you like or dislike about living there. Speak for 1-2 minutes.",
                    part=1,
                    level="B1"
                )
                s2 = SpeakingTask(
                    title="Influence of Books",
                    prompt="Describe a book that has had a significant impact on your life. Explain who wrote it, what it is about, and why it influenced you so deeply. Speak for 2 minutes.",
                    part=2,
                    level="B2"
                )
                session.add_all([s1, s2])
                await session.commit()

            # Seed a default Mock Exam if empty
            count_stmt = select(func.count(MockExam.id))
            res = await session.execute(count_stmt)
            if res.scalar() == 0:
                print("Seeding default Mock Exam...")
                # We fetch existing IDs to link
                q_res = await session.execute(select(Question.id))
                q_ids = [row[0] for row in q_res.all()]
                w_res = await session.execute(select(WritingTask.id))
                w_ids = [row[0] for row in w_res.all()]
                s_res = await session.execute(select(SpeakingTask.id))
                s_ids = [row[0] for row in s_res.all()]

                mock1 = MockExam(
                    title="CEFR Mock Exam Standard #1",
                    price=25000, # 25,000 UZS or mock payment
                    questions_ids=q_ids,
                    writing_ids=w_ids,
                    speaking_ids=s_ids,
                    active=True
                )
                session.add(mock1)
                await session.commit()
                
        except Exception as e:
            print("Default content seeding failed:", e)


# DB context manager helper
class DBContext:
    def __init__(self):
        self.session = None

    async def __aenter__(self) -> AsyncSession:
        self.session = async_session()
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
