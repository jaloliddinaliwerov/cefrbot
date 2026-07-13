import asyncio
import logging
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN
from user_handlers import user_router

logging.basicConfig(level=logging.INFO)

# 1. Bot va Dispatcher yaratamiz
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()
dp.include_router(user_router)

# 2. FastAPI serverini yaratamiz
app = FastAPI()
templates = Jinja2Templates(directory="templates")

# ==================== WEB APP SAHIFALARI ====================

# ==================== WEB APP SAHIFALARI ====================

@app.get("/test/{section}/{part}")
async def serve_test_app(request: Request, section: str, part: str):
    mock_data = {
        "text": "The history of computers dates back to the 1800s...",
        "questions": [
            {"id": 1, "q": "When did computer history begin?", "options": ["1700s", "1800s", "1900s"]},
            {"id": 2, "q": "Who is known as the father of computers?", "options": ["Charles Babbage", "Alan Turing", "Steve Jobs"]}
        ]
    }
    # view="test" degan parametr qoshib yuboramiz
    return templates.TemplateResponse("app.html", {
        "request": request, 
        "view": "test", 
        "section": section, 
        "part": part, 
        "data": mock_data
    })

@app.get("/admin")
async def serve_admin_app(request: Request):
    # view="admin" parametrini beramiz
    return templates.TemplateResponse("app.html", {
        "request": request, 
        "view": "admin"
    })

# ==================== API ENDPOINTLAR ====================

class TestSubmit(BaseModel):
    user_id: int
    section: str
    part: str
    answers: dict

@app.post("/api/submit_test")
async def submit_test(data: TestSubmit):
    # Foydalanuvchidan javoblar keldi. Tekshiramiz:
    correct_answers = {"1": "1800s", "2": "Charles Babbage"}
    score = 0
    
    for q_id, ans in data.answers.items():
        if correct_answers.get(q_id) == ans:
            score += 1
            
    total = len(correct_answers)
    
    # Foydalanuvchiga bot orqali natijani yuboramiz
    result_text = (
        f"📊 <b>Test natijangiz:</b>\n\n"
        f"Bo'lim: {data.section.capitalize()} | {data.part}\n"
        f"To'g'ri javoblar: {score} / {total}\n"
        f"Sizning javoblaringiz: {data.answers}"
    )
    
    try:
        await bot.send_message(chat_id=data.user_id, text=result_text)
    except Exception as e:
        print(f"Xabar yuborishda xatolik: {e}")
        
    return {"status": "success", "score": score}

# ==================== ISHGA TUSHIRISH ====================

@app.on_event("startup")
async def on_startup():
    asyncio.create_task(dp.start_polling(bot))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
