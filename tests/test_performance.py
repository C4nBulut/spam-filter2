import sys
import io
import time
import asyncio
import httpx
import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API_URL = "http://127.0.0.1:8000/predict"

# Farklı metinler (Cache Miss senaryosu için)
texts = [
    "Meeting reminder: Today's design sync is scheduled at 4 PM in room 3B.",
    "URGENT: Click here to claim your immediate reward of $5,000 before it expires!",
    "Hi Can, did you review the pull request for the spam filter database integration?",
    "Get rich quick! No experience needed, start making thousands from home now.",
    "The translation layer handles non-English emails asynchronously with caching.",
    "Your parcel has been delivered to the local post office. Pick it up within 3 days.",
    "Let's grab a coffee tomorrow morning and discuss the pipeline architecture.",
    "ALERT: Suspicious activity detected on your credit card. Login to confirm.",
    "The new Multinomial Naive Bayes model has a larger vocabulary and higher accuracy.",
    "Please find attached the slides for the security audit presentation."
]

async def measure_single(client: httpx.AsyncClient, text: str):
    start = time.perf_counter()
    try:
        response = await client.post(API_URL, json={"text": text}, timeout=10.0)
        elapsed = (time.perf_counter() - start) * 1000.0
        return response.status_code, elapsed, response.json().get("translated", False)
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000.0
        return 0, elapsed, False

async def run_benchmark():
    print("Spam Filter API Hız ve Performans Testi Başlatılıyor...\n")
    
    async with httpx.AsyncClient() as client:
        # Sunucunun açık olduğundan emin ol
        try:
            test_resp = await client.get("http://127.0.0.1:8000/")
            if test_resp.status_code != 200:
                print("[HATA] API sunucusu çalışıyor ancak geçersiz yanıt veriyor.")
                return
        except Exception:
            print("[HATA] API sunucusu aktif değil. Lütfen önce backend sunucusunu başlatın.")
            return

        # ─── 1. CACHE MISS (Yeni İstekler - Çeviri ve Tahmin Dahil) ───
        print("1. CACHE MISS (Yeni İstekler - Sıralı) Ölçülüyor...")
        cache_miss_times = []
        for i in range(20):
            text = f"{texts[i % len(texts)]} [unique id: {i}]"  # Cache'e girmemesi için benzersiz yapıyoruz
            status, elapsed, translated = await measure_single(client, text)
            if status == 200:
                cache_miss_times.append(elapsed)
            await asyncio.sleep(0.05)  # Sunucuyu yormamak için ufak bekleme
        
        # ─── 2. CACHE HIT (Tekrarlanan İstekler) ───
        print("2. CACHE HIT (Tekrarlanan İstekler - Sıralı) Ölçülüyor...")
        cache_hit_times = []
        static_text = "This is a static email text for checking cache hit latency."
        # İlk istek cache'lensin
        await measure_single(client, static_text)
        
        for _ in range(30):
            status, elapsed, _ = await measure_single(client, static_text)
            if status == 200:
                cache_hit_times.append(elapsed)
            await asyncio.sleep(0.01)

        # ─── 3. EŞZAMANLI / CONCURRENT İSTEKLER (Yük Testi) ───
        print("3. EŞZAMANLI YÜK TESTİ (Concurrent Clients) Ölçülüyor...")
        concurrent_times = []
        tasks = []
        for i in range(40):
            text = f"Concurrent email sample {i} for stress test purposes."
            tasks.append(measure_single(client, text))
        
        start_concurrent = time.perf_counter()
        results = await asyncio.gather(*tasks)
        total_concurrent_time = (time.perf_counter() - start_concurrent) * 1000.0
        
        for status, elapsed, _ in results:
            if status == 200:
                concurrent_times.append(elapsed)

    # ─── İstatistikleri Hesaplama ───
    def get_stats(times):
        if not times:
            return {k: 0.0 for k in ["mean", "min", "max", "p95", "p99", "std"]}
        arr = np.array(times)
        return {
            "mean": np.mean(arr),
            "min": np.min(arr),
            "max": np.max(arr),
            "p95": np.percentile(arr, 95),
            "p99": np.percentile(arr, 99),
            "std": np.std(arr)
        }

    miss_stats = get_stats(cache_miss_times)
    hit_stats = get_stats(cache_hit_times)
    concur_stats = get_stats(concurrent_times)
    throughput = (len(concurrent_times) / (total_concurrent_time / 1000.0)) if total_concurrent_time > 0 else 0.0

    # ─── Rapor Çıktısı Hazırlama ───
    report = f"""======================================================================
                 SPAM FILTER API HIZ VE PERFORMANS TESTİ RAPORU
======================================================================
Tarih/Saat      : {time.strftime('%Y-%m-%d %H:%M:%S')}
Test Edilen URL : {API_URL}
Model Sürümü    : v2.4.6 (Yeni Multinomial Naive Bayes)

----------------------------------------------------------------------
1. CACHE MISS PERFORMANSI (Sıralı 20 Yeni İstek - Çeviri/NLP Aktif)
----------------------------------------------------------------------
Başarılı İstek : {len(cache_miss_times)} / 20
Ortalama Süre  : {miss_stats['mean']:.2f} ms
Minimum Süre   : {miss_stats['min']:.2f} ms
Maksimum Süre  : {miss_stats['max']:.2f} ms
95. Yüzdelik (p95): {miss_stats['p95']:.2f} ms
99. Yüzdelik (p99): {miss_stats['p99']:.2f} ms
Standart Sapma : {miss_stats['std']:.2f} ms

----------------------------------------------------------------------
2. CACHE HIT PERFORMANSI (Sıralı 30 Tekrarlanan İstek - Önbellekten)
----------------------------------------------------------------------
Başarılı İstek : {len(cache_hit_times)} / 30
Ortalama Süre  : {hit_stats['mean']:.2f} ms
Minimum Süre   : {hit_stats['min']:.2f} ms
Maksimum Süre  : {hit_stats['max']:.2f} ms
95. Yüzdelik (p95): {hit_stats['p95']:.2f} ms
99. Yüzdelik (p99): {hit_stats['p99']:.2f} ms
Standart Sapma : {hit_stats['std']:.2f} ms
Hız Artışı     : {miss_stats['mean'] / hit_stats['mean']:.1f}x Kat Daha Hızlı! (Cache Sayesinde)

----------------------------------------------------------------------
3. EŞZAMANLI YÜK TESTİ (40 Paralel İstek)
----------------------------------------------------------------------
Başarılı İstek : {len(concurrent_times)} / 40
Toplam Süre    : {total_concurrent_time:.2f} ms
İstek/Saniye   : {throughput:.2f} rps (Throughput)
Ortalama Süre  : {concur_stats['mean']:.2f} ms
Minimum Süre   : {concur_stats['min']:.2f} ms
Maksimum Süre  : {concur_stats['max']:.2f} ms
95. Yüzdelik (p95): {concur_stats['p95']:.2f} ms
99. Yüzdelik (p99): {concur_stats['p99']:.2f} ms

$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
"""

    print(report)

    # Sonuçları dosyaya yaz
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(script_dir)
    output_filepath = os.path.join(parent_dir, "tests", "speed_test_results.txt")
    file_exists = os.path.exists(output_filepath) and os.path.getsize(output_filepath) > 0
    with open(output_filepath, "a", encoding="utf-8") as f:
        if file_exists:
            f.write("\n\n" + "=" * 70 + "\n\n")
        f.write(report)
    print(f"\n[OK] Sonuçlar başarıyla '{output_filepath}' dosyasına yazıldı.")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
