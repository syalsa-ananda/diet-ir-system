# diet-ir-system

**Sistem Temu Kembali Resep Diet Rendah Kalori**
Berbasis Hybrid Computing Score TF-IDF, BM25, dan Calorie-Aware Ranking

> Penelitian Mata Kuliah Sistem Temu Kembali Informasi

---

## Deskripsi

ResepDiet adalah sistem chatbot berbasis web yang membantu pengguna Indonesia menemukan resep makanan rendah kalori. Pengguna cukup mengetik pertanyaan dengan bahasa sehari-hari, sistem akan mencari dan menampilkan resep yang relevan beserta informasi gizi dan langkah memasaknya.

Sistem ini menggunakan pendekatan **Hybrid Information Retrieval** yang menggabungkan tiga komponen utama:
- **TF-IDF** — mengukur relevansi kata kunci terhadap dokumen resep
- **BM25** — algoritma ranking probabilistik untuk mengurutkan hasil
- **Calorie-Aware Ranking** — komponen tambahan yang memprioritaskan resep dengan kalori lebih rendah

Hasil pencarian kemudian diproses oleh **GPT-4o-mini** sebagai modul Natural Language Generation (NLG) untuk menyajikan bahan dan langkah memasak dalam bahasa Indonesia yang baku dan mudah dipahami.

---

## Arsitektur Sistem

```
Query user (bahasa natural)
        ↓
Intent Classification (intents.json)
        ↓
IR Engine: TF-IDF + BM25 + Calorie-Aware Ranking
        ↓
Validasi bahan (filter kategori protein)
        ↓
OpenAI GPT-4o-mini (naturalisasi teks)
        ↓
FastAPI → Chat UI (HTML/CSS/JS)
```

---

## Struktur Folder

```
diet-ir-system/
│
├── app/
│   ├── main.py                         ← FastAPI backend + endpoint /chat
│   └── static/
│       └── index.html                  ← Chat UI (mobile-friendly)
│
├── data/
│   ├── resep/                          ← Dataset resep per protein (8 file CSV)
│   │   ├── dataset-ayam.csv
│   │   ├── dataset-ikan.csv
│   │   ├── dataset-kambing.csv
│   │   ├── dataset-sapi.csv
│   │   ├── dataset-tahu.csv
│   │   ├── dataset-telur.csv
│   │   ├── dataset-tempe.csv
│   │   └── dataset-udang.csv
│   ├── nutrition.csv                   ← Dataset nutrisi 1.346 bahan makanan
│   ├── resep_clean.csv                 ← [GENERATED] Output Step 1
│   └── dataset_final_resep_nutrisi.csv ← [GENERATED] Output Step 2
│
├── notebooks/
│   ├── 01_build_recipe_dataset.ipynb   ← Gabung + bersihkan dataset resep
│   ├── 02_calorie_estimation.ipynb     ← Estimasi kalori per resep (fuzzy match)
│   ├── 03_build_ir_system.ipynb        ← Bangun TF-IDF + BM25 + Calorie index
│   └── 04_evaluation.ipynb            ← Evaluasi Precision, Recall, MRR, NDCG
│
├── src/
│   ├── ir_system.py                    ← Modul IR engine (search + scoring)
│   ├── chatbot.py                      ← Intent classification + OpenAI NLG
│   ├── intents.json                    ← Kamus intent 23 kategori
│   └── ir_model.pkl                    ← [GENERATED] Model terlatih
│
├── output/
│   └── evaluation_results.csv          ← [GENERATED] Hasil evaluasi
│
├── .env                                ← API key (TIDAK di-push ke GitHub)
├── .env.example                        ← Template .env
├── .gitignore
├── Dockerfile                          ← Untuk deploy ke Cloud Run
├── .dockerignore
├── requirements.txt
├── DEPLOY.md                           ← Panduan deploy Google Cloud Run
└── README.md                           ← File ini
```

---

## Setup & Instalasi

### Prasyarat
- Python 3.10 atau lebih baru
- OpenAI API key (untuk fitur naturalisasi teks)

### Langkah 1 — Clone repository

```bash
git clone https://github.com/USERNAME/diet-ir-system.git
cd diet-ir-system
```

### Langkah 2 — Buat virtual environment

```bash
python -m venv .venv
```

Aktifkan:
```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# Mac / Linux
source .venv/bin/activate
```

### Langkah 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### Langkah 4 — Buat file .env

```bash
copy .env.example .env   # Windows
cp .env.example .env     # Mac/Linux
```

Isi file `.env` dengan API key Anda:
```
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

### Langkah 5 — Siapkan data

Pastikan file-file berikut sudah ada di tempat yang benar:
- 8 file `dataset-*.csv` → taruh di `data/resep/`
- `nutrition.csv` → taruh di `data/`

---

## Menjalankan Notebook (Wajib Urut)

Jalankan notebook **secara berurutan** untuk membangun sistem dari awal:

| Urutan | Notebook | Output | Estimasi Waktu |
|--------|----------|--------|----------------|
| 1 | `01_build_recipe_dataset.ipynb` | `data/resep_clean.csv` | 1-2 menit |
| 2 | `02_calorie_estimation.ipynb` | `data/dataset_final_resep_nutrisi.csv` | 10-15 menit |
| 3 | `03_build_ir_system.ipynb` | `src/ir_model.pkl` | 5-10 menit |
| 4 | `04_evaluation.ipynb` | `output/evaluation_results.csv` | 5-10 menit |

Daftarkan kernel Jupyter dulu sebelum membuka notebook:
```bash
python -m ipykernel install --user --name=diet-ir-system --display-name "Python (diet-ir-system)"
jupyter notebook
```

---

## Menjalankan Web Chatbot

Setelah `ir_model.pkl` sudah terbuat (Step 3 selesai):

```bash
# Pastikan venv aktif dan berada di folder diet-ir-system/
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

Buka browser: **http://localhost:8080**

---

## Hasil Evaluasi

Sistem dievaluasi menggunakan 10 query variatif dengan metrik standar IR:

| Metrik | TF-IDF | BM25 | TF-IDF+BM25 | Hybrid+Calorie | Hybrid BEST |
|--------|--------|------|-------------|----------------|-------------|
| Precision@10 | 0.34 | 0.37 | 0.36 | **0.44** | 0.43 |
| Recall@10 | 0.34 | 0.37 | 0.36 | **0.44** | 0.43 |
| MRR | 0.71 | 0.72 | 0.72 | 0.76 | **0.76** |
| NDCG@10 | 0.74 | 0.77 | **0.79** | 0.77 | 0.79 |

**Kesimpulan:** Sistem Hybrid+Calorie mengungguli baseline TF-IDF dan BM25 pada Precision dan Recall dengan peningkatan **18.9%**, membuktikan kontribusi nyata dari komponen Calorie-Aware Ranking.

---

## Teknologi yang Digunakan

| Komponen | Teknologi |
|----------|-----------|
| IR Engine | TF-IDF (scikit-learn), BM25 (rank-bm25) |
| NLP Bahasa Indonesia | PySastrawi (stemming + stopword) |
| Fuzzy Matching | RapidFuzz |
| NLG | OpenAI GPT-4o-mini |
| Backend | FastAPI + Uvicorn |
| Frontend | HTML / CSS / Vanilla JS |
| Deploy | Google Cloud Run |

---

## Contoh Penggunaan

```
Pengguna : "resep ayam rendah kalori"
ResepDiet : Mencarikan resep rendah kalori — saya temukan 3 resep (Ayam) untukmu!
            [Menampilkan kartu resep dengan bahan dan langkah memasak]

Pengguna : "ada tahu di rumah, bisa masak apa yang sehat?"
ResepDiet : Kategori: Tahu — saya temukan 3 resep untukmu!
            [Menampilkan resep tahu rendah kalori]

Pengguna : "ikan di bawah 300 kalori"
ResepDiet : Filter kalori di bawah 300 kkal — saya temukan 3 resep (Ikan) untukmu!
```

---

## Deploy ke Google Cloud Run

Lihat panduan lengkap di **[DEPLOY.md](DEPLOY.md)**

Ringkasan singkat:
```bash
gcloud run deploy diet-ir-system \
  --source . \
  --region asia-southeast1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --set-secrets="OPENAI_API_KEY=OPENAI_API_KEY:latest"
```

---

## Catatan Pengembangan

- File `ir_model.pkl` tidak di-push ke GitHub karena ukurannya besar. Jalankan notebook 1-3 untuk membuat ulang model setelah clone.
- File `.env` tidak pernah di-push ke GitHub. Gunakan `.env.example` sebagai template.
- Untuk deploy ke Cloud Run, API key disimpan di **Google Secret Manager**, bukan di environment variable biasa.