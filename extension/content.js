/**
 * Gmail Spam Filtresi — Content Script
 * ─────────────────────────────────────
 * Gmail sayfasına bir "Spam Kontrolü" butonu ekler.
 * Butona tıklanınca açık e-postanın metnini alır,
 * FastAPI backend'ine gönderir ve sonucu toast bildirim olarak gösterir.
 */

const API_URL = "http://localhost:8000/predict";

// ═══════════════════════════════════════════════════════════════════════════
// 1. BUTON OLUŞTURMA
// ═══════════════════════════════════════════════════════════════════════════
function createSpamButton() {
  // Zaten varsa tekrar oluşturma
  if (document.getElementById("spam-filter-btn")) return;

  const btn = document.createElement("button");
  btn.id = "spam-filter-btn";
  btn.innerHTML = `<span class="btn-icon">🛡️</span> Spam Kontrolü`;
  btn.addEventListener("click", handleSpamCheck);

  document.body.appendChild(btn);
  console.log("[Spam Filtresi] Buton eklendi ✅");
}

// ═══════════════════════════════════════════════════════════════════════════
// 2. E-POSTA İÇERİĞİNİ DOM'DAN ALMA
// ═══════════════════════════════════════════════════════════════════════════
/**
 * Gmail'deki açık e-posta gövdesini yakalamaya çalışır.
 * Gmail dinamik olduğu için birden fazla seçici denenir.
 * @returns {string|null} E-posta metni veya null
 */
function getActiveEmailBody() {
  // Gmail'in kullandığı bilinen CSS seçicileri (öncelik sırasına göre)
  const selectors = [
    "div.a3s.aiL",          // Ana e-posta gövdesi (genişletilmiş)
    "div.a3s",              // Ana e-posta gövdesi
    "div.ii.gt",            // Alternatif gövde seçici
    "div.adn .ads",         // Başka bir alternatif
    "div[data-message-id]", // Mesaj ID'si olan div
  ];

  for (const selector of selectors) {
    const elements = document.querySelectorAll(selector);
    if (elements.length > 0) {
      // Son açılan e-postayı al (birden fazla varsa en alttaki)
      const lastElement = elements[elements.length - 1];
      const text = lastElement.innerText || lastElement.textContent;
      if (text && text.trim().length > 0) {
        console.log(`[Spam Filtresi] E-posta bulundu (seçici: ${selector})`);
        return text.trim();
      }
    }
  }

  console.warn("[Spam Filtresi] Açık e-posta bulunamadı.");
  return null;
}

// ═══════════════════════════════════════════════════════════════════════════
// 3. TOAST BİLDİRİM SİSTEMİ
// ═══════════════════════════════════════════════════════════════════════════
/**
 * Toast bildirim gösterir (alert yerine modern bildirim).
 * @param {"spam"|"ham"|"error"|"info"} type — Bildirim tipi
 * @param {string} title — Başlık
 * @param {string} body — Açıklama metni
 * @param {number} [confidence] — Güven oranı (0-1), opsiyonel
 */
function showToast(type, title, body, confidence) {
  // Eski toast'ı kaldır
  const existing = document.getElementById("spam-filter-toast");
  if (existing) existing.remove();

  const toast = document.createElement("div");
  toast.id = "spam-filter-toast";
  toast.classList.add(`toast-${type}`);

  // İkon seçimi
  const icons = { spam: "🚫", ham: "✅", error: "⚠️", info: "ℹ️", suspicious: "🟡" };
  const icon = icons[type] || "ℹ️";

  let html = `
    <div class="toast-title">${icon} ${title}</div>
    <div class="toast-body">${body}</div>
  `;

  // Güven çubuğu (varsa)
  if (typeof confidence === "number") {
    html += `
      <div class="confidence-bar-track">
        <div class="confidence-bar-fill" style="width: 0%"></div>
      </div>
    `;
  }

  toast.innerHTML = html;
  document.body.appendChild(toast);

  // Animasyonu tetikle
  requestAnimationFrame(() => {
    toast.classList.add("visible");

    // Güven çubuğu animasyonu
    if (typeof confidence === "number") {
      const fill = toast.querySelector(".confidence-bar-fill");
      if (fill) {
        setTimeout(() => {
          fill.style.width = `${(confidence * 100).toFixed(0)}%`;
        }, 100);
      }
    }
  });

  // 5 saniye sonra otomatik kapat
  setTimeout(() => {
    toast.classList.remove("visible");
    setTimeout(() => toast.remove(), 400);
  }, 5000);
}

// ═══════════════════════════════════════════════════════════════════════════
// 4. SPAM KONTROL FONKSİYONU (FETCH İLE API ÇAĞRISI)
// ═══════════════════════════════════════════════════════════════════════════
async function handleSpamCheck() {
  const btn = document.getElementById("spam-filter-btn");

  // ── E-posta metnini al ──
  const emailText = getActiveEmailBody();

  if (!emailText) {
    showToast(
      "info",
      "E-posta Bulunamadı",
      "Lütfen önce bir e-posta açın ve tekrar deneyin."
    );
    return;
  }

  console.log(
    `[Spam Filtresi] Metin alındı (${emailText.length} karakter). API'ye gönderiliyor…`
  );

  // ── Yükleme durumu ──
  btn.classList.add("loading");
  btn.innerHTML = `<span class="btn-icon">⏳</span> Analiz ediliyor…`;

  try {
    // ── API çağrısı ──
    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: emailText }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      throw new Error(
        errorData?.detail || `HTTP ${response.status}: Sunucu hatası`
      );
    }

    const data = await response.json();

    // ── Sonucu göster (dinamik UI: color_tag & status desteği) ──
    const translatedNote = data.translated ? " (Otomatik çeviri yapıldı)" : "";

    if (data.status === "suspicious") {
      showToast(
        "suspicious",
        "Şüpheli E-posta",
        `Bu e-posta şüpheli olarak değerlendirildi.\nGüven: %${(data.confidence * 100).toFixed(1)}${translatedNote}`,
        data.confidence
      );
    } else if (data.prediction === "spam") {
      showToast(
        "spam",
        "SPAM Tespit Edildi!",
        `Bu e-posta spam olarak sınıflandırıldı.\nGüven: %${(data.confidence * 100).toFixed(1)}${translatedNote}`,
        data.confidence
      );
    } else {
      showToast(
        "ham",
        "Güvenli E-posta",
        `Bu e-posta güvenli görünüyor.\nGüven: %${(data.confidence * 100).toFixed(1)}${translatedNote}`,
        data.confidence
      );
    }

    console.log("[Spam Filtresi] Sonuç:", data);
  } catch (error) {
    console.error("[Spam Filtresi] Hata:", error);

    // Kullanıcıya anlaşılır hata mesajı
    let errorMsg = error.message;
    if (error.message.includes("Failed to fetch") || error.message.includes("NetworkError")) {
      errorMsg = "API sunucusuna bağlanılamıyor. FastAPI'nin çalıştığından emin olun (localhost:8000).";
    }

    showToast("error", "Bağlantı Hatası", errorMsg);
  } finally {
    // ── Butonu eski haline döndür ──
    btn.classList.remove("loading");
    btn.innerHTML = `<span class="btn-icon">🛡️</span> Spam Kontrolü`;
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// 5. BAŞLATMA
// ═══════════════════════════════════════════════════════════════════════════
// Gmail SPA olduğu için sayfa yüklendikten sonra butonu ekle
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", createSpamButton);
} else {
  createSpamButton();
}

// Gmail'de sayfa içi navigasyon olduğunda butonun kaybolmaması için gözlemle
const observer = new MutationObserver(() => {
  if (!document.getElementById("spam-filter-btn")) {
    createSpamButton();
  }
});

observer.observe(document.body, { childList: true, subtree: true });
