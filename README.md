# 🎓 CEFR Prep Hub — Telegram Bot & Admin Portal

CEFR Prep Hub — bu foydalanuvchilarning ingliz tili (CEFR) darajasini oshirishga mo'ljallangan, sun'iy intellekt (Gemini AI) yordamida ishlaydigan interaktiv Telegram bot va admin boshqaruv paneli (Web Admin Portal).

---

## 🌟 Asosiy Imkoniyatlar (Features)

### 🤖 Telegram Bot Imkoniyatlari:
1. **📖 Reading Bo'limi**: CEFR formatidagi matnlar va savollar (Part 1-5). Foydalanuvchilar javoblarini tekshirib, o'zlashtirish foizlarini ko'radilar.
2. **🎧 Listening Bo'limi**: Audio fayllarni eshitish va savollarga javob berish. Mahalliy serverga yuklangan yoki tashqi URL audiolarni to'g'ridan-to'g'ri botda tinglash imkoniyati.
3. **✍️ Writing Bo'limi**: Berilgan topshiriq bo'yicha insho yozish. **Gemini AI** inshoni grammatika, so'z boyligi, struktura bo'yicha tahlil qilib, 0-100 ball oralig'ida baholaydi va xatolarni ko'rsatadi.
4. **🗣️ Speaking Bo'limi**: Ovozli xabar (Voice message) yuborish orqali gapirish topshiriqlarini topshirish. **Gemini Multimodal AI** audioni eshitib, transkripsiya qiladi va grammatika, talaffuz, ravonlik mezonlari bo'yicha darhol tahlil beradi.
5. **🔥 Daily Challenge & Streak**: Har kuni muntazam dars qilgan o'quvchilarga ketma-ketlik (Streak) tizimi va bonus XP ballari beriladi.
6. **🎓 Mock Exam**: Foydalanuvchilar jami Reading, Listening, Writing va Speaking bo'limlarini o'z ichiga olgan to'liq Mock imtihonlarni topshirishlari mumkin.
7. **👑 Telegram Premium Integratsiyasi**:
   * Premium o'quvchilar testlarni topshirganda **2 barobar ko'p XP** (XP Boost) to'plashadi.
   * Premium o'quvchilar profilida va Leaderboard (peshqadamlar) jadvalida ismining yonida maxsus premium emoji ko'rsatiladi.

### ⚙️ Web Admin Panel Imkoniyatlari:
* **minimalist iOS dizayn tizimi** asosida yaratilgan yengil va xavfsiz boshqaruv paneli.
* **Testlar yaratuvchisi (Builder)**: Reading matnlari va Listening savollarini visual qo'shish/o'chirish.
* **Audio yuklovchi**: Listening audiolari uchun mahalliy fayllarni (.mp3, .ogg) to'g'ridan-to'g'ri serverga yuklash tizimi.
* **Topshiriqlar boshqaruvi**: Writing va Speaking mavzularini qo'shish.
* **Mock Exam Builder**: Mavjud testlar va topshiriqlarni birlashtirib Mock imtihonlar yaratish.

---

## 🛠 Texnologik Stack

* **Backend / API**: Python 3.11, FastAPI, Uvicorn, SQLAlchemy 2.0 (Asinxron)
* **Telegram Bot**: Aiogram 3.x (Asinxron kutubxona)
* **Ma'lumotlar Bazasi**: PostgreSQL (Railway uchun), SQLite (Mahalliy ishlab chiqish uchun)
* **Frontend**: HTML5, Vanilla CSS, Tailwind CSS (Juda yengil va tezkor, Vercel uchun)
* **AI Xizmati**: Google Gemini 1.5 Flash API (Multimodal audio tahlil va insho tekshirish)

---

## 🔑 Environment Variables (Sozlamalar)

Bot va API to'g'ri ishlashi uchun quyidagi o'zgaruvchilarni tizimga (Railway panelida Variables bo'limiga) kiritish zarur:

```env
BOT_TOKEN=123456789:ABCdefGhIJK...        # Telegram Bot Token (@BotFather)
DATABASE_URL=postgresql://...             # Ommaviy ma'lumotlar bazasi manzili
DATABASE_PRIVATE_URL=postgresql://...     # (Tavsiya etiladi) Railway ichki xavfsiz bazasi manzili
GEMINI_API_KEY=AIzaSy...                  # Google Gemini API Kaliti (Gapirish va yozishni baholash uchun)
ADMIN_IDS=987654321,123456789            # Adminlarning Telegram ID raqamlari (vergul bilan ajratilgan)
SITE_URL=https://sizning-bot.up.railway.app # Railway API/Backend ommaviy manzili
WEB_APP_URL=https://sizning-portal.vercel.app # Vercel-da joylashgan sayt manzili
```

---

## 🚀 O'rnatish va Ishga Tushirish

### Mahalliy kompyuterda ishga tushirish:

1. **Repozitoriyani yuklab oling**:
   ```bash
   git clone <repo-url>
   cd zakas-cefr-bot
   ```

2. **Virtual muhit yarating va faollashtiring**:
   ```bash
   python -m venv .venv
   # Windows uchun:
   .venv\Scripts\activate
   # Linux/macOS uchun:
   source .venv/bin/activate
   ```

3. **Kutubxonalarni o'rnating**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Loyiha fayllarini ishga tushiring**:
   ```bash
   python main.py
   ```
   *Bot va API server mahalliy kompyuterda (port: 8000) bir vaqtning o'zida ishga tushadi. Ma'lumotlar bazasi sifatida avtomatik tarzda `cefr_bot.db` yaratiladi.*

---

## ☁️ Serverga Joylashtirish (Deployment Guide)

### 1. Backend & Bot (Railway):
* Loyihani GitHub-ga yuklang.
* Railway-da yangi loyiha ochib, GitHub repozitoriyasini bog'lang.
* Yuqoridagi **Environment Variables** ro'yxatidagi o'zgaruvchilarni sozlang.
* Railway avtomatik ravishda `Procfile` faylini o'qib, bot va API-ni ishga tushiradi.

### 2. Frontend (Vercel):
* Vercel platformasida yangi loyiha oching va ushbu repozitoriyani tanlang.
* Build sozlamalarida **Root directory**ni loyihaning asosiy papkasi (root) qilib qoldiring.
* Nashr etilgandan (Deploy) so'ng, olingan URL manzilini Railway-dagi `WEB_APP_URL` o'zgaruvchisiga kiritib qo'ying.

---

## 💎 Custom Premium Emoji ID Resolver (Adminlar uchun)

Adminlar bot yuboradigan xabarlardagi emojilarni o'zlarining maxsus premium emojilariga almashtirishlari uchun har bir emojining Telegram ID kodini osongina aniqlay oladilar:
1. Akkauntingiz Telegram ID raqamini `ADMIN_IDS` o'zgaruvchisiga qo'shing.
2. Botga istalgan premium emojini xabar ko'rinishida yuboring.
3. Bot sizga javob tariqasida ushbu emojining **Emoji ID** kodini va uni kodda ishlatish uchun tayyor HTML formatini yuboradi.

---

## 📝 Muallif va Litsenziya

* Ushbu loyiha CEFR o'quvchilari uchun eng mukammal mobil o'quv dasturlaridan biri hisoblanadi.
* Barcha huquqlar himoyalangan.
