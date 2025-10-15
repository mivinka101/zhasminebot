# app.py — FastAPI вебхук для aiogram v3
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from bot_simple import router, BOT_TOKEN

app = FastAPI(title="zhasminebot")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
dp.include_router(router)

@app.get("/")
async def root():
    return {"ok": True, "service": "zhasminebot"}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    try:
        update = Update.model_validate(data)  # pydantic v2
    except AttributeError:
        update = Update(**data)               # pydantic v1 (fallback)
    await dp.feed_update(bot, update)
    return {"ok": True}
