"""
Spam Filter API — FastAPI Backend
Eğitilmiş Naive Bayes modelini servis olarak sunar.
POST /predict endpoint'i ile metin alır, spam/ham tahmini ve güven oranı döndürür.

v2 — Async mimari, otomatik çeviri, LRU cache, dinamik UI verisi.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import json as json_module
import joblib
import os
import hashlib
import asyncio
from functools import lru_cache
from collections import OrderedDict
import numpy as np

# ─── Çeviri & Dil Algılama ───────────────────────────────────────────────────
from deep_translator import GoogleTranslator
from langdetect import detect, LangDetectException

# ─── Uygulama ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Spam Filter API",
    description="Gmail Spam Filtresi Chrome Eklentisi için tahmin API'si",
    version="2.1.0",
)

# ─── CORS Middleware (geliştirme için tüm kaynaklara izin ver) ───────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Prod'da kısıtlanmalı
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Model ve Vectorizer Yükleme ────────────────────────────────────────────
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")

try:
    model = joblib.load(os.path.join(MODEL_DIR, "spam_model.pkl"))
    vectorizer = joblib.load(os.path.join(MODEL_DIR, "vectorizer.pkl"))
    print("[OK] Model ve vectorizer basariyla yuklendi.")
except Exception as e:
    print(f"[HATA] Model yukleme hatasi: {e}")
    model = None
    vectorizer = None

# ─── InMemory LRU Cache ─────────────────────────────────────────────────────
# Basit thread-safe LRU cache (çeviri ve tahmin sonuçları için)
class LRUCache:
    """Async-safe, sınırlı kapasiteli LRU cache."""

    def __init__(self, max_size: int = 1024):
        self._cache: OrderedDict = OrderedDict()
        self._max_size = max_size
        self._lock = asyncio.Lock()

    async def get(self, key: str):
        async with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            return None

    async def set(self, key: str, value):
        async with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value
            if len(self._cache) > self._max_size:
                self._cache.popitem(last=False)


translation_cache = LRUCache(max_size=2048)
prediction_cache = LRUCache(max_size=2048)


# ─── Dil Algılama & Çeviri Yardımcıları ─────────────────────────────────────
def _is_english(text: str) -> bool:
    """
    langdetect kütüphanesi ile metnin dilini algılar.
    Algılanan dil 'en' ise True döner, değilse False.
    Algılama başarısız olursa (çok kısa metin vb.) güvenli tarafta kalıp False döner
    → çeviri yapılır.
    """
    if not text or len(text.strip()) < 3:
        return True  # Çok kısa metinlerde çeviriye gerek yok
    try:
        lang = detect(text)
        return lang == "en"
    except LangDetectException:
        return False  # Algılanamadıysa çeviriye gönder


async def translate_to_english(text: str) -> str:
    """
    Metni İngilizceye çevirir.
    • Metin zaten İngilizce ise doğrudan döndürür (koşullu çeviri).
    • Sonuç cache'lenir, aynı metin tekrar geldiğinde API çağrısı yapılmaz.
    """
    if _is_english(text):
        return text

    # Cache kontrolü
    cache_key = hashlib.md5(text.encode()).hexdigest()
    cached = await translation_cache.get(cache_key)
    if cached is not None:
        return cached

    # Asenkron olarak çeviri yap (blocking I/O → executor)
    loop = asyncio.get_event_loop()
    try:
        translated = await loop.run_in_executor(
            None,
            lambda: GoogleTranslator(source="auto", target="en").translate(text),
        )
        await translation_cache.set(cache_key, translated)
        return translated
    except Exception as e:
        print(f"[UYARI] Ceviri servisi hatasi: {e}. Orijinal metin kullanilacak.")
        return text


# ─── Request / Response Şemaları ─────────────────────────────────────────────
class PredictRequest(BaseModel):
    text: str


class PredictResponse(BaseModel):
    prediction: str          # "spam" veya "ham"
    confidence: float        # 0.0 – 1.0 arası güven oranı
    message: str             # Kullanıcıya gösterilecek açıklama
    color_tag: str           # Eklenti UI renk etiketi: "red" | "green" | "yellow"
    status: str              # Durum etiketi: "spam" | "safe" | "suspicious"
    translated: bool         # Metin çevrildiyse True


class FeedbackRequest(BaseModel):
    text: str                # Orijinal e-posta metni
    prediction: str          # Modelin tahmini: "spam" | "ham"
    is_correct: bool         # Kullanıcı onayı: True = doğru, False = yanlış
    user_id: str             # Benzersiz kullanıcı kimliği (Gizlilik korumalı)


class FeedbackResponse(BaseModel):
    status: str
    message: str


# ─── Yardımcı: Dinamik UI verisi ─────────────────────────────────────────────
def _build_ui_fields(label: str, confidence: float) -> dict:
    """
    Güven oranına göre color_tag ve status belirler.
    • Confidence %50-60 → yellow / suspicious
    • spam  → red / spam
    • ham   → green / safe
    """
    pct = confidence * 100

    if 50 <= pct <= 60:
        return {"color_tag": "yellow", "status": "suspicious"}
    elif label == "spam":
        return {"color_tag": "red", "status": "spam"}
    else:
        return {"color_tag": "green", "status": "safe"}


# ─── Endpoint'ler ────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    """API sağlık kontrolü."""
    return {"status": "ok", "message": "Spam Filter API calisiyor"}


@app.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest):
    """
    Gelen metni:
      1) Gerekirse İngilizceye çevir  (koşullu + cache'li)
      2) Vektörize et
      3) Model ile tahmin yap
    Sonuç olarak spam/ham etiketi, güven oranı ve dinamik UI verisi döndür.
    """
    if model is None or vectorizer is None:
        raise HTTPException(
            status_code=503,
            detail="Model henüz yüklenmedi. Lütfen model dosyalarını kontrol edin.",
        )

    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Metin boş olamaz.")

    # ── Prediction cache kontrolü ──
    pred_cache_key = hashlib.md5(text.encode()).hexdigest()
    cached_prediction = await prediction_cache.get(pred_cache_key)
    if cached_prediction is not None:
        return cached_prediction

    # ── Otomatik çeviri (gerekirse) ──
    was_translated = not _is_english(text)
    english_text = await translate_to_english(text)

    # ── Vektörize et (CPU-bound → executor) ──
    loop = asyncio.get_event_loop()

    def _predict():
        text_vectorized = vectorizer.transform([english_text])
        pred = model.predict(text_vectorized)[0]
        try:
            probabilities = model.predict_proba(text_vectorized)[0]
            conf = float(np.max(probabilities))
        except AttributeError:
            conf = 1.0
        return pred, conf

    prediction_raw, confidence = await loop.run_in_executor(None, _predict)

    label = "spam" if prediction_raw == 1 else "ham"
    ui = _build_ui_fields(label, confidence)

    # Kullanıcı dostu mesaj
    if label == "spam":
        message = f"[SPAM] Bu e-posta SPAM olarak tespit edildi (Guven: %{confidence * 100:.1f})"
    else:
        message = f"[GUVENLI] Bu e-posta guvenli gorunuyor (Guven: %{confidence * 100:.1f})"

    response = PredictResponse(
        prediction=label,
        confidence=round(confidence, 4),
        message=message,
        color_tag=ui["color_tag"],
        status=ui["status"],
        translated=was_translated,
    )

    # Sonucu cache'le
    await prediction_cache.set(pred_cache_key, response)

    return response


# ─── Feedback Endpoint (Kullanıcı Geri Bildirimi) ────────────────────────────
FEEDBACK_FILE = os.path.join(os.path.dirname(__file__), "feedback_data.jsonl")


@app.post("/feedback", response_model=FeedbackResponse)
async def feedback(request: FeedbackRequest):
    """
    Kullanıcıdan gelen doğru/yanlış geri bildirimini kaydeder.
    Şüpheli (suspicious) tahminlerden geri bildirim kabul edilmez.
    Aynı kullanıcının aynı e-posta için mükerrer oy atması engellenir (SHA-256 ile).
    Veriler feedback_data.jsonl dosyasına JSONL formatında yazılır.
    """
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Metin boş olamaz.")

    # Şüpheli kategorisinden geri bildirim almıyoruz
    if request.prediction not in ("spam", "ham"):
        raise HTTPException(
            status_code=422,
            detail="Şüpheli kategorisindeki tahminlerden geri bildirim kabul edilmez.",
        )

    # Doğru etiket: kullanıcı onayladıysa modelin tahmini, reddettiyse tersi
    if request.is_correct:
        correct_label = request.prediction
    else:
        correct_label = "ham" if request.prediction == "spam" else "spam"

    # ── Kriptografik İmza ve Mükerrer Kontrolü (Gizlilik Korumalı) ──
    hash_input = f"{request.user_id}:{text}"
    vote_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

    loop = asyncio.get_event_loop()
    is_dup = await loop.run_in_executor(
        None,
        lambda: _is_duplicate_vote(vote_hash),
    )

    if is_dup:
        print(f"[FEEDBACK] Mükerrer oylama engellendi! (Gizlilik korumalı imza: {vote_hash[:12]}...)")
        return FeedbackResponse(
            status="duplicate",
            message="Bu e-posta için zaten geri bildirim gönderdiniz.",
        )

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "original_text": text,
        "model_prediction": request.prediction,
        "user_says_correct": request.is_correct,
        "correct_label": correct_label,
        "vote_hash": vote_hash,  # Log dosyasında user_id ASLA saklanmaz, sadece bu hash saklanır!
    }

    # JSONL dosyasına async yaz
    await loop.run_in_executor(
        None,
        lambda: _append_feedback(entry),
    )

    print(f"[FEEDBACK] {correct_label} <- kullanici {'onayladi' if request.is_correct else 'reddetti'} (model: {request.prediction})")

    return FeedbackResponse(
        status="ok",
        message="Geri bildiriminiz kaydedildi. Teşekkürler!",
    )


def _is_duplicate_vote(vote_hash: str) -> bool:
    """Aynı kullanıcının aynı e-postayı daha önce oylayıp oylamadığını kontrol eder (Gizlilik Korumalı)."""
    if not os.path.exists(FEEDBACK_FILE):
        return False

    with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json_module.loads(line)
                if entry.get("vote_hash") == vote_hash:
                    return True
            except Exception:
                continue
    return False


def _append_feedback(entry: dict):
    """Feedback verisini JSONL dosyasına ekler (thread-safe)."""
    with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
        f.write(json_module.dumps(entry, ensure_ascii=False) + "\n")


@app.get("/feedback/stats")
async def feedback_stats():
    """Toplanan geri bildirim verilerinin istatistiklerini döndürür."""
    if not os.path.exists(FEEDBACK_FILE):
        return {"total": 0, "correct": 0, "incorrect": 0, "accuracy": None}

    total = correct = incorrect = 0
    with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json_module.loads(line)
            total += 1
            if entry.get("user_says_correct"):
                correct += 1
            else:
                incorrect += 1

    return {
        "total": total,
        "correct": correct,
        "incorrect": incorrect,
        "accuracy": round(correct / total, 4) if total > 0 else None,
    }
