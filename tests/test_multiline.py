import sys
import io
import requests
import json
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API_URL = "http://127.0.0.1:8000/predict"

# ─── Test Metinleri (Alt Satır/Çoklu Satır İçerenler) ──────────────────────────
test_cases = [
    # ── Kullanıcının Verdiği Örnekler (3 Adet) ──────────────────────────────────
    {
        "id": 1,
        "lang": "EN",
        "expected": "spam",
        "desc": "Kullanıcı 1 — Sahte iş teklifi (Spam)",
        "text": """Hello,

We found your profile online and would like to offer you a high-paying remote job. No experience required.

To get started, please send your personal details and a small registration fee of $500."""
    },
    {
        "id": 2,
        "lang": "EN",
        "expected": "spam",
        "desc": "Kullanıcı 2 — Sahte Netflix askıya alma (Spam)",
        "text": """Dear Customer,

We were unable to process your monthly subscription payment. As a result, your Netflix account has been temporarily suspended.

To restore your service and continue watching, please update your payment details within 24 hours. Failure to do so will result in the permanent deletion of your profile history.

👉 UPDATE YOUR PAYMENT METHOD HERE

Thank you for being a loyal member.

The Netflix Team"""
    },
    {
        "id": 3,
        "lang": "EN",
        "expected": "spam",
        "desc": "Kullanıcı 3 — Piyango kazancı (Spam)",
        "text": """Dear Winner,

We are pleased to inform you that your email address has been selected as the winner of our international lottery. You have won $1,000,000 USD.

To claim your prize, please send your full name, address, and bank details immediately.

Congratulations once again!"""
    },

    # ── Eklenen Türkçe Örnekler (5 Adet) ───────────────────────────────────────
    {
        "id": 4,
        "lang": "TR",
        "expected": "spam",
        "desc": "Türkçe 1 — Kripto Yatırım Tuzağı (Spam)",
        "text": """Sayın Yatırımcı,

Kripto para piyasalarındaki benzersiz fırsatı kaçırmayın! Sadece bugün geçerli olmak üzere, yapacağınız 1000 TL yatırıma 5000 TL bonus kazanacaksınız.

Hemen aşağıdaki gizli linke tıklayın ve cüzdanınızı bağlayarak kazanmaya başlayın.

Kaçırmayın!"""
    },
    {
        "id": 5,
        "lang": "TR",
        "expected": "spam",
        "desc": "Türkçe 2 — Sahte Kargo Adres Güncelleme (Spam)",
        "text": """Sayın Müşterimiz,

Gönderiniz adres yetersizliği nedeniyle teslim edilememiştir. Paketinizi tekrar dağıtıma çıkarmak için lütfen adresinizi güncelleyin.

NOT: Güncelleme yapılmadığı takdirde paketiniz göndericiye iade edilecektir.

👉 ADRES GÜNCELLEME LİNKİ"""
    },
    {
        "id": 6,
        "lang": "TR",
        "expected": "ham",
        "desc": "Türkçe 3 — Proje İlerleme Toplantısı (Ham)",
        "text": """Merhaba Can Bey,

Yarın saat 14:00'te gerçekleştireceğimiz proje ilerleme toplantısının gündem maddelerini aşağıda görebilirsiniz:

- Yeni veritabanı entegrasyonu
- Eklenti arayüz revizyonları
- Performans testi raporu değerlendirmesi

Katılımınızı rica eder, iyi çalışmalar dilerim."""
    },
    {
        "id": 7,
        "lang": "TR",
        "expected": "ham",
        "desc": "Türkçe 4 — Dijital Fatura Bilgilendirmesi (Ham)",
        "text": """Değerli Abonemiz,

Mayıs 2026 dönemine ait dijital faturanız hazırlanmıştır.

Son Ödeme Tarihi: 05.06.2026
Toplam Tutar: 342.50 TL

Detaylı fatura dökümünüzü ekte yer alan PDF dosyasından veya online işlemler merkezinden inceleyebilirsiniz."""
    },
    {
        "id": 8,
        "lang": "TR",
        "expected": "spam",
        "desc": "Türkçe 5 — Sahte Alışveriş Hediye Çeki (Spam)",
        "text": """TEBRİKLER!

Migros'tan 2.000 TL değerinde alışveriş çeki kazandınız! Çekin aktif olması için yapmanız gereken tek şey aşağıdaki ankete katılmak.

Ankete Gitmek İçin Tıklayın:
[Link]

Bu kampanya sınırlı sayıdadır, acele edin!"""
    },

    # ── Eklenen İngilizce Örnekler (5 Adet) ────────────────────────────────────
    {
        "id": 9,
        "lang": "EN",
        "expected": "spam",
        "desc": "İngilizce 1 — Miras/Para Transferi Tuzağı (Spam)",
        "text": """Değerli Alıcı / Dear Beneficiary,

I am writing to you regarding the estate left behind by my late client. There is an unclaimed fund of $10.5 Million USD in his bank account.

Since you share the same last name, I can present you as the next of kin to claim these funds.

Please reply to this email with your secret details to proceed."""
    },
    {
        "id": 10,
        "lang": "EN",
        "expected": "spam",
        "desc": "İngilizce 2 — Sahte PayPal Hesap Kısıtlaması (Spam)",
        "text": """Urgent Security Alert!

We detected an unauthorized login attempt to your PayPal account from an unrecognized IP address. For your safety, your account has been temporarily restricted.

To unlock your account, click the link below and verify your security questions:

[Secure Login Link]"""
    },
    {
        "id": 11,
        "lang": "EN",
        "expected": "ham",
        "desc": "İngilizce 3 — Geliştirici Pull Request Bildirimi (Ham)",
        "text": """Hey team,

I just opened a new pull request for the translation cache optimizations. It includes:
- Asynchronous cache lookups
- Safe error fallbacks for GoogleTranslator
- Standardizing lowercase text comparison

Please review and merge if it looks good. Thanks!"""
    },
    {
        "id": 12,
        "lang": "EN",
        "expected": "ham",
        "desc": "İngilizce 4 — Otel Rezervasyon Onayı (Ham)",
        "text": """Booking Confirmation

Dear Traveler,
Your reservation at the Grand Plaza Hotel has been confirmed.

Check-in: June 10, 2026 - 14:00
Check-out: June 15, 2026 - 11:00

Thank you for choosing our service. Have a wonderful stay!"""
    },
    {
        "id": 13,
        "lang": "EN",
        "expected": "spam",
        "desc": "İngilizce 5 — Kripto Airdrop Ödül Dağıtımı (Spam)",
        "text": """EXCLUSIVE AIRDROP EVENT!

To celebrate our 5th anniversary, we are giving away 0.5 BTC to 100 lucky users. You are one of the selected winners!

Claim your Bitcoin now by transferring a minimum deposit of 0.01 BTC to verify your wallet address.

Register here: [link]"""
    },
]

def run_multiline_tests():
    print("=" * 90)
    print("  SPAM FILTER API — COKLU SATIR VE ALT SATIR TEST SUITI  ")
    print("=" * 90)

    results = []
    success_count = 0

    for tc in test_cases:
        start = time.time()
        try:
            r = requests.post(API_URL, json={"text": tc["text"]}, timeout=30)
            elapsed = (time.time() - start) * 1000
            data = r.json()

            pred = data.get("prediction")
            is_correct = (pred == tc["expected"])
            if is_correct:
                success_count += 1

            results.append({
                "id": tc["id"],
                "lang": tc["lang"],
                "desc": tc["desc"],
                "expected": tc["expected"],
                "prediction": pred,
                "confidence": data.get("confidence"),
                "status": data.get("status"),
                "translated": data.get("translated"),
                "is_correct": is_correct,
                "time_ms": round(elapsed),
            })
        except Exception as e:
            results.append({
                "id": tc["id"],
                "lang": tc["lang"],
                "desc": tc["desc"],
                "expected": tc["expected"],
                "error": str(e),
            })

    # ─── Sonuçları Tablo Olarak Yazdır ────────────────────────────────────
    print()
    header = f"{'#':<3} {'Dil':<4} {'Beklenen':<8} {'Tahmin':<6} {'Güven':>7} {'Çeviri':<7} {'Sonuç':<6} {'Süre':>7}  Açıklama"
    print(header)
    print("─" * len(header) + "─" * 20)

    for r in results:
        if "error" in r:
            print(f"{r['id']:<3} {r['lang']:<4} {r['expected']:<8} {'HATA':<6} {'—':>7} {'—':<7} {'BAŞARISIZ':<6} {'—':>7}  {r['desc']}")
            print(f"    └─ Hata: {r['error']}")
        else:
            conf_str = f"%{r['confidence']*100:.1f}"
            trans_str = "Evet" if r["translated"] else "Hayır"
            status_str = "BAŞARILI" if r["is_correct"] else "HATALI"
            print(
                f"{r['id']:<3} {r['lang']:<4} {r['expected']:<8} {r['prediction']:<6} {conf_str:>7} "
                f"{trans_str:<7} {status_str:<6} {r['time_ms']:>5}ms  {r['desc']}"
            )

    print("─" * len(header) + "─" * 20)
    accuracy = (success_count / len(test_cases)) * 100
    print(f"\nSonuç: {len(test_cases)} testten {success_count} tanesi BAŞARILI. Doğruluk Oranı: %{accuracy:.1f}")
    print()

if __name__ == "__main__":
    run_multiline_tests()
