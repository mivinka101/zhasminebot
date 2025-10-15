# bot_simple.py — версия с жёстко прописанным токеном и бесплатным ИИ
import asyncio
import requests
from aiogram import Router, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import game_logic as game

# ====== ТВОЙ ТОКЕН БОТА (как просил) ======
BOT_TOKEN = "8396678240:AAGtZq5LT41xgtB-XGu413TZ7LnWVfyaWVs"

# ====== Роутер (его подключает app.py на Render) ======
router = Router()

# ====== Клавиатуры ======
MAIN_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🤖 ИИ чат"), KeyboardButton(text="🎮 Мини-игра")]],
    resize_keyboard=True
)
BACK_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="⬅️ Главное меню")]],
    resize_keyboard=True
)

# ====== Память режима на пользователя ======
_mode = {}  # user_id -> "ai" | "game"
def set_mode(uid: int, mode: str): _mode[uid] = mode
def get_mode(uid: int) -> str:     return _mode.get(uid, "ai")

# ====== Бесплатный ИИ (без ключей/установок) ======
API_URL = "https://api-inference.huggingface.co/models/google/gemma-2b-it"

def _gen_sync(prompt: str, system: str | None = None) -> str:
    system = system or "Отвечай кратко и по делу, на русском."
    text = f"{system}\n\nВопрос: {prompt}"
    try:
        r = requests.post(API_URL, json={"inputs": text}, timeout=60)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and data and "generated_text" in data[0]:
                return (data[0]["generated_text"] or "").strip()
            return str(data)
        return f"Ошибка {r.status_code}: {r.text}"
    except Exception as e:
        return f"Ошибка соединения: {e}"

async def generate_async(prompt: str, system: str | None = None) -> str:
    return await asyncio.to_thread(_gen_sync, prompt, system)

# ====== Инициализация мини-игры ======
# В твоём game_logic.py функции принимают chat_id/Message и сами шлют ответы через Telegram API.
# Токен передавать не нужно — там уже всё настроено.
game.init_from_config({"BOT_TOKEN": BOT_TOKEN})

# ====== Хэндлеры ======
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
        handled = game.process_text_with_game(m)  # True если мини-игра обработала сообщение
        if not handled:
            await m.answer("Не распознал команду мини-игры. Пример: «профиль», «баланс», «казино 100».")
        return

    # mode == "ai"
    await m.answer("⏳ Думаю над ответом...")
    text = await generate_async(m.text or "", system="Отвечай кратко и по делу, на русском.")
    await m.answer(text if text else "Пустой ответ.")

# ====== Опционально: локальный запуск в режиме polling ======
# На Render это НЕ нужно (там webhook через app.py).
if __name__ == "__main__":
    import logging
    from aiogram import Bot, Dispatcher
    logging.basicConfig(level=logging.INFO)
    async def main():
        bot = Bot(token=BOT_TOKEN)
        dp = Dispatcher()
        dp.include_router(router)
        print("Бот запущен (polling).")
        await dp.start_polling(bot)
    asyncio.run(main())
