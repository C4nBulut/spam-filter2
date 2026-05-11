"""
Spam Filter API -- Test Script
10 farkli metin ile /predict endpoint'ini test eder.
5 Turkce + 5 Ingilizce metin.
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests
import json
import time

API_URL = "http://localhost:8000/predict"

# ─── Test Metinleri ──────────────────────────────────────────────────────────
test_cases = [
    # ── Türkçe Metinler (5) ──────────────────────────────────────────────────
    {
        "id": 1,
        "lang": "TR",
        "desc": "Türkçe — Toplantı daveti (ham beklenir)",
        "text": "Merhaba, şirketimizin aylık değerlendirme toplantısı önümüzdeki Perşembe günü saat 10:00'da yapılacaktır. Gündem maddelerini ekte bulabilirsiniz. Katılımınız önemlidir, lütfen takvimlerinizi ayarlayın."
    },
    {
        "id": 2,
        "lang": "TR",
        "desc": "Türkçe — Spam ödül tuzağı (spam beklenir)",
        "text": "TEBRİKLER! 500.000 TL değerinde büyük ödülü kazandınız! Ödülünüzü almak için hemen şimdi bu linke tıklayın ve kişisel bilgilerinizi girin. Bu fırsat sadece 24 saat geçerlidir, acele edin!"
    },
    {
        "id": 3,
        "lang": "TR",
        "desc": "Türkçe — İş başvurusu yanıtı (ham beklenir)",
        "text": "Sayın başvuru sahibi, iş başvurunuz tarafımıza ulaşmıştır. Başvurunuz insan kaynakları departmanımız tarafından değerlendirilmektedir. Süreç hakkında sizi bilgilendireceğiz. İyi günler dileriz."
    },
    {
        "id": 4,
        "lang": "TR",
        "desc": "Türkçe — Sahte banka uyarısı (spam beklenir)",
        "text": "DİKKAT! Banka hesabınıza yetkisiz giriş tespit edildi. Hesabınızın güvenliği için derhal şifrenizi sıfırlayın. Aşağıdaki bağlantıya tıklayarak kimliğinizi doğrulayın, aksi halde hesabınız 48 saat içinde kapatılacaktır."
    },
    {
        "id": 5,
        "lang": "TR",
        "desc": "Türkçe — Proje güncellemesi (ham beklenir)",
        "text": "Merhabalar, geçen haftaki sprint kapanışında belirlenen görevlerin durumunu paylaşıyorum. Frontend tarafında tasarım revizyonları tamamlandı. Backend API entegrasyonu test aşamasında. Bir sorun yaşarsanız Jira üzerinden bildirim oluşturabilirsiniz."
    },

    # ── İngilizce Metinler (5) ───────────────────────────────────────────────
    {
        "id": 6,
        "lang": "EN",
        "desc": "English — Meeting follow-up (ham expected)",
        "text": "Hi team, just following up on our discussion from yesterday's meeting. I've attached the updated project timeline and the revised budget proposal. Please review and share your feedback by Friday. Let me know if you have any questions."
    },
    {
        "id": 7,
        "lang": "EN",
        "desc": "English — Lottery scam (spam expected)",
        "text": "CONGRATULATIONS!!! You have been selected as the winner of our $1,000,000 international lottery! To claim your prize, reply immediately with your full name, address, and bank account details. This offer expires in 24 hours. Act now!"
    },
    {
        "id": 8,
        "lang": "EN",
        "desc": "English — Newsletter (ham expected)",
        "text": "Hi there, here is your weekly tech digest. This week we cover the latest advances in machine learning, a deep dive into microservices architecture, and tips for writing clean Python code. Happy reading and see you next week!"
    },
    {
        "id": 9,
        "lang": "EN",
        "desc": "English — Phishing email (spam expected)",
        "text": "URGENT: Your account has been compromised! Click the link below to verify your identity and secure your account immediately. Failure to act within 12 hours will result in permanent suspension. Verify now: http://totally-legit-bank.xyz/login"
    },
    {
        "id": 10,
        "lang": "EN",
        "desc": "English — Colleague message (ham expected)",
        "text": "Hey, I just pushed the latest changes to the develop branch. Can you take a look at the pull request when you get a chance? I refactored the authentication module and added unit tests. Let me know if anything looks off."
    },
]

# ─── Test Çalıştırıcı ────────────────────────────────────────────────────────
def run_tests():
    print("=" * 80)
    print("  SPAM FILTER API — TEST SUITE  (5 TR + 5 EN)")
    print("=" * 80)

    results = []

    for tc in test_cases:
        start = time.time()
        try:
            r = requests.post(API_URL, json={"text": tc["text"]}, timeout=30)
            elapsed = (time.time() - start) * 1000
            data = r.json()

            results.append({
                "id": tc["id"],
                "lang": tc["lang"],
                "desc": tc["desc"],
                "status_code": r.status_code,
                "prediction": data.get("prediction"),
                "confidence": data.get("confidence"),
                "color_tag": data.get("color_tag"),
                "status": data.get("status"),
                "translated": data.get("translated"),
                "time_ms": round(elapsed),
            })
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            results.append({
                "id": tc["id"],
                "lang": tc["lang"],
                "desc": tc["desc"],
                "error": str(e),
                "time_ms": round(elapsed),
            })

    # ─── Sonuçları Tablo Olarak Yazdır ────────────────────────────────────
    print()
    header = f"{'#':<3} {'Dil':<4} {'Tahmin':<6} {'Güven':>7} {'Renk':<8} {'Durum':<12} {'Çeviri':<7} {'Süre':>7}  Açıklama"
    print(header)
    print("─" * len(header) + "─" * 20)

    for r in results:
        if "error" in r:
            print(f"{r['id']:<3} {r['lang']:<4} {'HATA':<6} {'—':>7} {'—':<8} {'—':<12} {'—':<7} {r['time_ms']:>5}ms  {r['desc']}")
            print(f"    └─ Hata: {r['error']}")
        else:
            conf_str = f"%{r['confidence']*100:.1f}"
            trans_str = "Evet" if r["translated"] else "Hayır"
            print(
                f"{r['id']:<3} {r['lang']:<4} {r['prediction']:<6} {conf_str:>7} "
                f"{r['color_tag']:<8} {r['status']:<12} {trans_str:<7} "
                f"{r['time_ms']:>5}ms  {r['desc']}"
            )

    print("─" * len(header) + "─" * 20)
    print(f"\nToplam: {len(results)} test tamamlandı.")
    print()


if __name__ == "__main__":
    run_tests()
