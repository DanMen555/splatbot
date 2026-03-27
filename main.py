import sqlite3
import logging
import asyncio
import os
import base64
from openai import AsyncOpenAI
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties

OPENAI_API_KEY = "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"
BOT_TOKEN = "7702030321:AAGCxgvlvCrqI5Z-PxZPOG71pHdWO_kJNqg"

client = AsyncOpenAI(
    api_key=OPENAI_API_KEY,
    base_url="https://openrouter.ai/api/v1" 
)

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

def init_db():
    with sqlite3.connect("eco_bot.db") as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                brushes_count INTEGER DEFAULT 0,
                referred_by INTEGER
            )
        """)
        conn.commit()

def update_brushes(user_id):
    with sqlite3.connect("eco_bot.db") as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET brushes_count = brushes_count + 1 WHERE user_id = ?", (user_id,))
        conn.commit()

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🪥 Добавить щетку")],
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🏆 Рекорды")],
            [KeyboardButton(text="👥 Пригласить друга"), KeyboardButton(text="🆘 Поддержка")]
        ],
        resize_keyboard=True
    )

async def check_image_for_brush(file_path: str) -> bool:
    try:
        with open(file_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')

        response = await client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "На этом фото есть зубная щетка? Ответь только одним словом: ДА или НЕТ."},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        },
                    ],
                }
            ],
            max_tokens=10
        )
        
        answer = response.choices[0].message.content.strip().upper()
        return "ДА" in answer
    except Exception as e:
        logging.error(f"Ошибка ИИ: {e}")
        return False

@dp.message(CommandStart())
async def cmd_start(message: Message):
    args = message.text.split()
    referrer_id = args[1] if len(args) > 1 and args[1].isdigit() else None
    
    with sqlite3.connect("eco_bot.db") as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO users (user_id, username, referred_by) VALUES (?, ?, ?)", 
                    (message.from_user.id, message.from_user.username, referrer_id))
    
    await message.answer(f"Привет, {message.from_user.first_name}! Готов сдавать щетки?", reply_markup=main_menu())

@dp.message(F.text == "🪥 Добавить щетку")
async def ask_photo(message: Message):
    await message.answer("📸 Пришли фото зубной щетки крупным планом.")

@dp.message(F.photo)
async def handle_photo(message: Message):
    status_msg = await message.answer("🔄 Обработка фото нейросетью...")
    
    photo = message.photo[-1]
    file_info = await bot.get_file(photo.file_id)
    temp_path = f"img_{message.from_user.id}.jpg"
    await bot.download_file(file_info.file_path, temp_path)

    is_brush = await check_image_for_brush(temp_path)
    
    if os.path.exists(temp_path):
        os.remove(temp_path)

    if is_brush:
        update_brushes(message.from_user.id)
        await status_msg.edit_text("✅ <b>Принято!</b> Щетка засчитана. Спасибо за вклад в экологию!")
    else:
        await status_msg.edit_text("❌ <b>Хмм...</b> Кажется, это не зубная щетка. Попробуй сделать фото почётче.")

@dp.message(F.text == "📊 Статистика")
async def show_stats(message: Message):
    with sqlite3.connect("eco_bot.db") as conn:
        cur = conn.cursor()
        cur.execute("SELECT brushes_count FROM users WHERE user_id = ?", (message.from_user.id,))
        res = cur.fetchone()
    
    count = res[0] if res else 0
    await message.answer(f"📊 Твои успехи:\n🪥 Сдано щеток: <b>{count}</b>")

@dp.message(F.text == "🏆 Рекорды")
async def show_leaderboard(message: Message):
    with sqlite3.connect("eco_bot.db") as conn:
        cur = conn.cursor()
        cur.execute("SELECT username, brushes_count FROM users ORDER BY brushes_count DESC LIMIT 10")
        leaders = cur.fetchall()
    
    text = "🏆 <b>Топ-10 эко-активистов:</b>\n\n"
    for i, (name, count) in enumerate(leaders, 1):
        display_name = f"@{name}" if name else f"ID:{i*123}"
        text += f"{i}. {display_name} — {count} шт.\n"
    await message.answer(text)

@dp.message(F.text == "👥 Пригласить друга")
async def invite(message: Message):
    bot_user = await bot.get_me()
    link = f"https://t.me/{bot_user.username}?start={message.from_user.id}"
    await message.answer(f"Твоя ссылка для друзей:\n<code>{link}</code>")

@dp.message(F.text == "🆘 Поддержка")
async def support(message: Message):
    await message.answer("🆘 Возникли вопросы? Пиши: @твой_админ")

async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
