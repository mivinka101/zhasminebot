import asyncio, requests, json

# Бесплатная публичная модель (Gemma-2b-it, хостится HuggingFace Inference)
API_URL = "https://api-inference.huggingface.co/models/google/gemma-2b-it"

def generate(prompt: str, system: str | None = None, max_tokens=200, temperature=0.7):
    sys = system or "Отвечай коротко и по делу, на русском."
    full = f"{sys}\n\nВопрос: {prompt}"
    resp = requests.post(API_URL, json={"inputs": full}, timeout=60)
    if resp.status_code == 200:
        data = resp.json()
        if isinstance(data, list) and len(data) and "generated_text" in data[0]:
            return data[0]["generated_text"].strip()
        return str(data)
    else:
        return f"Ошибка {resp.status_code}: {resp.text}"

async def generate_async(prompt: str, system: str | None = None, **kw):
    return await asyncio.to_thread(generate, prompt, system, **kw)
