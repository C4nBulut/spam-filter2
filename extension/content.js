/**
 * Gmail Spam Filtresi — Content Script
 * ─────────────────────────────────────
 * Gmail sayfasına bir "Spam Kontrolü" butonu ekler.
 * Butona tıklanınca açık e-postanın metnini alır,
 * FastAPI backend'ine gönderir ve sonucu toast bildirim olarak gösterir.
 */

const API_URL = "http://localhost:8000/predict";
const FEEDBACK_URL = "http://localhost:8000/feedback";

// ─── Kullanıcı Ayarları ─────────────────────────────────────────────────────
let userSettings = {
  collectData: false, // Varsayılan: kapalı
};

/** chrome.storage'dan ayarları yükle */
function loadSettings() {
  if (typeof chrome !== "undefined" && chrome.storage) {
    chrome.storage.sync.get({ collectData: false }, (result) => {
      userSettings.collectData = result.collectData;
      console.log("[Spam Filtresi] Ayarlar yüklendi:", userSettings);
    });

    // Ayar değiştiğinde (popup'tan) anlık güncelle
    chrome.storage.onChanged.addListener((changes) => {
      if (changes.collectData) {
        userSettings.collectData = changes.collectData.newValue;
        console.log(`[Spam Filtresi] Veri toplama: ${userSettings.collectData ? "Açık" : "Kapalı"}`);
      }
    });
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// 1. SÜRÜKLENEBİLİR BUTON (kenar yapışmalı)
// ═══════════════════════════════════════════════════════════════════════════
function createSpamButton() {
  // Zaten varsa tekrar oluşturma
  if (document.getElementById("spam-filter-btn")) return;

  const btn = document.createElement("button");
  btn.id = "spam-filter-btn";
  btn.innerHTML = `<span class="btn-icon">🛡️</span>`;

  // ── Sürükleme değişkenleri ──
  let isDragging = false;
  let wasDragged = false;
  let startX, startY, startLeft, startTop;

  // Önceki konumu yükle
  if (typeof chrome !== "undefined" && chrome.storage) {
    chrome.storage.local.get({ btnPosition: null }, (res) => {
      if (res.btnPosition) {
        btn.style.left = res.btnPosition.left;
        btn.style.top = res.btnPosition.top;
        btn.style.right = "auto";
        btn.style.bottom = "auto";
      }
    });
  }

  btn.addEventListener("pointerdown", (e) => {
    isDragging = true;
    wasDragged = false;
    startX = e.clientX;
    startY = e.clientY;

    const rect = btn.getBoundingClientRect();
    startLeft = rect.left;
    startTop = rect.top;

    btn.setPointerCapture(e.pointerId);
    btn.classList.add("dragging");
    e.preventDefault();
  });

  btn.addEventListener("pointermove", (e) => {
    if (!isDragging) return;

    const dx = e.clientX - startX;
    const dy = e.clientY - startY;

    if (Math.abs(dx) > 5 || Math.abs(dy) > 5) {
      wasDragged = true;
    }

    // Serbest hareket (sürükleme sırasında)
    const btnW = btn.offsetWidth;
    const btnH = btn.offsetHeight;
    let newLeft = Math.max(0, Math.min(window.innerWidth - btnW, startLeft + dx));
    let newTop = Math.max(0, Math.min(window.innerHeight - btnH, startTop + dy));

    btn.style.left = `${newLeft}px`;
    btn.style.top = `${newTop}px`;
    btn.style.right = "auto";
    btn.style.bottom = "auto";
  });

  btn.addEventListener("pointerup", (e) => {
    if (!isDragging) return;
    isDragging = false;
    btn.classList.remove("dragging");
    btn.releasePointerCapture(e.pointerId);

    if (!wasDragged) {
      // Sürüklenmediyse → tıklama
      handleSpamCheck();
    } else {
      // Sürüklendiyse → en yakın kenara yapıştır
      snapToEdge(btn);
    }
  });

  document.body.appendChild(btn);
  console.log("[Spam Filtresi] Buton eklendi ✅");
}

/**
 * Butonu en yakın yatay kenara (sol/sağ) animasyonlu yapıştırır.
 * Dikey pozisyon korunur, sadece ekran sınırları içinde tutulur.
 */
function snapToEdge(btn) {
  const rect = btn.getBoundingClientRect();
  const centerX = rect.left + rect.width / 2;
  const viewW = window.innerWidth;
  const margin = 12; // Kenardan boşluk

  // Dikey sınır kontrolü
  let top = Math.max(margin, Math.min(window.innerHeight - rect.height - margin, rect.top));

  // Yatay: ekranın ortasına göre sol veya sağ kenara yapış
  if (centerX < viewW / 2) {
    btn.style.left = `${margin}px`;
  } else {
    btn.style.left = `${viewW - rect.width - margin}px`;
  }

  btn.style.top = `${top}px`;
  btn.style.right = "auto";
  btn.style.bottom = "auto";

  // Konumu kaydet
  if (typeof chrome !== "undefined" && chrome.storage) {
    chrome.storage.local.set({
      btnPosition: {
        left: btn.style.left,
        top: btn.style.top
      }
    });
  }
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
 * Tıklanınca erken kapatılabilir.
 * @param {"spam"|"ham"|"error"|"info"|"suspicious"} type — Bildirim tipi
 * @param {string} title — Başlık
 * @param {string} body — Açıklama metni
 * @param {number} [confidence] — Güven oranı (0-1), opsiyonel
 * @param {object} [feedbackData] — Geri bildirim verisi (varsa 👍👎 butonları eklenir)
 */
function showToast(type, title, body, confidence, feedbackData) {
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

  // Geri bildirim butonları (ayar açık + şüpheli değil)
  const showFeedback = feedbackData && userSettings.collectData;
  if (showFeedback) {
    html += `
      <div class="feedback-section">
        <span class="feedback-label">Tahmin doğru mu?</span>
        <div class="feedback-buttons">
          <button class="feedback-btn feedback-up" data-correct="true" title="Evet, doğru">👍</button>
          <button class="feedback-btn feedback-down" data-correct="false" title="Hayır, yanlış">👎</button>
        </div>
      </div>
    `;
  }

  toast.innerHTML = html;
  document.body.appendChild(toast);

  // Geri bildirim buton event'leri
  if (showFeedback) {
    toast.querySelectorAll(".feedback-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation(); // Toast'ın kapanmasını engelle
        const isCorrect = e.currentTarget.dataset.correct === "true";
        sendFeedback(feedbackData.text, feedbackData.prediction, isCorrect, toast);
      });
    });
  }

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

  // Feedback varsa 20sn, yoksa 5sn sonra otomatik kapat
  const dismissDelay = showFeedback ? 20000 : 5000;
  const autoCloseTimer = setTimeout(() => {
    dismissToast(toast);
  }, dismissDelay);

  toast._autoCloseTimer = autoCloseTimer;

  // ── Tıklayınca erken kapat ──
  toast.addEventListener("click", (e) => {
    if (e.target.closest(".feedback-btn")) return;
    clearTimeout(toast._autoCloseTimer);
    dismissToast(toast);
  });
}

/** Toast'ı animasyonlu kapat */
function dismissToast(toast) {
  if (!toast || !toast.parentNode) return;
  toast.classList.remove("visible");
  setTimeout(() => toast.remove(), 400);
}

// ═══════════════════════════════════════════════════════════════════════════
// 3b. GERİ BİLDİRİM FONKSİYONU
// ═══════════════════════════════════════════════════════════════════════════
/**
 * Kullanıcı geri bildirimini backend'e gönderir.
 * @param {string} text — Orijinal e-posta metni
 * @param {string} prediction — Modelin tahmini
 * @param {boolean} isCorrect — Kullanıcı onayı
 * @param {HTMLElement} toast — Toast elementi (güncelleme için)
 */
async function sendFeedback(text, prediction, isCorrect, toast) {
  // Butonları devre dışı bırak
  const buttons = toast.querySelectorAll(".feedback-btn");
  buttons.forEach((btn) => (btn.disabled = true));

  try {
    const response = await fetch(FEEDBACK_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, prediction, is_correct: isCorrect }),
    });

    if (!response.ok) throw new Error("Feedback gönderilemedi");

    // Butonları geri bildirim mesajıyla değiştir
    const section = toast.querySelector(".feedback-section");
    if (section) {
      section.innerHTML = `
        <div class="feedback-thanks">
          ${isCorrect ? "👍" : "👎"} Geri bildiriminiz kaydedildi. Teşekkürler!
        </div>
      `;
    }

    console.log(`[Spam Filtresi] Feedback gönderildi: ${isCorrect ? "doğru" : "yanlış"}`);
  } catch (error) {
    console.error("[Spam Filtresi] Feedback hatası:", error);
    const section = toast.querySelector(".feedback-section");
    if (section) {
      section.innerHTML = `<div class="feedback-thanks">⚠️ Gönderilemedi</div>`;
    }
  }

  // 3 saniye sonra toast'ı kapat
  clearTimeout(toast._autoCloseTimer);
  setTimeout(() => dismissToast(toast), 3000);
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
  btn.innerHTML = `<span class="btn-icon">⏳</span>`;

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

    // Feedback verisi (şüpheli hariç)
    const feedbackData = data.status !== "suspicious"
      ? { text: emailText, prediction: data.prediction }
      : null;

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
        data.confidence,
        feedbackData
      );
    } else {
      showToast(
        "ham",
        "Güvenli E-posta",
        `Bu e-posta güvenli görünüyor.\nGüven: %${(data.confidence * 100).toFixed(1)}${translatedNote}`,
        data.confidence,
        feedbackData
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
    btn.innerHTML = `<span class="btn-icon">🛡️</span>`;
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// 5. BAŞLATMA
// ═══════════════════════════════════════════════════════════════════════════
loadSettings();

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
