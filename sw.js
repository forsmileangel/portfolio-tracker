/* Portfolio Tracker – Service Worker
   v3：移除所有快取與 fetch 攔截，只保留 PWA 資格 */
const CACHE_NAME = 'portfolio-tracker-v3';

// 安裝：直接接管，不預快取任何東西
self.addEventListener('install', event => {
  event.waitUntil(self.skipWaiting());
});

// 啟動：清除所有舊快取
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// 不攔截任何 fetch，讓瀏覽器直接處理所有請求
