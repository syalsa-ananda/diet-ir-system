# Deploy ke Google Cloud Run

## Prasyarat
- Google Cloud account (gratis $300 credit untuk akun baru)
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) terinstall
- Docker terinstall (untuk build lokal, opsional)

---

## Langkah 1 — Setup Google Cloud

```bash
# Login
gcloud auth login

# Buat project baru (atau pakai yang sudah ada)
gcloud projects create diet-ir-system --name="Diet IR System"
gcloud config set project diet-ir-system

# Aktifkan billing (wajib untuk Cloud Run)
# Buka: https://console.cloud.google.com/billing

# Aktifkan API yang dibutuhkan
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable secretmanager.googleapis.com
```

---

## Langkah 2 — Simpan API Key di Secret Manager

```bash
# Simpan OPENAI_API_KEY dengan aman (JANGAN hardcode di kode!)
echo -n "sk-xxxxxxxxxxxxxxxx" | \
  gcloud secrets create OPENAI_API_KEY \
    --data-file=- \
    --replication-policy=automatic

# Verifikasi
gcloud secrets versions list OPENAI_API_KEY
```

---

## Langkah 3 — Build & Deploy

```bash
# Dari folder diet-ir-system/
cd diet-ir-system

# Build dan deploy langsung ke Cloud Run (tanpa Docker lokal)
gcloud run deploy diet-ir-system \
  --source . \
  --region asia-southeast1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 1 \
  --timeout 300 \
  --set-secrets="OPENAI_API_KEY=OPENAI_API_KEY:latest" \
  --port 8080
```

Tunggu 3-5 menit. Setelah selesai akan muncul URL seperti:
```
Service URL: https://diet-ir-system-xxxxxxxxxx-et.a.run.app
```

---

## Langkah 4 — Verifikasi

```bash
# Cek health endpoint
curl https://diet-ir-system-xxxxxxxxxx-et.a.run.app/health

# Test chat endpoint
curl -X POST https://diet-ir-system-xxxxxxxxxx-et.a.run.app/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "resep ayam rendah kalori"}'
```

---

## Jalankan Lokal (sebelum deploy)

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variable
$env:OPENAI_API_KEY = "sk-xxxxxxxx"   # Windows PowerShell
export OPENAI_API_KEY="sk-xxxxxxxx"   # Mac/Linux

# Jalankan server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

# Buka browser
# http://localhost:8080
```

---

## Estimasi Biaya Cloud Run

| Komponen | Gratis per bulan | Keterangan |
|---|---|---|
| Request | 2 juta request | Lebih dari cukup untuk demo |
| CPU | 180.000 vCPU-detik | ~50 jam compute |
| Memory | 360.000 GB-detik | Dengan 2GB RAM = ~50 jam |
| **Total** | **$0** | Untuk traffic demo/penelitian |

Biaya baru muncul jika traffic sangat tinggi atau instance selalu aktif.

---

## Update Setelah Push ke GitHub

```bash
# Setelah ada perubahan kode:
gcloud run deploy diet-ir-system \
  --source . \
  --region asia-southeast1
```

---

## Troubleshooting

**Error: ir_model.pkl not found**
```bash
# Model perlu ada di image. Pastikan ir_model.pkl ada di src/
# dan tidak ada di .dockerignore
```

**Error: Memory limit exceeded**
```bash
# Naikkan memory limit
gcloud run services update diet-ir-system \
  --memory 4Gi \
  --region asia-southeast1
```

**Melihat logs**
```bash
gcloud logging read "resource.type=cloud_run_revision" \
  --limit 50 \
  --format "table(timestamp,textPayload)"
```
