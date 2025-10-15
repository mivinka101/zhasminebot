# bot_simple.py — твоя версия: ИИ (HF + фолбэк), нарезка длинных ответов, мини-игра
import asyncio
import os
import requests
from aiogram import Router, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

import game_logic as game

# ====== токен бота (как просил — хардкод) ======
BOT_TOKEN = "8396678240:AAGtZq5LT41xgtB-XGu413TZ7LnWVfyaWVs"

# ====== роутер, его подключает app.py ======
router = Router()

# ====== клавиатуры ======
MAIN_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🤖 ИИ чат"), KeyboardButton(text="🎮 Мини-игра")]],
    resize_keyboard=True
)
BACK_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="⬅️ Главное меню")]],
    resize_keyboard=True
)

# ====== хранение режима пользователя ======
_mode = {}  # user_id -> "ai" | "game"
def set_mode(uid: int, mode: str): _mode[uid] = mode
def get_mode(uid: int) -> str:     return _mode.get(uid, "ai")

# ====== ИИ: HuggingFace c токеном + фолбэк без ключей ======
HF_TOKEN = os.getenv("HF_TOKEN")  # добавь в Render → Environment при желании
HF_URL = "https://api-inference.huggingface.co/models/google/gemma-2b-it"

def _gen_sync(prompt: str, system: str | None = None) -> str:
    system = system or "Отвечай кратко и по делу, на русском."
    text = f"{system}\n\nВопрос: {prompt}"

    # 1) пробуем HuggingFace с токеном
    if HF_TOKEN:
        try:
            r = requests.post(
                HF_URL,
                headers={"Authorization": f"Bearer {HF_TOKEN}"},
                json={"inputs": text},
                timeout=60,
            )
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and data and "generated_text" in data[0]:
                    return (data[0]["generated_text"] or "").strip()
                return str(data)
            # если не 200 — идём в фолбэк
        except Exception:
            pass

    # 2) фолбэк без ключей (Pollinations)
    try:
        r = requests.get("https://text.pollinations.ai/", params={"text": text}, timeout=60)
        if r.status_code == 200:
            return (r.text or "").strip()
        return f"Ошибка {r.status_code}: {r.text}"
    except Exception as e:
        return f"Ошибка соединения: {e}"

async def generate_async(prompt: str, system: str | None = None) -> str:
    return await asyncio.to_thread(_gen_sync, prompt, system)

# ====== инициализация мини-игры ======
# твой game_logic сам шлёт сообщения пользователю; токен ему уже известен
game.init_from_config({"BOT_TOKEN": BOT_TOKEN})

# ====== хэндлеры ======
@router.message(CommandStart())
async def start_cmd(m: types.Message):
    set_mode(m.from_user.id, "ai")
    await m.answer(
        "Привет! Выбери режим ниже:\n\n"
        "• 🤖 ИИ чат — общение с моделью\n"
        "• 🎮 Мини-игра — экономика/казино/ферма\n",
        reply_markup=MAIN_KB
    )

@router.message(F.text == "🤖 ИИ чат")
async def choose_ai(m: types.Message):
    set_mode(m.from_user.id, "ai")
    await m.answer("Режим: 🤖 ИИ чат. Напиши вопрос/сообщение.", reply_markup=BACK_KB)

@router.message(F.text == "🎮 Мини-игра")
async def choose_game(m: types.Message):
    set_mode(m.from_user.id, "game")
    await m.answer(
        "Режим: 🎮 Мини-игра. Пиши команды без слэша (например: «профиль», «баланс», «работа», «казино 100»).",
        reply_markup=BACK_KB
    )
    game.cmd_info(m.chat.id)

@router.message(F.text == "⬅️ Главное меню")
async def back_to_menu(m: types.Message):
    set_mode(m.from_user.id, "ai")
    await m.answer("Главное меню. Выбери режим:", reply_markup=MAIN_KB)

@router.message()
async def fallback(m: types.Message):
    uid = m.from_user.id
    mode = get_mode(uid)

    if mode == "game":
        handled = game.process_text_with_game(m)
        if not handled:
            await m.answer("Не распознал команду мини-игры. Пример: «профиль», «баланс», «казино 100».")
        return

    # режим ИИ
    await m.answer("⏳ Думаю над ответом...")
    text = await generate_async(m.text or "", system="Отвечай кратко и по делу, на русском.")
    text = (text or "").strip()

    # Нарезаем длинные ответы (лимит Telegram ~4096)
    MAX_LEN = 3500
    if not text:
        await m.answer("Пустой ответ.")
    elif len(text) <= MAX_LEN:
        await m.answer(text)
    else:
        for i in range(0, len(text), MAX_LEN):
            await m.answer(text[i:i+MAX_LEN])

# ====== опциональный локальный запуск (polling) — на Render не нужен ======
if __name__ == "__main__":
    from aiogram import Bot, Dispatcher
    import logging
    logging.basicConfig(level=logging.INFO)
    async def main():
        bot = Bot(token=BOT_TOKEN)
        dp = Dispatcher()
        dp.include_router(router)
        print("Бот запущен (polling).")
        await dp.start_polling(bot)
    asyncio.run(main())
