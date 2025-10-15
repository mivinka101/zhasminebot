# app.py — веб-сервер (FastAPI) + вебхук для aiogram
import json, os
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher
from aiogram.types import Update

# читаем конфиг (из ENV или из файла)
def _cfg():
    env_bot = os.environ.get("BOT_TOKEN")
    env_or  = os.environ.get("OPENROUTER_API_KEY")
    if env_bot and env_or:
        return {"BOT_TOKEN": env_bot, "OPENROUTER_API_KEY": env_or}
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)
CFG = _cfg()

import bot_simple as bot_module  # твой файл с роутером и хендлерами

bot = Bot(token=CFG["BOT_TOKEN"])
dp = Dispatcher()
dp.include_router(bot_module.router)  # ВАЖНО: в bot_simple.py должен быть router

app = FastAPI()

@app.get("/")
async def root():
    return {"ok": True, "msg": "telegram webhook is alive"}

@app.post("/webhook")
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}
