import asyncio
import json
import logging
import requests
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder

import game_logic as game  # мини-игра

# ---------------- НАСТРОЙКИ ---------------- #
with open("config.json", "r", encoding="utf-8") as f:
    CFG = json.load(f)

BOT_TOKEN = CFG["BOT_TOKEN"]

# ---------------- БЕСПЛАТНЫЙ ИИ ---------------- #
API_URL = "https://api-inference.huggingface.co/models/google/gemma-2b-it"

def generate(prompt: str, system: str | None = None):
    """Отправка запроса к бесплатной модели HuggingFace"""
    system = system or "Отвечай коротко и по делу, на русском."
    text = f"{system}\n\nВопрос: {prompt}"
    try:
        r = requests.post(API_URL, json={"inputs": text}, timeout=60)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) and "generated_text" in data[0]:
                return data[0]["generated_text"].strip()
            return str(data)
        else:
            return f"Ошибка {r.status_code}: {r.text}"
    except Exception as e:
        return f"Ошибка соединения: {e}"

async def generate_async(prompt: str, system: str | None = None):
    """Асинхронная обёртка, чтобы бот не зависал"""
    return await asyncio.to_thread(generate, prompt, system)

# ---------------- ИНИЦИАЛИЗАЦИЯ БОТА ---------------- #
bot = Bot(BOT_TOKEN)
dp = Dispatcher()
game.init_from_config(CFG)

# ---------------- КЛАВИАТУРА ---------------- #
def main_menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text="🎮 Играть")
    kb.button(text="🤖 ИИ чат")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

# ---------------- КОМАНДЫ ---------------- #
@dp.message(Command("start"))
async def cmd_start(m: Message):
    await m.answer("Привет! 👋 Я твой бот.\nВыбери действие ниже 👇", reply_markup=main_menu())

# ---------------- ОБРАБОТКА СООБЩЕНИЙ ---------------- #
@dp.message()
async def fallback(m: Message):
    text = (m.text or "").lower()

    # 🎮 если пользователь выбрал игру
    if text.startswith("🎮") or text.startswith("игра"):
        await m.answer("🎲 Запускаю игру...")
        await game.process_text_with_game(m)
        return

    # 🤖 если выбрал режим ИИ
    if text.startswith("🤖") or text.startswith("ии") or text.startswith("ai"):
        await m.answer("Пиши вопрос, я подумаю 🤔")
        return

    # иначе — просто общение с ИИ
    await m.answer("⏳ Думаю над ответом...")
    answer = await generate_async(m.text or "", system="Отвечай коротко и по делу, на русском.")
    await m.answer(answer if answer else "Не смог придумать ответ 😅")

# ---------------- ЗАПУСК ---------------- #
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("✅ Бот запущен, можно писать в Telegram!")
    asyncio.run(dp.start_polling(bot))
