# app.py — FastAPI вебхук для aiogram v3
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher
from aiogram.types import Update

# забираем РОУТЕР и токен из твоего bot_simple.py
from bot_simple import router, BOT_TOKEN

app = FastAPI(title="zhasminebot")

# единые объекты бота и диспетчера
bot = Bot(BOT_TOKEN)
dp = Dispatcher()
dp.include_router(router)

@app.get("/")
async def root():
    return {"ok": True, "service": "zhasminebot"}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    # 1) читаем JSON
    data = await request.json()
    # 2) приводим к aiogram Update (учтём разные версии pydantic)
    try:
        update = Update.model_validate(data)  # pydantic v2 (aiogram>=3.5)
    except AttributeError:
        update = Update(**data)  # pydantic v1 (на всякий случай)
    # 3) отдаём апдейт aiogram
    await dp.feed_update(bot, update)
    return {"ok": True}
