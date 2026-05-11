"""
Spam Filter API — FastAPI Backend
Eğitilmiş Naive Bayes modelini servis olarak sunar.
POST /predict endpoint'i ile metin alır, spam/ham tahmini ve güven oranı döndürür.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import joblib
import os
import numpy as np

# ─── Uygulama ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Spam Filter API",
    description="Gmail Spam Filtresi Chrome Eklentisi için tahmin API'si",
    version="1.0.0",
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

# ─── Request / Response Şemaları ─────────────────────────────────────────────
class PredictRequest(BaseModel):
    text: str

class PredictResponse(BaseModel):
    prediction: str          # "spam" veya "ham"
    confidence: float        # 0.0 – 1.0 arası güven oranı
    message: str             # Kullanıcıya gösterilecek açıklama

# ─── Endpoint'ler ────────────────────────────────────────────────────────────
@app.get("/")
def root():
    """API sağlık kontrolü."""
    return {"status": "ok", "message": "Spam Filter API calisiyor"}


@app.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest):
    """
    Gelen metni vektörize et, model ile tahmin yap.
    Sonuç olarak spam/ham etiketi ve güven oranını döndür.
    """
    if model is None or vectorizer is None:
        raise HTTPException(
            status_code=503,
            detail="Model henüz yüklenmedi. Lütfen model dosyalarını kontrol edin.",
        )

    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Metin boş olamaz.")

    # Vektörize et
    text_vectorized = vectorizer.transform([text])

    # Tahmin
    prediction = model.predict(text_vectorized)[0]
    label = "spam" if prediction == 1 else "ham"

    # Güven oranı (predict_proba destekliyorsa)
    try:
        probabilities = model.predict_proba(text_vectorized)[0]
        confidence = float(np.max(probabilities))
    except AttributeError:
        confidence = 1.0  # predict_proba yoksa varsayılan

    # Kullanıcı dostu mesaj
    if label == "spam":
        message = f"[SPAM] Bu e-posta SPAM olarak tespit edildi (Guven: %{confidence * 100:.1f})"
    else:
        message = f"[GUVENLI] Bu e-posta guvenli gorunuyor (Guven: %{confidence * 100:.1f})"

    return PredictResponse(
        prediction=label,
        confidence=round(confidence, 4),
        message=message,
    )
