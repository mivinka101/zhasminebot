# game_logic.py
# --- модуль мини-игры / экономики: хранение users.json, роутинг команд, обработчики ---
# твоя логика сохранена, адаптирован ввод/вывод и настройки через init_from_config()

import json, time, random, os, re
from urllib import request, parse

# ========= Глобальные настройки, задаются через init_from_config =========
TOKEN = ""
ADMIN_IDS = set()

START_BALANCE = 50
WORK_MIN, WORK_MAX = 10, 30
WORK_COOLDOWN_SEC = 600

DAILY_MIN, DAILY_MAX = 100, 300_000
DAILY_COOLDOWN_SEC = 24*3600

CASINO_WEIGHTS = [("x50",0.3),("x20",0.7),("x10",1.5),("x5",4.0),("x2",12.0)]

CARS_LIST = [
    ("Audi RS 6", 100_000), ("BMW M3", 135_000), ("Mustang GT 500", 175_000),
    ("Acura NSX", 200_000), ("Ferrari 458 Italia", 320_000), ("Porsche 911", 350_000),
    ("Mercedes AMG GT", 400_000), ("Bugatti Chiron", 700_000), ("Lamborghini Huracan", 750_000),
    ("Lamborghini Urus", 1_000_000), ("Mercedes G-class", 1_250_000)
]
HOUSES_LIST = [
    ("Улица", 5_000), ("Сарай", 50_000), ("Комната в общаге", 100_000),
    ("Квартира", 70_000), ("Дом на рублёвке", 1_000_000),
    ("Вилла в Испании", 1_200_000), ("Moscow City", 1,500,000)
]

BUSINESSES = [
    ("Сервер в Minecraft", 10_000, 400),
    ("Продажа палёных вещей", 20_000, 800),
    ("Ночной клуб", 100_000, 1600),
    ("Магазин электронных сигарет", 120_000, 3700),
    ("Кальянная", 150_000, 4200)
]
BUSINESS_MAX_LEVEL = 5
BUSINESS_UPGRADE_COST = 150_000

def business_multiplier(level:int)->float:
    level = max(1, min(BUSINESS_MAX_LEVEL, level))
    return 1.0 + (2.5 - 1.0) * (level - 1) / (BUSINESS_MAX_LEVEL - 1)

FARMS = {1: {"price": 5_000, "per_min": 27}, 2: {"price": 10_000, "per_min": 60}, 3: {"price": 20_000, "per_min": 150}}
FARM_MAX_TOTAL = 5000

API = ""
USERS_PATH = "users.json"

# ========= Хранилище =========
DEFAULT_USER = {
    "username": "", "nick": None, "nick_enabled": False,
    "balance": START_BALANCE, "bank": 0, "rating": 0,
    "house": None, "car": None,
    "business": None, "farms": {"1":0,"2":0,"3":0},
    "farm_last_ts": int(time.time()), "farm_vault": 0,
    "wins": 0, "losses": 0, "last_work": 0, "last_daily": 0,
    "is_banned": False, "mute_until": 0
}

def init_from_config(cfg: dict):
    global TOKEN, ADMIN_IDS, START_BALANCE, WORK_MIN, WORK_MAX, WORK_COOLDOWN_SEC
    global DAILY_MIN, DAILY_MAX, DAILY_COOLDOWN_SEC, API, DEFAULT_USER

    TOKEN = cfg["BOT_TOKEN"]
    ADMIN_IDS = set(cfg.get("ADMIN_IDS", []))
    START_BALANCE = cfg.get("START_BALANCE", START_BALANCE)
    WORK_MIN = cfg.get("WORK_MIN", WORK_MIN)
    WORK_MAX = cfg.get("WORK_MAX", WORK_MAX)
    WORK_COOLDOWN_SEC = cfg.get("WORK_COOLDOWN_SEC", WORK_COOLDOWN_SEC)
    # daily оставлю дефолтные, при желании тоже можно вынести в config.json

    API = "https://api.telegram.org/bot" + TOKEN + "/"

    DEFAULT_USER = {
        "username": "", "nick": None, "nick_enabled": False,
        "balance": START_BALANCE, "bank": 0, "rating": 0,
        "house": None, "car": None,
        "business": None, "farms": {"1":0,"2":0,"3":0},
        "farm_last_ts": int(time.time()), "farm_vault": 0,
        "wins": 0, "losses": 0, "last_work": 0, "last_daily": 0,
        "is_banned": False, "mute_until": 0
    }

def load_users():
    if not os.path.exists(USERS_PATH):
        return {}
    with open(USERS_PATH, "r", encoding="utf-8") as f:
        txt = f.read().strip()
        if not txt:
            return {}
        return json.loads(txt)

def save_users(data):
    with open(USERS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

users = {}

def patch_defaults(u: dict) -> dict:
    for k, v in DEFAULT_USER.items():
        if k not in u:
            u[k] = json.loads(json.dumps(v))
    u.setdefault("farms", {"1":0,"2":0,"3":0})
    for k in ["1","2","3"]:
        u["farms"].setdefault(k, 0)
    return u

def ensure_user(uid, username=None):
    uid_s = str(uid)
    if uid_s not in users:
        users[uid_s] = patch_defaults({"username": (username or "").lower()})
        save_users(users)
    else:
        u = users[uid_s]
        patch_defaults(u)
        if username:
            uname = (username or "").lower()
            if u.get("username") != uname:
                u["username"] = uname
                save_users(users)
    return users[uid_s]

# ========= Telegram API (прямой HTTP как у тебя) =========
def api_call(method, params=None):
    url = API + method
    data = None; headers = {}
    if params is not None:
        data = json.dumps(params).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = request.Request(url, data=data, headers=headers)
    try:
        with request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print("API call error:", e)
        return None

def send_message(chat_id, text):
    api_call("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML"})

# ========= Утилиты =========
def is_admin(uid): return uid in ADMIN_IDS
def display_name(u):
    if u.get("nick_enabled") and u.get("nick"): return u["nick"]
    return "@"+u["username"] if u.get("username") else "игрок"

def resolve_target_to_id(target:str):
    t = target.strip()
    if t.isdigit() or (t.startswith("-") and t[1:].isdigit()): return int(t)
    if t.startswith("@"):
        name = t[1:].lower()
        for uid_s, data in users.items():
            if data.get("username") == name: return int(uid_s)
    return None

def norm(s: str) -> str:
    s = s.replace("\u200b"," ").replace("\u200c"," ").replace("\xa0"," ")
    return re.sub(r"\s+", " ", s).strip()

def to_int(text: str) -> int:
    m = re.sub(r"[^\d]", "", text or "")
    return int(m) if m.isdigit() else 0

def clamp(n, lo, hi): return max(lo, min(hi, n))

# ========= Начисления =========
def accrue_farm(u):
    now = int(time.time()); last = u.get("farm_last_ts", now)
    minutes = max(0, (now - last)//60)
    if minutes <= 0:
        u["farm_last_ts"] = now
        return
    total = 0
    for tier, cnt in u.get("farms", {}).items():
        c = int(cnt)
        if c <= 0: continue
        total += FARMS[int(tier)]["per_min"] * c * minutes
    u["farm_vault"] = u.get("farm_vault",0) + total
    u["farm_last_ts"] = last + minutes*60

def accrue_business(u):
    if not u.get("business"): return
    now = int(time.time()); b = u["business"]; last = b.get("last_ts", now)
    hours = max(0, (now - last)//3600)
    if hours <= 0: return
    mult = business_multiplier(clamp(b.get("level",1), 1, BUSINESS_MAX_LEVEL))
    income = int(b["base_hr"] * mult * hours)
    b["vault"] = b.get("vault",0) + income
    b["last_ts"] = last + hours*3600

# ========= Команды (коротко оставил твои обработчики) =========
def cmd_info(chat_id):
    send_message(chat_id,
"""<b>🍀 Развлекательные</b>
Переверни [фраза]
Выбери [фраза] или [фраза2]
Реши [пример]

<b>💼 Бизнес</b>
Бизнес
Бизнес статистика
Бизнес снять [сумма]
Бизнес улучшить

<b>🚀 Игры</b>
Казино [сумма]
Трейд [вверх/вниз] [сумма]

<b>💡 Разное</b>
Профиль
Баланс
Банк [сумма/снять сумма/положить сумма]
Рейтинг
Ник [ник/вкл/выкл]
Продать [машина/дом/бизнес]
Ферма
Передать [@ник|id] [сумма]
Топ
Бонус
Репорт [фраза]"""
    )

def handle_start(msg):
    uid = msg['from']['id']
    uname = (msg['from'].get('username') or msg['from'].get('first_name') or "").lower()
    u = ensure_user(uid, uname)
    send_message(msg["chat"]["id"], f"Привет, {display_name(u)}! Добро пожаловать.\nБаланс: {u['balance']}$")

def handle_profile(msg):
    uid = msg['from']['id']; u = ensure_user(uid, msg['from'].get('username'))
    accrue_farm(u); accrue_business(u); save_users(users)
    car = u['car']['name'] if u.get('car') else 'нет'
    house = u['house']['name'] if u.get('house') else 'нет'
    biz = (f"{u['business']['name']} (лвл {u['business']['level']})" if u.get('business') else "нет")
    send_message(msg["chat"]["id"],
        f"<b>Профиль</b>\n"
        f"Игрок: {display_name(u)}\n"
        f"💰 Баланс: {u['balance']}$ | 🏦 Банк: {u['bank']}$ | 👑 Рейтинг: {u.get('rating',0)}\n"
        f"🏠 Дом: {house}\n🚗 Машина: {car}\n🏢 Бизнес: {biz}"
    )

def handle_balance(msg):
    uid = msg['from']['id']; u = ensure_user(uid, msg['from'].get('username'))
    send_message(msg["chat"]["id"], f"💰 Баланс: {u['balance']}$ | 🏦 Банк: {u['bank']}$")

def handle_work(msg):
    uid = msg['from']['id']; u = ensure_user(uid, msg['from'].get('username'))
    if u.get("is_banned"): return
    if u.get("mute_until",0) > time.time(): return
    now = int(time.time()); last = u.get("last_work", 0)
    if now - last < WORK_COOLDOWN_SEC:
        left = WORK_COOLDOWN_SEC - (now - last)
        send_message(msg["chat"]["id"], f"⏳ Ещё {left//60} мин {left%60} сек до работы.")
        return
    reward = random.randint(WORK_MIN, WORK_MAX)
    u["balance"] += reward; u["last_work"] = now; save_users(users)
    send_message(msg["chat"]["id"], f"⚒️ Ты заработал {reward}$! Баланс: {u['balance']}$")

def handle_daily(msg):
    uid = msg['from']['id']; u = ensure_user(uid, msg['from'].get('username'))
    now = int(time.time()); last = u.get("last_daily", 0)
    if now - last < DAILY_COOLDOWN_SEC:
        left = DAILY_COOLDOWN_SEC - (now - last)
        send_message(msg["chat"]["id"], f"⏳ Бонус через {left//3600}ч {(left%3600)//60}м.")
        return
    reward = random.randint(DAILY_MIN, DAILY_MAX)
    u["balance"] += reward; u["last_daily"] = now; save_users(users)
    send_message(msg["chat"]["id"], f"🎁 Ежедневный бонус: +{reward}$! Баланс: {u['balance']}$")

def handle_casino_args(msg, args):
    uid = msg['from']['id']; u = ensure_user(uid, msg['from'].get('username'))
    if not args:
        send_message(msg["chat"]["id"], "Используй: казино [сумма]"); return
    bet = to_int(args[0])
    if bet <= 0:
        send_message(msg["chat"]["id"], "Минимальная ставка 1$."); return
    if u["balance"] < bet:
        send_message(msg["chat"]["id"], "Недостаточно денег!"); return
    roll = random.random()*100.0; acc = 0.0; outcome = "lose"
    for mult, w in CASINO_WEIGHTS:
        acc += w
        if roll <= acc: outcome = mult; break
    if outcome == "lose":
        u["balance"] -= bet
        text = f"🎰 Не повезло! -{bet}$ (осталось {u['balance']}$)"
    else:
        m = int(outcome[1:]); gain = bet*(m-1)
        u["balance"] += gain
        text = f"🎰 Удача! {outcome}! +{gain}$ (теперь {u['balance']}$)"
    save_users(users); send_message(msg["chat"]["id"], text)

def handle_trade_args(msg, args):
    uid = msg['from']['id']; u = ensure_user(uid, msg['from'].get('username'))
    if len(args) < 2:
        send_message(msg["chat"]["id"], "Используй: трейд вверх|вниз [сумма]"); return
    direction = args[0].lower()
    bet = to_int(args[1])
    if bet <= 0:
        send_message(msg["chat"]["id"], "Минимальная сумма 1$."); return
    if u["balance"] < bet:
        send_message(msg["chat"]["id"], "Недостаточно денег!"); return
    actual = random.choice(["вверх","вниз"])
    if direction not in ["вверх","вниз"]:
        send_message(msg["chat"]["id"], "Направление: вверх или вниз."); return
    if direction == actual:
        u["balance"] += bet
        send_message(msg["chat"]["id"], f"📈 Рынок пошёл {actual}! +{bet}$ (теперь {u['balance']}$)")
    else:
        u["balance"] -= bet
        send_message(msg["chat"]["id"], f"📉 Рынок пошёл {actual}. -{bet}$ (осталось {u['balance']}$)")
    save_users(users)

def handle_bank_args(msg, args):
    uid = msg['from']['id']; u = ensure_user(uid, msg['from'].get('username'))
    if not args:
        send_message(msg["chat"]["id"], "Используй: банк [сумма] | банк положить [сумма] | банк снять [сумма]")
        return
    if args[0].lower() in ["положить","снять"]:
        action = args[0].lower()
        if len(args) < 2:
            send_message(msg["chat"]["id"], "Укажи сумму."); return
        amount = to_int(args[1])
    else:
        action = "положить"
        amount = to_int(args[0])

    if amount <= 0:
        send_message(msg["chat"]["id"], "Сумма должна быть > 0."); return

    if action == "положить":
        if u["balance"] < amount:
            send_message(msg["chat"]["id"], "Недостаточно денег в кошельке."); return
        u["balance"] -= amount; u["bank"] += amount
        save_users(users)
        send_message(msg["chat"]["id"], f"🏦 Положено {amount}$. Баланс: {u['balance']}$ | Банк: {u['bank']}$")
    else:
        if u["bank"] < amount:
            send_message(msg["chat"]["id"], "Недостаточно средств в банке."); return
        u["bank"] -= amount; u["balance"] += amount
        save_users(users)
        send_message(msg["chat"]["id"], f"🏦 Снято {amount}$. Баланс: {u['balance']}$ | Банк: {u['bank']}$")

def handle_transfer(msg, parts):
    uid = msg['from']['id']; u = ensure_user(uid, msg['from'].get('username'))
    if len(parts) < 3:
        send_message(msg["chat"]["id"], "Используй: передать @ник|id [сумма]"); return
    to_id = resolve_target_to_id(parts[1])
    if not to_id:
        send_message(msg["chat"]["id"], "Получатель не найден или не писал боту."); return
    amount = to_int(parts[2])
    if amount <= 0 or u["balance"] < amount:
        send_message(msg["chat"]["id"], "Недостаточно средств."); return
    rec = ensure_user(to_id)
    u["balance"] -= amount; rec["balance"] += amount; save_users(users)
    send_message(msg["chat"]["id"], f"🤝 Перевод {amount}$ → {display_name(rec)}. Твой баланс: {u['balance']}$")

def list_cars(chat_id):
    lines = [f"{i+1}) {name} ({price}$)" for i,(name,price) in enumerate(CARS_LIST)]
    send_message(chat_id, "🚗 <b>Машины</b>:\n" + "\n".join(lines) + "\nКупить: машина [номер]")

def buy_car(msg, parts):
    uid = msg['from']['id']; u = ensure_user(uid, msg['from'].get('username'))
    if len(parts) < 2:
        send_message(msg["chat"]["id"], "Используй: машина [номер]"); return
    idx = to_int(parts[1]) - 1
    if not (0 <= idx < len(CARS_LIST)):
        send_message(msg["chat"]["id"], "Нет такой машины."); return
    name, price = CARS_LIST[idx]
    if u["balance"] < price:
        send_message(msg["chat"]["id"], f"Не хватает денег. Цена {price}$, у тебя {u['balance']}$"); return
    u["balance"] -= price; u["car"] = {"name": name, "price": price}; save_users(users)
    send_message(msg["chat"]["id"], f"🚗 Куплен {name} за {price}$. Баланс: {u['balance']}$")

def list_houses(chat_id):
    lines = [f"{i+1}) {name} ({price}$)" for i,(name,price) in enumerate(HOUSES_LIST)]
    send_message(chat_id, "🏠 <b>Дома</b>:\n" + "\n".join(lines) + "\nКупить: дом [номер]")

def buy_house(msg, parts):
    uid = msg['from']['id']; u = ensure_user(uid, msg['from'].get('username'))
    if len(parts) < 2:
        send_message(msg["chat"]["id"], "Используй: дом [номер]"); return
    idx = to_int(parts[1]) - 1
    if not (0 <= idx < len(HOUSES_LIST)):
        send_message(msg["chat"]["id"], "Нет такого дома."); return
    name, price = HOUSES_LIST[idx]
    if u["balance"] < price:
        send_message(msg["chat"]["id"], f"Не хватает денег. Цена {price}$, у тебя {u['balance']}$"); return
    u["balance"] -= price; u["house"] = {"name": name, "price": price}; save_users(users)
    send_message(msg["chat"]["id"], f"🏠 Куплен {name} за {price}$. Баланс: {u['balance']}$")

def handle_sell(msg, parts):
    uid = msg['from']['id']; u = ensure_user(uid, msg['from'].get('username'))
    if len(parts) < 2:
        send_message(msg["chat"]["id"], "Продать что? продать машина|дом|бизнес"); return
    what = parts[1].lower(); refund_rate = 0.7
    if what == "машина" and u.get("car"):
        refund = int(u["car"]["price"]*refund_rate); u["balance"] += refund; u["car"] = None
        save_users(users); send_message(msg["chat"]["id"], f"💸 Продано авто. Возврат {refund}$. Баланс: {u['balance']}$")
    elif what == "дом" and u.get("house"):
        refund = int(u["house"]["price"]*refund_rate); u["balance"] += refund; u["house"] = None
        save_users(users); send_message(msg["chat"]["id"], f"💸 Продан дом. Возврат {refund}$. Баланс: {u['balance']}$")
    elif what == "бизнес" and u.get("business"):
        refund = int(u["business"]["price"]*refund_rate); u["balance"] += refund; u["business"] = None
        save_users(users); send_message(msg["chat"]["id"], f"💸 Продан бизнес. Возврат {refund}$. Баланс: {u['balance']}$")
    else:
        send_message(msg["chat"]["id"], "Нечего продавать или неверный предмет.")

def list_businesses(chat_id):
    lines = [f"{i+1}) {name}: цена {price}$, прибыль {hr}$/час" for i,(name,price,hr) in enumerate(BUSINESSES)]
    send_message(chat_id, "🏢 <b>Бизнесы</b>:\n" + "\n".join(lines) + "\nКупить: бизнес [номер]")

def buy_business(msg, parts):
    uid = msg['from']['id']; u = ensure_user(uid, msg['from'].get('username'))
    if u.get("business"):
        send_message(msg["chat"]["id"], "У тебя уже есть бизнес. Разрешён только один."); return
    if len(parts) < 2:
        send_message(msg["chat"]["id"], "Используй: бизнес [номер]"); return
    idx = to_int(parts[1]) - 1
    if not (0 <= idx < len(BUSINESSES)):
        send_message(msg["chat"]["id"], "Нет такого бизнеса."); return
    name, price, base_hr = BUSINESSES[idx]
    if u["balance"] < price:
        send_message(msg["chat"]["id"], f"Не хватает денег. Цена {price}$, у тебя {u['balance']}$"); return
    u["balance"] -= price
    u["business"] = {"name": name, "price": price, "base_hr": base_hr, "level": 1, "last_ts": int(time.time()), "vault": 0}
    save_users(users)
    send_message(msg["chat"]["id"], f"🏢 Куплен бизнес {name} за {price}$. Баланс: {u['balance']}$")

def business_stats(msg):
    uid = msg['from']['id']; u = ensure_user(uid, msg['from'].get('username'))
    if not u.get("business"):
        send_message(msg["chat"]["id"], "Бизнеса нет."); return
    accrue_business(u); save_users(users)
    b = u["business"]; lvl = b["level"]; mult = business_multiplier(lvl)
    send_message(msg["chat"]["id"],
        f"📊 Бизнес: {b['name']}\n"
        f"Уровень: {lvl} (x{mult:.2f})\n"
        f"База: {b['base_hr']}$/час\n"
        f"Накоплено: {b.get('vault',0)}$\n"
        f"Улучшение: {BUSINESS_UPGRADE_COST}$ (макс {BUSINESS_MAX_LEVEL})"
    )

def business_withdraw_all(msg):
    uid = msg['from']['id']; u = ensure_user(uid, msg['from'].get('username'))
    if not u.get("business"):
        send_message(msg["chat"]["id"], "Бизнеса нет."); return
    accrue_business(u); v = u["business"].get("vault",0)
    if v <= 0:
        send_message(msg["chat"]["id"], "Снимать нечего."); return
    u["business"]["vault"] = 0; u["balance"] += v; save_users(users)
    send_message(msg["chat"]["id"], f"💵 Снято {v}$ из бизнеса. Баланс: {u['balance']}$")

def business_withdraw_amount(msg, amount_text):
    uid = msg['from']['id']; u = ensure_user(uid, msg['from'].get('username'))
    if not u.get("business"):
        send_message(msg["chat"]["id"], "Бизнеса нет."); return
    accrue_business(u)
    want = to_int(amount_text)
    v = u["business"].get("vault",0)
    if want <= 0:
        send_message(msg["chat"]["id"], "Укажи сумму > 0."); return
    if v <= 0:
        send_message(msg["chat"]["id"], "Снимать нечего."); return
    take = min(want, v)
    u["business"]["vault"] = v - take
    u["balance"] += take; save_users(users)
    send_message(msg["chat"]["id"], f"💵 Снято {take}$ (остаток в бизнесе: {u['business']['vault']}$). Баланс: {u['balance']}$")

def business_upgrade(msg):
    uid = msg['from']['id']; u = ensure_user(uid, msg['from'].get('username'))
    if not u.get("business"):
        send_message(msg["chat"]["id"], "Бизнеса нет."); return
    b = u["business"]; lvl = b["level"]
    if lvl >= BUSINESS_MAX_LEVEL:
        send_message(msg["chat"]["id"], "Макс уровень уже достигнут."); return
    cost = BUSINESS_UPGRADE_COST
    if u["balance"] < cost:
        send_message(msg["chat"]["id"], f"Нужно {cost}$, у тебя {u['balance']}$"); return
    u["balance"] -= cost; b["level"] = lvl + 1; save_users(users)
    send_message(msg["chat"]["id"], f"✅ Бизнес улучшен до {b['level']} уровня. Баланс: {u['balance']}$")

def farm_menu(chat_id):
    send_message(chat_id,
        f"💽 <b>Фермы</b>\n"
        f"1) {FARMS[1]['price']}$ /шт — {FARMS[1]['per_min']}$/мин\n"
        f"2) {FARMS[2]['price']}$ /шт — {FARMS[2]['per_min']}$/мин\n"
        f"3) {FARMS[3]['price']}$ /шт — {FARMS[3]['per_min']}$/мин\n"
        f"Максимум суммарно: {FARM_MAX_TOTAL} шт\n"
        f"Команды: ферма купить [1|2|3] [шт], ферма снять, ферма стата"
    )

def farm_buy(msg, parts):
    uid = msg['from']['id']; u = ensure_user(uid, msg['from'].get('username'))
    if len(parts) < 4:
        send_message(msg["chat"]["id"], "Используй: ферма купить [1|2|3] [шт]"); return
    tier = to_int(parts[2]); qty = to_int(parts[3])
    if tier not in FARMS or qty <= 0:
        send_message(msg["chat"]["id"], "Неверные параметры."); return
    total_now = sum(int(u["farms"][k]) for k in ["1","2","3"])
    if total_now + qty > FARM_MAX_TOTAL:
        send_message(msg["chat"]["id"], f"Превышен лимит. Доступно ещё {FARM_MAX_TOTAL - total_now} шт."); return
    price = FARMS[tier]["price"] * qty
    if u["balance"] < price:
        send_message(msg["chat"]["id"], f"Нужно {price}$, у тебя {u['balance']}$"); return
    accrue_farm(u); u["balance"] -= price; u["farms"][str(tier)] += qty; save_users(users)
    send_message(msg["chat"]["id"], f"💽 Куплено {qty} шт фермы {tier} за {price}$. Баланс: {u['balance']}$")

def farm_withdraw(msg):
    uid = msg['from']['id']; u = ensure_user(uid, msg['from'].get('username'))
    accrue_farm(u); v = u.get("farm_vault",0)
    if v <= 0:
        send_message(msg["chat"]["id"], "Снимать нечего."); return
    u["farm_vault"] = 0; u["balance"] += v; save_users(users)
    send_message(msg["chat"]["id"], f"💽 Снято {v}$. Баланс: {u['balance']}$")

def farm_stats(msg):
    uid = msg['from']['id']; u = ensure_user(uid, msg['from'].get('username'))
    accrue_farm(u); save_users(users)
    f1,f2,f3 = u["farms"]["1"], u["farms"]["2"], u["farms"]["3"]
    per_min = f1*FARMS[1]["per_min"] + f2*FARMS[2]["per_min"] + f3*FARMS[3]["per_min"]
    send_message(msg["chat"]["id"], f"💽 Фермы: 1→{f1} шт, 2→{f2} шт, 3→{f3} шт\nДоход: {per_min}$/мин\nНакоплено: {u.get('farm_vault',0)}$")

def handle_nick(msg, parts):
    uid = msg['from']['id']; u = ensure_user(uid, msg['from'].get('username'))
    if len(parts) < 2:
        send_message(msg["chat"]["id"], "Ник: ник [текст] | ник вкл | ник выкл"); return
    sub = parts[1].lower()
    if sub == "вкл":
        u["nick_enabled"]=True; save_users(users); send_message(msg["chat"]["id"], "Ник включён.")
    elif sub == "выкл":
        u["nick_enabled"]=False; save_users(users); send_message(msg["chat"]["id"], "Ник выключен.")
    else:
        new_nick = " ".join(parts[1:])
        if len(new_nick) > 24:
            send_message(msg["chat"]["id"], "Слишком длинный ник (макс 24)."); return
        u["nick"]=new_nick; save_users(users); send_message(msg["chat"]["id"], f"Ник установлен: {new_nick}")

def handle_rating(msg, parts):
    uid = msg['from']['id']; u = ensure_user(uid, msg['from'].get('username'))
    if len(parts)>=2 and parts[1].lower()=="купить":
        qty = 1
        if len(parts)>=3: qty = max(1, to_int(parts[2]))
        cost = 25_000*qty
        if u["balance"]<cost:
            send_message(msg["chat"]["id"], f"Нужно {cost}$, у тебя {u['balance']}$"); return
        u["balance"]-=cost; u["rating"]=u.get("rating",0)+qty; save_users(users)
        send_message(msg["chat"]["id"], f"👑 Куплено {qty}. Баланс: {u['balance']}$ | Рейтинг: {u['rating']}")
    else:
        send_message(msg["chat"]["id"], f"👑 Текущий рейтинг: {u.get('rating',0)}. Купить: рейтинг купить [число]")

def handle_top(msg):
    top = sorted([(u.get("rating",0), display_name(u)) for u in users.values()], reverse=True)[:10]
    lines = [f"{i}. {name} — 👑 {r}" for i,(r,name) in enumerate(top, start=1)]
    send_message(msg["chat"]["id"], "🏆 <b>Топ по рейтингу</b>:\n" + ("\n".join(lines) if lines else "Пусто"))

def handle_reverse(msg, parts, raw_text):
    phrase = raw_text.partition(' ')[2]
    if not phrase:
        send_message(msg["chat"]["id"], "Используй: переверни [фраза]"); return
    send_message(msg["chat"]["id"], phrase[::-1])

def handle_choose(msg, raw_text):
    rest = raw_text.partition(' ')[2]
    if " или " not in rest:
        send_message(msg["chat"]["id"], "Формат: выбери [фраза] или [фраза2]"); return
    a,_,b = rest.partition(" или "); a=a.strip(); b=b.strip()
    if not a or not b:
        send_message(msg["chat"]["id"], "Нужно 2 фразы через «или»."); return
    send_message(msg["chat"]["id"], f"Выбираю: <b>{random.choice([a,b])}</b>")

def handle_solve(msg, raw_text):
    expr = raw_text.partition(' ')[2].strip()
    if not expr:
        send_message(msg["chat"]["id"], "Используй: реши [пример]"); return
    allowed = set("0123456789+-*/(). ")
    if any(ch not in allowed for ch in expr):
        send_message(msg["chat"]["id"], "Только цифры и + - * / ( )"); return
    try:
        val = eval(expr, {"__builtins__": {}}, {})
        send_message(msg["chat"]["id"], f"📠 Ответ: <b>{val}</b>")
    except:
        send_message(msg["chat"]["id"], "Не смог посчитать. Проверь выражение.")

def handle_report(msg, raw_text):
    text = raw_text.partition(' ')[2].strip()
    if not text:
        send_message(msg["chat"]["id"], "Напиши сообщение после команды."); return
    send_message(msg["chat"]["id"], "Спасибо! Сообщение принято.")

# ========= Роутер текста ИГРЫ (без слэшей) =========
def build_msg_dict(aiogram_message) -> dict:
    m = aiogram_message
    return {
        "message_id": m.message_id,
        "from": {"id": m.from_user.id, "username": m.from_user.username, "first_name": m.from_user.first_name},
        "chat": {"id": m.chat.id},
        "date": int(time.time()),
        "text": m.text or ""
    }

def process_text_with_game(aiogram_message) -> bool:
    """Возвращает True, если сообщение обработано ИГРОЙ; False — если не распознано (пусть ответит ИИ)."""
    msg = build_msg_dict(aiogram_message)

    # миграция юзера + анти-спам
    u = ensure_user(msg['from']['id'], msg['from'].get('username'))
    if u.get("is_banned") or (u.get("mute_until",0) > time.time()):
        return True  # считаем обработанным (просто молчим)

    raw = (msg.get("text") or "").replace("\r","")
    raw_norm = norm(raw)
    parts    = raw_norm.split(" ")
    text_low = raw_norm.lower()
    args     = parts[1:]

    handled = True
    if text_low in ["инфо","info"]:             cmd_info(msg["chat"]["id"])
    elif text_low.startswith("профиль"):        handle_profile(msg)
    elif text_low.startswith("баланс"):         handle_balance(msg)
    elif text_low.startswith("работа"):         handle_work(msg)
    elif text_low.startswith("бонус"):          handle_daily(msg)
    elif text_low.startswith("казино"):         handle_casino_args(msg, args)
    elif text_low.startswith("трейд"):          handle_trade_args(msg, args)
    elif text_low.startswith("банк"):           handle_bank_args(msg, args)
    elif text_low == "машины":                  list_cars(msg["chat"]["id"])
    elif text_low.startswith("машина"):         buy_car(msg, parts)
    elif text_low == "дома":                    list_houses(msg["chat"]["id"])
    elif text_low.startswith("дом"):            buy_house(msg, parts)
    elif text_low.startswith("продать"):        handle_sell(msg, parts)
    elif text_low == "бизнес":                  list_businesses(msg["chat"]["id"])
    elif text_low == "бизнес статистика":       business_stats(msg)
    elif text_low.startswith("бизнес снять "):  business_withdraw_amount(msg, args[1] if len(args)>=2 else "0")
    elif text_low == "бизнес снять":            business_withdraw_all(msg)
    elif text_low == "бизнес улучшить":         business_upgrade(msg)
    elif text_low.startswith("бизнес "):        buy_business(msg, parts)
    elif text_low == "ферма":                   farm_menu(msg["chat"]["id"])
    elif text_low.startswith("ферма купить"):   farm_buy(msg, parts)
    elif text_low == "ферма снять":             farm_withdraw(msg)
    elif text_low == "ферма стата":             farm_stats(msg)
    elif text_low.startswith("ник"):            handle_nick(msg, parts)
    elif text_low.startswith("рейтинг"):        handle_rating(msg, parts)
    elif text_low == "топ":                     handle_top(msg)
    elif text_low.startswith("переверни"):      handle_reverse(msg, parts, raw_norm)
    elif text_low.startswith("выбери"):         handle_choose(msg, raw_norm)
    elif text_low.startswith("реши"):           handle_solve(msg, raw_norm)
    elif text_low.startswith("репорт"):         handle_report(msg, raw_norm)
    elif text_low.startswith("передать"):       handle_transfer(msg, parts)
    else:
        handled = False

    return handled

# инициализируем users при импорте
def _ensure_users_loaded():
    global users
    users = load_users()

_ensure_users_loaded()
