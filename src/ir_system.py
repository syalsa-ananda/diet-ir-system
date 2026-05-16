"""
ir_system.py
============
Modul Sistem Temu Kembali Resep Diet Rendah Kalori
Berbasis Hybrid Computing Score TF-IDF, BM25, dan Calorie-Aware Ranking

Perbaikan v2:
- Tambahkan parameter `kategori` di search() sebagai hard mask
  sehingga filter kategori terjadi di level scoring, bukan post-filter
"""

import os
import re
import pickle
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity


KATA_DIET = [
    "diet", "rendah kalori", "rendah lemak", "sehat", "ringan",
    "tidak gemuk", "nggak gemuk", "gak gemuk", "ga bikin gemuk",
    "tidak bikin gemuk", "langsing", "kurus", "turun berat",
    "berat badan", "low calorie", "low fat", "light",
    "kalori rendah", "lemak rendah", "bebas lemak",
]

STOPWORDS_TAMBAHAN = {
    "resep", "cara", "membuat", "masak", "memasak", "buat",
    "mudah", "enak", "lezat", "sedap", "nikmat",
    "praktis", "simpel", "simple", "cepat",
    "yummy", "mantap", "yuk", "ayo", "dong",
}


class IRSystem:

    def __init__(self, model_path: str = None):
        if model_path is None:
            base_dir   = os.path.dirname(os.path.abspath(__file__))
            model_path = os.path.join(base_dir, "ir_model.pkl")

        print(f"[IRSystem] Loading model dari: {model_path}")

        with open(model_path, "rb") as f:
            bundle = pickle.load(f)

        self.tfidf_vectorizer  = bundle["tfidf_vectorizer"]
        self.tfidf_matrix      = bundle["tfidf_matrix"]
        self.bm25_index        = bundle["bm25_index"]
        self.df                = bundle["df"].reset_index(drop=True)
        self.calorie_threshold = bundle.get("calorie_threshold", 500.0)

        self.calorie_scores = self.df["calories"].apply(
            self._hitung_calorie_score
        ).values

        self._stemmer          = None
        self._stopword_remover = None

        print(f"[IRSystem] Model loaded. Corpus: {len(self.df):,} dokumen")

    @property
    def stemmer(self):
        if self._stemmer is None:
            from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
            self._stemmer = StemmerFactory().create_stemmer()
        return self._stemmer

    @property
    def stopword_remover(self):
        if self._stopword_remover is None:
            from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory
            self._stopword_remover = StopWordRemoverFactory().create_stop_word_remover()
        return self._stopword_remover

    def preprocess(self, text: str) -> str:
        if not text or pd.isna(text):
            return ""
        text = str(text).lower()
        text = re.sub(r"[^a-z\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        text = self.stopword_remover.remove(text)
        text = self.stemmer.stem(text)
        words = [w for w in text.split() if w not in STOPWORDS_TAMBAHAN]
        return " ".join(words)

    def _hitung_calorie_score(self, calories) -> float:
        if pd.isna(calories) or calories <= 0:
            return 0.5
        return round(1.0 - min(calories / self.calorie_threshold, 1.0), 4)

    def deteksi_intent_diet(self, query: str) -> bool:
        q = query.lower()
        return any(k in q for k in KATA_DIET)

    def search(
        self,
        query: str,
        top_k: int = 10,
        alpha: float = 0.4,
        beta: float = 0.4,
        gamma: float = 0.2,
        kalori_max: float = None,
        kategori: str = None,        # ← BARU: filter kategori protein
    ) -> pd.DataFrame:
        """
        Hybrid search: TF-IDF + BM25 + Calorie-Aware.

        Args:
            query     : teks pencarian dari user
            top_k     : jumlah hasil
            alpha     : bobot TF-IDF
            beta      : bobot BM25
            gamma     : bobot Calorie-Aware
            kalori_max: filter hard kalori maksimum (opsional)
            kategori  : filter hard kategori protein, contoh 'tahu.csv' (opsional)
                        Jika diisi, hanya dokumen dengan Kategori == kategori
                        yang akan masuk hasil akhir.
        """

        query_processed = self.preprocess(query)
        if not query_processed.strip():
            return pd.DataFrame()

        # ---- TF-IDF ----
        query_vec    = self.tfidf_vectorizer.transform([query_processed])
        tfidf_scores = cosine_similarity(query_vec, self.tfidf_matrix)[0]
        tfidf_max    = tfidf_scores.max()
        tfidf_norm   = tfidf_scores / tfidf_max if tfidf_max > 0 else tfidf_scores

        # ---- BM25 ----
        query_tokens = query_processed.split()
        bm25_scores  = self.bm25_index.get_scores(query_tokens)
        bm25_max     = bm25_scores.max()
        bm25_norm    = bm25_scores / bm25_max if bm25_max > 0 else bm25_scores

        # ---- Calorie Score ----
        cal_scores = self.calorie_scores

        # ---- Adaptive Weights ----
        if self.deteksi_intent_diet(query):
            a, b, g = 0.35, 0.35, 0.30
        else:
            a, b, g = alpha, beta, gamma

        # ---- Hybrid Score ----
        hybrid = a * tfidf_norm + b * bm25_norm + g * cal_scores

        # ---- Filter Kalori (hard mask) ----
        if kalori_max is not None:
            mask_kal = (
                self.df["calories"].notna() &
                (self.df["calories"] <= kalori_max)
            ).values
            hybrid = hybrid * mask_kal

        # ---- Filter Kategori (hard mask) ← BARU ----
        # Set skor = 0 untuk dokumen di luar kategori
        # sehingga tidak pernah masuk top-K
        if kategori is not None:
            mask_kat = (self.df["Kategori"] == kategori).values
            hybrid   = hybrid * mask_kat

        # ---- Top-K ----
        top_idx = np.argsort(hybrid)[::-1][:top_k]
        hasil   = self.df.iloc[top_idx].copy()

        hasil["tfidf_score"]     = tfidf_norm[top_idx]
        hasil["bm25_score"]      = bm25_norm[top_idx]
        hasil["calorie_score_doc"] = cal_scores[top_idx]
        hasil["hybrid_score"]    = hybrid[top_idx]

        hasil = hasil[hasil["hybrid_score"] > 0]

        return hasil.reset_index(drop=True)

    def format_results(self, df_hasil: pd.DataFrame) -> str:
        if df_hasil is None or len(df_hasil) == 0:
            return "Maaf, tidak ditemukan resep yang sesuai. Coba gunakan kata kunci yang berbeda ya 😊"

        lines = [f"Saya temukan **{len(df_hasil)} resep** yang cocok untuk kamu:\n"]

        for i, row in df_hasil.iterrows():
            kal   = f"{row['calories']:.0f} kkal" if pd.notna(row.get("calories")) else "—"
            pro   = f"{row['proteins']:.1f}g"     if pd.notna(row.get("proteins")) else "—"
            lemak = f"{row['fat']:.1f}g"          if pd.notna(row.get("fat"))      else "—"
            karbo = f"{row['carbohydrate']:.1f}g" if pd.notna(row.get("carbohydrate")) else "—"
            kat   = row.get("Kategori", "").replace(".csv", "").title()

            lines.append(f"**{i+1}. {row['Title']}** ({kat})")
            lines.append(f"   🔥 Kalori: {kal}  |  🥩 Protein: {pro}  |  🫙 Lemak: {lemak}  |  🌾 Karbo: {karbo}")
            lines.append(f"   📊 Skor relevansi: {row['hybrid_score']:.3f}")
            lines.append("")

        return "\n".join(lines)