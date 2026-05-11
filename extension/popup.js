/**
 * Gmail Spam Filtresi — Popup Script
 * Uzantı ayarlarını yönetir.
 */

const API_BASE = "http://localhost:8000";

// ─── Ayarları Yükle ──────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("collect-toggle");

  // Mevcut ayarı yükle
  chrome.storage.sync.get({ collectData: false }, (result) => {
    toggle.checked = result.collectData;
  });

  // Toggle değiştiğinde kaydet
  toggle.addEventListener("change", () => {
    chrome.storage.sync.set({ collectData: toggle.checked });
  });

  // API durumunu kontrol et
  checkApiStatus();
});

// ─── API Sağlık Kontrolü ────────────────────────────────────────────────────
async function checkApiStatus() {
  const badge = document.getElementById("api-status");

  try {
    const response = await fetch(API_BASE + "/", { signal: AbortSignal.timeout(3000) });
    if (response.ok) {
      badge.textContent = "Çalışıyor ✅";
      badge.classList.add("status-ok");
    } else {
      badge.textContent = "Hata ⚠️";
      badge.classList.add("status-error");
    }
  } catch {
    badge.textContent = "Bağlantı yok ❌";
    badge.classList.add("status-error");
  }
}
