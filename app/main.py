"""
main.py — FastAPI backend untuk Diet IR System Chatbot
Versi 2: mengembalikan structured JSON untuk UI yang lebih bersih
"""

import os, sys, time, re
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from chatbot import Chatbot, deteksi_kategori, KATA_DIET, naturalisasi_resep

# ============================================================
# INIT
# ============================================================

app = FastAPI(title="Diet IR System", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

print("[API] Loading chatbot...")
bot = Chatbot(openai_api_key=os.getenv("OPENAI_API_KEY"))
print("[API] Chatbot ready.")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ============================================================
# MODELS
# ============================================================

class ChatRequest(BaseModel):
    message: str
    top_k: int = 3

class NutritionInfo(BaseModel):
    kalori: Optional[float] = None
    protein: Optional[float] = None
    lemak: Optional[float] = None
    karbo: Optional[float] = None
    porsi: Optional[float] = None

class RecipeCard(BaseModel):
    rank: int
    title: str
    category: str
    nutrition: NutritionInfo
    ingredients: list[str]
    steps: list[str]
    score: float
    score_pct: int

class ChatResponse(BaseModel):
    type: str           # "recipe" | "info" | "greeting"
    message: str        # pesan singkat untuk chat bubble
    recipes: list[RecipeCard]
    duration_ms: int


# ============================================================
# HELPERS
# ============================================================

def extract_kalori_max(query: str):
    m = re.search(
        r"(?:di bawah|kurang dari|maksimal|max|bawah|<)\s*(\d+)\s*(?:kalori|kal|kkal)?",
        query.lower()
    )
    if m:
        v = float(m.group(1))
        return v if 50 <= v <= 2000 else None
    return None

def build_chat_prefix(query: str, kategori: str, kalori_max) -> str:
    parts = []
    if any(k in query.lower() for k in KATA_DIET):
        parts.append("Mencarikan resep rendah kalori untukmu")
    if kalori_max:
        parts.append(f"Filter kalori di bawah {kalori_max:.0f} kkal")
    if kategori:
        parts.append(f"Kategori: {kategori.replace('.csv','').title()}")
    return " · ".join(parts) if parts else "Ini resep yang saya temukan"

def df_to_recipe_cards(df_hasil, top_k: int, api_key: str = None) -> list[RecipeCard]:
    import pandas as pd
    cards = []
    for i, row in df_hasil.head(top_k).iterrows():
        raw_ing   = str(row.get("Ingredients", ""))
        raw_steps = str(row.get("Steps", ""))
        title     = str(row.get("Title", ""))

        # ── Coba naturalisasi via OpenAI ──
        nlg = None
        if api_key:
            nlg = naturalisasi_resep(
                judul       = title,
                bahan_raw   = raw_ing,
                langkah_raw = raw_steps,
                api_key     = api_key,
            )

        # ── Bahan ──
        if nlg and nlg.get("bahan"):
            ingredients = [b.lstrip("- ").strip() for b in nlg["bahan"].split("\n") if b.strip()]
        elif raw_ing and raw_ing != "nan":
            ingredients = [b.strip() for b in raw_ing.split("--") if b.strip()]
        else:
            ingredients = []

        # ── Langkah ──
        if nlg and nlg.get("langkah"):
            steps = [re.sub(r"^\d+\.\s*", "", l).strip()
                     for l in nlg["langkah"].split("\n") if l.strip()]
        elif raw_steps and raw_steps != "nan":
            steps = [s.strip() for s in raw_steps.split("--") if s.strip() and len(s.strip()) > 5]
            if len(steps) <= 1:
                steps = [s.strip() for s in re.split(r"\n+", raw_steps) if s.strip() and len(s.strip()) > 5]
        else:
            steps = []

        score = float(row.get("hybrid_score", 0))
        kal   = row.get("calories")
        pro   = row.get("proteins")
        fat   = row.get("fat")
        carb  = row.get("carbohydrate")
        porsi = row.get("porsi", 4)

        cards.append(RecipeCard(
            rank=len(cards) + 1,
            title=title,
            category=str(row.get("Kategori", "")).replace(".csv", "").title(),
            nutrition=NutritionInfo(
                kalori=round(float(kal), 1) if pd.notna(kal) else None,
                protein=round(float(pro), 1) if pd.notna(pro) else None,
                lemak=round(float(fat), 1) if pd.notna(fat) else None,
                karbo=round(float(carb), 1) if pd.notna(carb) else None,
                porsi=float(porsi) if pd.notna(porsi) else 4,
            ),
            ingredients=ingredients,
            steps=steps,
            score=round(score, 3),
            score_pct=min(int(score * 100), 100),
        ))
    return cards


# ============================================================
# ROUTES
# ============================================================

@app.get("/")
async def root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/health")
async def health():
    return {"status": "ok", "corpus": len(bot.ir.df)}

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    query = req.message.strip()
    if not query:
        return ChatResponse(type="greeting", message="Silakan ketik pertanyaan kamu 😊",
                            recipes=[], duration_ms=0)

    start = time.time()

    try:
        intent    = bot.matcher.match(query)
        action    = intent.get("action", "respond") if intent else None
        tag       = intent.get("tag", "") if intent else ""
        kalori_max = bot._kalori_max(query)
        kategori  = None

        # Cek apakah ini intent statis (bukan search)
        static_tags = {"greeting", "goodbye", "thanks", "help", "about",
                       "info_kalori", "info_gizi", "tips_diet"}

        if tag in static_tags or (action == "respond"):
            reply = bot.matcher.get_response(tag) or "Ada yang bisa saya bantu? 😊"
            return ChatResponse(
                type="info",
                message=reply,
                recipes=[],
                duration_ms=int((time.time() - start) * 1000),
            )

        # Search intent — ambil DataFrame langsung
        if action == "search":
            kategori = intent.get("kategori")
            q_aug = intent.get("query_override", query)
        elif action in ("search_bahan", "search_filter_kalori"):
            kategori = deteksi_kategori(query)
            q_aug = query
        elif action == "search_diet":
            kategori = deteksi_kategori(query)
            kalori_max = kalori_max or 400.0
            q_aug = query
        else:
            kategori = deteksi_kategori(query)
            q_aug = query

        # Augment query
        if kategori:
            nama = kategori.replace(".csv", "")
            if nama not in q_aug.lower():
                q_aug = f"{nama} {q_aug}"

        # Jalankan IR search
        df_hasil = bot.ir.search(
            query=q_aug,
            top_k=req.top_k * 5,
            kalori_max=kalori_max,
            kategori=kategori,
        )

        # Validasi bahan
        if df_hasil is not None and len(df_hasil) > 0 and kategori:
            nama_protein = kategori.replace(".csv", "").lower()
            valid = df_hasil[df_hasil["Ingredients"].apply(
                lambda x: nama_protein in str(x).lower()
            )]
            if len(valid) >= 2:
                df_hasil = valid

        if df_hasil is None or len(df_hasil) == 0:
            return ChatResponse(
                type="info",
                message=f"Maaf, tidak ada resep yang cocok untuk '{query}' 😔 Coba kata kunci lain ya!",
                recipes=[],
                duration_ms=int((time.time() - start) * 1000),
            )

        cards = df_to_recipe_cards(df_hasil, req.top_k, api_key=bot.api_key)
        prefix = build_chat_prefix(query, kategori, kalori_max)
        n = len(cards)
        cat_str = f" ({kategori.replace('.csv','').title()})" if kategori else ""
        message = f"{prefix} — saya temukan **{n} resep{cat_str}** untukmu! 🥗"

        return ChatResponse(
            type="recipe",
            message=message,
            recipes=cards,
            duration_ms=int((time.time() - start) * 1000),
        )

    except Exception as e:
        return ChatResponse(
            type="info",
            message=f"Maaf, terjadi kesalahan: {str(e)}",
            recipes=[],
            duration_ms=int((time.time() - start) * 1000),
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)