# Spam Filter API — üretim (konteyner) imajı
# Python 3.12: scikit-learn 1.5.2 ve model dosyaları için wheel uyumu garanti.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# Sağlık kontrolü ve hata ayıklama için minimal araçlar
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Önce bağımlılıklar (katman önbelleği için)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama kodu ve model dosyaları
COPY . .

# Root olmayan kullanıcı (Render/Koyeb/Cloud Run uyumlu)
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/" || exit 1

# Platformlar PORT değişkenini kendileri atar; yerelde 8000'e düşer.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
