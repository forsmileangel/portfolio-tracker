/* Portfolio Tracker – Service Worker
   版本號更新會清除舊快取並重新下載 */
const CACHE_NAME = 'portfolio-tracker-v2';
const PRECACHE = [
  './portfolio-tracker-v15.html',
  'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js',
];

// 安裝：預快取核心資源
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(PRECACHE).catch(() => {}))
      .then(() => self.skipWaiting())
  );
});

// 啟動：清除舊版快取
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// 請求攔截：只快取本機靜態資源，外部 API 直接走網路不快取
const CACHE_ONLY_SAME_ORIGIN = true;
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  // 外部請求（Google Sheet、Yahoo Finance、匯率 API 等）→ 完全不攔截，讓瀏覽器直接處理
  if (url.origin !== self.location.origin) return;
  // 本機靜態資源：網路優先，失敗才用快取
  event.respondWith(
    fetch(event.request)
      .then(res => {
        if (res.ok) {
          const clone = res.clone();
          caches.open(CACHE_NAME).then(c => c.put(event.request, clone));
        }
        return res;
      })
      .catch(() => caches.match(event.request))
  );
});
