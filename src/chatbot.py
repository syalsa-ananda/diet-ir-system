"""
chatbot.py v5 — kategori diteruskan langsung ke ir.search()
"""

import re, json, random, os
import pandas as pd
from ir_system import IRSystem

# Load .env file (OPENAI_API_KEY disimpan di sini, tidak di-push ke GitHub)
try:
    from dotenv import load_dotenv
    # Cari .env di folder parent (diet-ir-system/)
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
    load_dotenv(env_path)
except ImportError:
    pass  # dotenv tidak wajib, bisa pakai environment variable langsung

# OpenAI — untuk naturalisasi teks resep
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
INTENTS_PATH = os.path.join(BASE_DIR, "intents.json")

with open(INTENTS_PATH, encoding="utf-8") as f:
    INTENTS_DATA = json.load(f)["intents"]

print(f"[Chatbot] Intents loaded: {len(INTENTS_DATA)} tag")

KATEGORI_KEYWORDS = {
    "daging sapi":"sapi.csv","daging kambing":"kambing.csv",
    "dada ayam":"ayam.csv","paha ayam":"ayam.csv",
    "ikan lele":"ikan.csv","ikan nila":"ikan.csv","ikan mas":"ikan.csv",
    "ikan kakap":"ikan.csv","ikan kembung":"ikan.csv",
    "ikan mujair":"ikan.csv","ikan gurame":"ikan.csv",
    "ikan salmon":"ikan.csv","ikan tuna":"ikan.csv",
    "ayam":"ayam.csv","chicken":"ayam.csv",
    "ikan":"ikan.csv","fish":"ikan.csv",
    "sapi":"sapi.csv","beef":"sapi.csv",
    "kambing":"kambing.csv","domba":"kambing.csv","lamb":"kambing.csv",
    "udang":"udang.csv","shrimp":"udang.csv","prawn":"udang.csv",
    "tahu":"tahu.csv","tofu":"tahu.csv",
    "telur":"telur.csv","telor":"telur.csv","egg":"telur.csv",
    "tempe":"tempe.csv","tempeh":"tempe.csv",
}
KATEGORI_SORTED = sorted(KATEGORI_KEYWORDS.keys(), key=len, reverse=True)

KATA_DIET = [
    "diet","rendah kalori","rendah lemak","sehat","ringan",
    "tidak gemuk","nggak gemuk","gak gemuk","ga bikin gemuk",
    "tidak bikin gemuk","langsing","kurus","turun berat",
    "berat badan","low calorie","low fat","light",
    "kalori rendah","lemak rendah","buncit","ga bikin buncit",
]


def deteksi_kategori(query: str):
    q = query.lower()
    for kata in KATEGORI_SORTED:
        if kata in q:
            return KATEGORI_KEYWORDS[kata]
    return None


class IntentMatcher:
    def __init__(self, intents):
        self.intents  = intents
        self.tag_map  = {i["tag"]: i for i in intents}
        self.compiled = []
        for intent in intents:
            patterns = intent.get("patterns", [])
            if not patterns:
                continue
            regex = "|".join(
                r"\b" + re.escape(p.lower()) + r"\b"
                for p in sorted(patterns, key=len, reverse=True)
            )
            self.compiled.append({"tag": intent["tag"], "regex": re.compile(regex), "intent": intent})

    def match(self, query):
        q, best, best_len = query.lower().strip(), None, 0
        for item in self.compiled:
            m = item["regex"].search(q)
            if m and len(m.group(0)) > best_len:
                best_len = len(m.group(0))
                best     = item["intent"]
        return best

    def get_response(self, tag):
        intent = self.tag_map.get(tag)
        if intent and intent.get("responses"):
            resp = random.choice(intent["responses"])
            if not resp.startswith("__"):
                return resp
        return ""


# ============================================================
# OPENAI NATURALIZER
# ============================================================

def naturalisasi_resep(judul, bahan_raw, langkah_raw, api_key):
    """
    Gunakan OpenAI GPT untuk mengubah teks resep mentah
    menjadi bahasa Indonesia yang natural dan mudah dipahami.

    Args:
        judul      : judul resep
        bahan_raw  : string bahan mentah dari dataset
        langkah_raw: string langkah mentah dari dataset
        api_key    : OpenAI API key

    Returns:
        dict {bahan: str, langkah: str} hasil parafrase
    """
    if not OPENAI_AVAILABLE or not api_key:
        return None

    # Bersihkan bahan dan langkah mentah
    bahan_list   = [b.strip() for b in str(bahan_raw).split("--") if b.strip()]
    langkah_list = [l.strip() for l in str(langkah_raw).split("--") if l.strip() and len(l.strip()) > 5]

    bahan_text   = "\n".join(f"- {b}" for b in bahan_list)
    langkah_text = "\n".join(f"{i+1}. {l}" for i, l in enumerate(langkah_list))

    prompt = f"""Kamu adalah editor resep profesional yang bertugas merapikan teks resep agar mudah dipahami semua kalangan.

Berikut data resep mentah yang perlu dirapikan:

JUDUL RESEP: {judul}

BAHAN-BAHAN (mentah):
{bahan_text}

LANGKAH MEMASAK (mentah):
{langkah_text}

ATURAN WAJIB:

Untuk BAHAN-BAHAN:
- Tulis lengkap setiap singkatan tanpa kecuali:
  sdm → sendok makan, sdt → sendok teh, bwng → bawang, telor/telor → telur,
  btr → butir, gr/gram → gram, kg → kilogram, sck → secukupnya,
  bk/bks → bungkus, sm → sama, dg/dgn → dengan, u/ → untuk,
  dll → dan lain-lain, dst → dan seterusnya
- Perbaiki ejaan yang salah
- Jangan ubah takaran atau urutan
- Tidak perlu diawali huruf kapital tiap kata

Untuk LANGKAH MEMASAK:
- Tulis setiap langkah dengan bahasa Indonesia yang baku dan jelas
- WAJIB tulis lengkap setiap singkatan (sama seperti aturan bahan di atas)
- Setiap langkah harus bisa dipahami oleh orang yang baru belajar memasak
- HAPUS semua kalimat berikut tanpa pengecualian:
  * Cerita atau pengalaman pribadi penulis ("saya makan pakai...", "di rumah saya...", "misua", "breng suami", dll)
  * Ekspresi berlebihan ("enak sekaleeee", "mantaap", "yummy banget", dll)
  * Kalimat basa-basi yang tidak informatif
  * Semua emoji
- Jika ada catatan berguna (variasi bahan, tips memasak), tulis ulang dengan kalimat netral dan informatif
  Contoh: "Siap disajikan dimakan pake nasi angat trs makan berdua breng misua enak sekaleeee😆"
  → Cukup tulis: "Angkat dan sajikan selagi hangat."
- JANGAN tambah informasi yang tidak ada di teks asli

Balas HANYA dalam format JSON berikut tanpa tambahan apapun:
{{
  "bahan": "bahan 1\nbahan 2\nbahan 3",
  "langkah": "1. langkah pertama\n2. langkah kedua\n3. langkah ketiga"
}}"""

    try:
        client   = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",        # model murah dan cepat
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,            # rendah agar konsisten
            max_tokens=1000,
        )
        raw  = response.choices[0].message.content.strip()

        # Bersihkan markdown code block jika ada
        raw  = re.sub(r"```json|```", "", raw).strip()
        data = json.loads(raw)

        return {
            "bahan":   data.get("bahan", bahan_text),
            "langkah": data.get("langkah", langkah_text),
        }

    except Exception as e:
        # Jika gagal (rate limit, timeout, dll) → fallback ke format biasa
        return None


def format_bahan(s):
    if pd.isna(s) or not str(s).strip():
        return "  (data tidak tersedia)"
    items = [b.strip() for b in str(s).split("--") if b.strip()]
    return "\n".join(f"  • {b}" for b in items)


def format_langkah(s):
    if pd.isna(s) or not str(s).strip():
        return "  (data tidak tersedia)"
    raw   = str(s)
    items = [l.strip() for l in raw.split("--") if l.strip() and len(l.strip()) > 5]
    if len(items) <= 1:
        items = [l.strip() for l in re.split(r"\n+", raw) if l.strip() and len(l.strip()) > 5]
    if len(items) <= 1:
        items = [l.strip() for l in re.split(r"(?<=[.!?])\s+", raw.strip()) if len(l.strip()) > 5]
    if not items:
        return "  (data tidak tersedia)"
    return "\n".join(f"  {i+1}. {l}" for i, l in enumerate(items))


def format_resep(nomor, row):
    kal   = f"{row['calories']:.0f} kkal"    if not pd.isna(row.get('calories'))     else "—"
    pro   = f"{row['proteins']:.1f}g"         if not pd.isna(row.get('proteins'))     else "—"
    lemak = f"{row['fat']:.1f}g"              if not pd.isna(row.get('fat'))          else "—"
    karbo = f"{row['carbohydrate']:.1f}g"     if not pd.isna(row.get('carbohydrate')) else "—"
    kat   = str(row.get("Kategori","")).replace(".csv","").title()
    porsi = row.get("porsi", 4)
    skor  = row.get("hybrid_score", 0)
    return "\n".join([
        f"{'─'*50}",
        f"**{nomor}. {row['Title']}** ({kat})",
        f"{'─'*50}",
        f"🔥 Kalori : {kal}/porsi  (untuk {porsi:.0f} porsi)",
        f"🥩 Protein: {pro}  |  🫙 Lemak: {lemak}  |  🌾 Karbo: {karbo}",
        f"📊 Skor relevansi: {skor:.3f}",
        "",
        "📝 **Bahan-bahan:**",
        format_bahan(row.get("Ingredients","")),
        "",
        "👨‍🍳 **Langkah memasak:**",
        format_langkah(row.get("Steps","")),
        "",
    ])


class Chatbot:
    def __init__(self, model_path=None, openai_api_key=None):
        self.ir       = IRSystem(model_path=model_path)
        self.matcher  = IntentMatcher(INTENTS_DATA)
        self.api_key  = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.use_nlg  = OPENAI_AVAILABLE and bool(self.api_key)
        if self.use_nlg:
            print("[Chatbot] OpenAI NLG aktif — resep akan ditampilkan dalam bahasa natural")
        else:
            print("[Chatbot] OpenAI tidak tersedia — menggunakan format standar")
        print("[Chatbot] Siap menerima pertanyaan.")

    def _kalori_max(self, query):
        m = re.search(
            r"(?:di bawah|kurang dari|maksimal|max|bawah|<)\s*(\d+)\s*(?:kalori|kal|kkal)?",
            query.lower()
        )
        if m:
            v = float(m.group(1))
            return v if 50 <= v <= 2000 else None
        return None

    def _validasi_bahan(self, hasil, kategori):
        """
        Solusi A: Validasi bahan — hanya pertahankan resep yang
        benar-benar mengandung nama protein kategori di ingredients.

        Contoh: kategori=tahu.csv → ingredients harus mengandung kata 'tahu'
        """
        if kategori is None:
            return hasil

        nama_protein = kategori.replace(".csv", "").lower()

        def mengandung_protein(ingredients):
            return nama_protein in str(ingredients).lower()

        hasil_valid = hasil[hasil["Ingredients"].apply(mengandung_protein)].copy()

        # Jika setelah validasi tidak ada hasil → kembalikan semua
        # (agar chatbot tidak pernah kosong)
        return hasil_valid if len(hasil_valid) > 0 else hasil

    def _do_search(self, query, top_k=3, kategori=None, kalori_max=None):
        # Augment query dengan nama kategori agar TF-IDF lebih relevan
        q_aug = query
        if kategori:
            nama = kategori.replace(".csv","")
            if nama not in query.lower():
                q_aug = f"{nama} {query}"

        # Ambil lebih banyak kandidat karena akan divalidasi
        top_k_fetch = top_k * 5 if kategori else top_k

        hasil = self.ir.search(
            query=q_aug,
            top_k=top_k_fetch,
            kalori_max=kalori_max,
            kategori=kategori,
        )

        if hasil is None or len(hasil) == 0:
            hasil = self.ir.search(query=q_aug, top_k=top_k, kalori_max=kalori_max)
            if hasil is None or len(hasil) == 0:
                return f"Maaf, tidak ada resep yang cocok untuk '{query}' 😔\nCoba kata kunci yang berbeda ya!"

        # Solusi A: validasi bahan — pastikan protein ada di ingredients
        hasil = self._validasi_bahan(hasil, kategori)

        # Ambil top_k setelah validasi
        hasil = hasil.head(top_k).reset_index(drop=True)

        prefix_parts = []
        if kalori_max:
            prefix_parts.append(f"🎯 Mencari resep dengan kalori di bawah **{kalori_max:.0f} kkal**")
        if any(k in query.lower() for k in KATA_DIET):
            prefix_parts.append("🥗 Menampilkan resep rendah kalori")
        if kategori:
            prefix_parts.append(f"📂 Kategori: **{kategori.replace('.csv','').title()}**")

        prefix = "\n".join(prefix_parts) + "\n\n" if prefix_parts else ""
        lines  = [prefix, f"Saya temukan **{len(hasil)} resep** untukmu:\n"]
        for i, row in hasil.iterrows():
            lines.append(self._format_resep_nlg(i+1, row))
        return "\n".join(lines)

    def _format_resep_nlg(self, nomor, row):
        """
        Format satu resep — jika OpenAI tersedia, naturalisasi dulu
        bahan dan langkah sebelum ditampilkan.
        """
        kal   = f"{row['calories']:.0f} kkal"    if not pd.isna(row.get('calories'))     else "—"
        pro   = f"{row['proteins']:.1f}g"         if not pd.isna(row.get('proteins'))     else "—"
        lemak = f"{row['fat']:.1f}g"              if not pd.isna(row.get('fat'))          else "—"
        karbo = f"{row['carbohydrate']:.1f}g"     if not pd.isna(row.get('carbohydrate')) else "—"
        kat   = str(row.get("Kategori","")).replace(".csv","").title()
        porsi = row.get("porsi", 4)
        skor  = row.get("hybrid_score", 0)

        # Coba naturalisasi via OpenAI
        nlg = None
        if self.use_nlg:
            nlg = naturalisasi_resep(
                judul       = row.get("Title", ""),
                bahan_raw   = row.get("Ingredients", ""),
                langkah_raw = row.get("Steps", ""),
                api_key     = self.api_key,
            )

        if nlg:
            # Format bahan dari hasil NLG
            bahan_text   = "\n".join(f"  • {b.lstrip('- ')}" for b in nlg["bahan"].split("\n") if b.strip())
            langkah_text = "\n".join(f"  {l}" for l in nlg["langkah"].split("\n") if l.strip())
        else:
            # Fallback ke format standar
            bahan_text   = format_bahan(row.get("Ingredients", ""))
            langkah_text = format_langkah(row.get("Steps", ""))

        return "\n".join([
            f"{'─'*50}",
            f"**{nomor}. {row['Title']}** ({kat})",
            f"{'─'*50}",
            f"🔥 Kalori : {kal}/porsi  (untuk {porsi:.0f} porsi)",
            f"🥩 Protein: {pro}  |  🫙 Lemak: {lemak}  |  🌾 Karbo: {karbo}",
            f"📊 Skor relevansi: {skor:.3f}",
            "",
            "📝 **Bahan-bahan:**",
            bahan_text,
            "",
            "👨‍🍳 **Langkah memasak:**",
            langkah_text,
            "",
        ])

    def respond(self, query, top_k=3):
        query = query.strip()
        if not query:
            return "Silakan ketik pertanyaan kamu 😊"

        intent     = self.matcher.match(query)
        kalori_max = self._kalori_max(query)

        if intent is None:
            return self._do_search(query, top_k, deteksi_kategori(query), kalori_max)

        tag    = intent["tag"]
        action = intent.get("action","respond")

        if action == "respond":
            return self.matcher.get_response(tag) or self.matcher.get_response("tidak_dimengerti")

        if action == "search":
            return self._do_search(
                intent.get("query_override", query), top_k,
                intent.get("kategori"), kalori_max
            )

        if action in ("search_bahan", "search_filter_kalori"):
            return self._do_search(query, top_k, deteksi_kategori(query), kalori_max)

        if action == "search_diet":
            # Deteksi kategori protein dari kalimat — jika ada
            kategori = deteksi_kategori(query)
            return self._do_search(query, top_k, kategori, kalori_max or 400.0)

        return self.matcher.get_response("tidak_dimengerti")


if __name__ == "__main__":
    print("="*55)
    print("  CHATBOT RESEP DIET RENDAH KALORI")
    print("  TF-IDF + BM25 + Calorie-Aware Ranking")
    print("  Intent Classification via intents.json")
    print("="*55)
    print("Ketik 'keluar' untuk berhenti.\n")

    # API key dibaca otomatis dari .env atau environment variable
    # Jangan pernah tulis API key langsung di kode ini!
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("[WARNING] OPENAI_API_KEY tidak ditemukan di .env")
        print("          Buat file .env di folder diet-ir-system/ dengan isi:")
        print("          OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx")
        print("          Sistem tetap berjalan tanpa naturalisasi.\n")

    bot = Chatbot(openai_api_key=api_key)
    print("\n" + bot.respond("halo") + "\n")

    while True:
        try:
            user_input = input("Kamu: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nSampai jumpa! 👋")
            break
        if not user_input:
            continue
        if user_input.lower() in ["keluar","exit","quit","bye"]:
            print("Bot: Sampai jumpa! Semoga diet kamu berhasil 💪")
            break
        print(f"\nBot: {bot.respond(user_input)}\n")
