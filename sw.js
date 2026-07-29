/* Portfolio Tracker – Service Worker
   v4：維持 no-op，revision bump 讓舊 PWA 主動重載 v15.945 */
const CACHE_NAME = 'portfolio-tracker-v4';

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
