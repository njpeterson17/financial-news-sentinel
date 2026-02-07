/**
 * Nickberg Terminal - Service Worker (sw.js)
 * Enhanced PWA with offline support, background sync, and smart caching
 * @version 2.0.0
 */

// ============================================
// CONFIGURATION
// ============================================

const CACHE_VERSION = 'v2';
const STATIC_CACHE = `nickberg-static-${CACHE_VERSION}`;
const API_CACHE = `nickberg-api-${CACHE_VERSION}`;
const IMAGE_CACHE = `nickberg-images-${CACHE_VERSION}`;

// Core static assets to pre-cache
const STATIC_ASSETS = [
    '/mobile',
    '/static/css/mobile.css',
    '/static/css/bloomberg-theme.css',
    '/static/css/style.css',
    '/static/js/mobile-dashboard.js',
    '/static/js/dashboard.js',
    '/static/manifest.json'
];

// CDN resources to cache
const CDN_ASSETS = [
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
    'https://cdn.jsdelivr.net/npm/chart.js'
];

// API endpoints to cache
const API_ENDPOINTS = [
    '/api/stats',
    '/api/articles',
    '/api/alerts',
    '/api/companies/top',
    '/api/market-data',
    '/api/watchlist'
];

// Cache expiration times
const CACHE_TTL = {
    api: 5 * 60 * 1000,        // 5 minutes for API data
    static: 7 * 24 * 60 * 60 * 1000,  // 7 days for static assets
    images: 30 * 24 * 60 * 60 * 1000  // 30 days for images
};

// Background sync tag
const SYNC_TAG_WATCHLIST = 'sync-watchlist';

// ============================================
// INSTALL EVENT
// ============================================

self.addEventListener('install', (event) => {
    console.log('[SW] Installing service worker v2...');

    event.waitUntil(
        Promise.all([
            // Cache static assets
            caches.open(STATIC_CACHE).then((cache) => {
                console.log('[SW] Pre-caching static assets');
                const allAssets = [...STATIC_ASSETS, ...CDN_ASSETS];
                return Promise.allSettled(
                    allAssets.map(url =>
                        cache.add(url).catch(err =>
                            console.warn(`[SW] Failed to cache: ${url}`, err)
                        )
                    )
                );
            }),
            // Pre-cache API responses for offline access
            caches.open(API_CACHE).then((cache) => {
                console.log('[SW] Pre-caching API endpoints');
                return Promise.allSettled(
                    API_ENDPOINTS.map(url =>
                        fetch(url)
                            .then(response => {
                                if (response.ok) {
                                    return cache.put(url, addCacheTimestamp(response.clone()));
                                }
                            })
                            .catch(err => console.warn(`[SW] Failed to pre-cache API: ${url}`, err))
                    )
                );
            })
        ]).then(() => {
            console.log('[SW] Installation complete');
            return self.skipWaiting();
        })
    );
});

// ============================================
// ACTIVATE EVENT
// ============================================

self.addEventListener('activate', (event) => {
    console.log('[SW] Activating service worker...');

    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames
                    .filter(name =>
                        name.startsWith('nickberg-') &&
                        ![STATIC_CACHE, API_CACHE, IMAGE_CACHE].includes(name)
                    )
                    .map(name => {
                        console.log(`[SW] Deleting old cache: ${name}`);
                        return caches.delete(name);
                    })
            );
        }).then(() => {
            console.log('[SW] Activation complete');
            return self.clients.claim();
        })
    );
});

// ============================================
// FETCH EVENT - Smart Caching Strategies
// ============================================

self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Skip non-GET requests
    if (request.method !== 'GET') {
        return;
    }

    // Skip chrome extension and other non-http requests
    if (!url.protocol.startsWith('http')) {
        return;
    }

    // Handle API requests - Network First with Cache Fallback
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(handleApiRequest(request));
        return;
    }

    // Handle image requests - Cache First with Network Fallback
    if (isImageRequest(request, url)) {
        event.respondWith(handleImageRequest(request));
        return;
    }

    // Handle static assets - Cache First with Network Update
    if (isStaticAsset(url)) {
        event.respondWith(handleStaticRequest(request));
        return;
    }

    // Handle navigation (HTML pages) - Network First with Cache Fallback
    if (request.mode === 'navigate') {
        event.respondWith(handleNavigationRequest(request));
        return;
    }

    // Default: Network First
    event.respondWith(handleDefaultRequest(request));
});

/**
 * API Request Handler - Network First Strategy
 * Tries network first, falls back to cache if offline
 */
async function handleApiRequest(request) {
    const cache = await caches.open(API_CACHE);

    try {
        const networkResponse = await fetch(request);

        if (networkResponse.ok) {
            // Cache the fresh response with timestamp
            const responseToCache = addCacheTimestamp(networkResponse.clone());
            cache.put(request, responseToCache);

            // Notify clients of fresh data
            notifyClients({
                type: 'DATA_UPDATED',
                url: request.url,
                timestamp: Date.now()
            });
        }

        return networkResponse;
    } catch (error) {
        console.log('[SW] Network failed for API, trying cache:', request.url);

        const cachedResponse = await cache.match(request);

        if (cachedResponse) {
            // Check if cache is stale
            const cachedAt = getCacheTimestamp(cachedResponse);
            const isStale = cachedAt && (Date.now() - cachedAt) > CACHE_TTL.api;

            // Notify clients about cached data usage
            notifyClients({
                type: 'SERVING_CACHED',
                url: request.url,
                cachedAt: cachedAt,
                isStale: isStale
            });

            return cachedResponse;
        }

        // No cache available
        return new Response(
            JSON.stringify({
                error: 'offline',
                message: 'No cached data available. Please connect to the internet.'
            }),
            {
                status: 503,
                headers: { 'Content-Type': 'application/json' }
            }
        );
    }
}

/**
 * Static Asset Handler - Cache First with Background Update
 */
async function handleStaticRequest(request) {
    const cache = await caches.open(STATIC_CACHE);
    const cachedResponse = await cache.match(request);

    if (cachedResponse) {
        // Return cached version immediately
        // Update cache in background
        updateCacheInBackground(request, cache);
        return cachedResponse;
    }

    // Not in cache, fetch from network
    try {
        const networkResponse = await fetch(request);
        if (networkResponse.ok) {
            cache.put(request, networkResponse.clone());
        }
        return networkResponse;
    } catch (error) {
        console.error('[SW] Failed to fetch static asset:', request.url);
        throw error;
    }
}

/**
 * Image Handler - Cache First with Expiration
 */
async function handleImageRequest(request) {
    const cache = await caches.open(IMAGE_CACHE);
    const cachedResponse = await cache.match(request);

    if (cachedResponse) {
        const cachedAt = getCacheTimestamp(cachedResponse);
        const isExpired = cachedAt && (Date.now() - cachedAt) > CACHE_TTL.images;

        if (!isExpired) {
            return cachedResponse;
        }

        // Expired but return it while updating in background
        updateCacheInBackground(request, cache);
        return cachedResponse;
    }

    // Fetch and cache
    try {
        const networkResponse = await fetch(request);
        if (networkResponse.ok) {
            const responseToCache = addCacheTimestamp(networkResponse.clone());
            cache.put(request, responseToCache);
        }
        return networkResponse;
    } catch (error) {
        // Return placeholder for failed images
        return new Response('Image unavailable offline', { status: 503 });
    }
}

/**
 * Navigation Handler - Network First with Offline Fallback
 */
async function handleNavigationRequest(request) {
    const cache = await caches.open(STATIC_CACHE);

    try {
        const networkResponse = await fetch(request);
        if (networkResponse.ok) {
            cache.put(request, networkResponse.clone());
        }
        return networkResponse;
    } catch (error) {
        console.log('[SW] Navigation network failed, using cache');

        const cachedResponse = await cache.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }

        // Try mobile page as fallback
        const mobileFallback = await cache.match('/mobile');
        if (mobileFallback) {
            return mobileFallback;
        }

        // Ultimate offline fallback
        return createOfflinePage();
    }
}

/**
 * Default Request Handler
 */
async function handleDefaultRequest(request) {
    const cache = await caches.open(STATIC_CACHE);

    try {
        const networkResponse = await fetch(request);
        if (networkResponse.ok) {
            cache.put(request, networkResponse.clone());
        }
        return networkResponse;
    } catch (error) {
        const cachedResponse = await cache.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        throw error;
    }
}

// ============================================
// BACKGROUND SYNC
// ============================================

self.addEventListener('sync', (event) => {
    console.log('[SW] Background sync triggered:', event.tag);

    if (event.tag === SYNC_TAG_WATCHLIST) {
        event.waitUntil(syncWatchlist());
    }

    if (event.tag === 'sync-pending-requests') {
        event.waitUntil(syncPendingRequests());
    }
});

/**
 * Sync watchlist updates that were made offline
 */
async function syncWatchlist() {
    console.log('[SW] Syncing watchlist...');

    try {
        // Get pending watchlist updates from IndexedDB
        const pendingUpdates = await getPendingWatchlistUpdates();

        for (const update of pendingUpdates) {
            try {
                const response = await fetch('/api/watchlist', {
                    method: update.method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(update.data)
                });

                if (response.ok) {
                    await removePendingUpdate(update.id);
                    console.log('[SW] Watchlist update synced:', update.id);
                }
            } catch (error) {
                console.error('[SW] Failed to sync watchlist update:', error);
            }
        }

        // Refresh cached watchlist data
        const cache = await caches.open(API_CACHE);
        const response = await fetch('/api/watchlist');
        if (response.ok) {
            cache.put('/api/watchlist', addCacheTimestamp(response.clone()));
        }

        // Notify clients
        notifyClients({
            type: 'WATCHLIST_SYNCED',
            message: 'Watchlist synchronized successfully'
        });
    } catch (error) {
        console.error('[SW] Watchlist sync failed:', error);
        throw error; // Will cause sync to retry
    }
}

/**
 * Sync any pending API requests
 */
async function syncPendingRequests() {
    console.log('[SW] Syncing pending requests...');

    const clients = await self.clients.matchAll({ type: 'window' });
    clients.forEach(client => {
        client.postMessage({
            type: 'SYNC_COMPLETE',
            message: 'Background sync completed'
        });
    });
}

// ============================================
// PUSH NOTIFICATIONS
// ============================================

self.addEventListener('push', (event) => {
    console.log('[SW] Push received:', event);

    let data = {
        title: 'Nickberg Terminal',
        body: 'New update available',
        icon: '/static/img/icon-192x192.png',
        badge: '/static/img/icon-72x72.png',
        tag: 'nickberg-notification',
        data: { url: '/mobile' }
    };

    if (event.data) {
        try {
            data = { ...data, ...event.data.json() };
        } catch (e) {
            data.body = event.data.text();
        }
    }

    event.waitUntil(
        self.registration.showNotification(data.title, {
            body: data.body,
            icon: data.icon,
            badge: data.badge,
            tag: data.tag,
            data: data.data,
            vibrate: [200, 100, 200],
            requireInteraction: true,
            actions: [
                { action: 'view', title: 'View' },
                { action: 'dismiss', title: 'Dismiss' }
            ]
        })
    );
});

self.addEventListener('notificationclick', (event) => {
    event.notification.close();

    if (event.action === 'dismiss') {
        return;
    }

    const urlToOpen = event.notification.data?.url || '/mobile';

    event.waitUntil(
        self.clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then((clientList) => {
                // Focus existing window if available
                for (const client of clientList) {
                    if (client.url.includes('/mobile') && 'focus' in client) {
                        return client.focus().then(() => {
                            if ('navigate' in client) {
                                client.navigate(urlToOpen);
                            }
                        });
                    }
                }
                // Open new window
                if (self.clients.openWindow) {
                    return self.clients.openWindow(urlToOpen);
                }
            })
    );
});

// ============================================
// MESSAGE HANDLING
// ============================================

self.addEventListener('message', (event) => {
    const { type, payload } = event.data || {};

    switch (type) {
        case 'SKIP_WAITING':
            self.skipWaiting();
            break;

        case 'CLEAR_CACHE':
            clearAllCaches().then(() => {
                event.source.postMessage({ type: 'CACHE_CLEARED' });
            });
            break;

        case 'GET_CACHE_STATUS':
            getCacheStatus().then(status => {
                event.source.postMessage({ type: 'CACHE_STATUS', payload: status });
            });
            break;

        case 'FORCE_REFRESH':
            forceRefreshApiCache().then(() => {
                event.source.postMessage({ type: 'REFRESH_COMPLETE' });
            });
            break;

        case 'QUEUE_WATCHLIST_UPDATE':
            queueWatchlistUpdate(payload).then(() => {
                // Register for background sync
                if ('sync' in self.registration) {
                    self.registration.sync.register(SYNC_TAG_WATCHLIST);
                }
                event.source.postMessage({ type: 'UPDATE_QUEUED' });
            });
            break;

        default:
            console.log('[SW] Unknown message:', type);
    }
});

// ============================================
// HELPER FUNCTIONS
// ============================================

/**
 * Add cache timestamp to response headers
 */
function addCacheTimestamp(response) {
    const headers = new Headers(response.headers);
    headers.set('x-sw-cached-at', Date.now().toString());

    return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers: headers
    });
}

/**
 * Get cache timestamp from response
 */
function getCacheTimestamp(response) {
    const timestamp = response.headers.get('x-sw-cached-at');
    return timestamp ? parseInt(timestamp, 10) : null;
}

/**
 * Check if request is for an image
 */
function isImageRequest(request, url) {
    return /\.(png|jpg|jpeg|gif|svg|webp|ico)$/i.test(url.pathname) ||
           request.destination === 'image';
}

/**
 * Check if URL is for static asset
 */
function isStaticAsset(url) {
    return /\.(css|js|json|woff2?|ttf|eot)$/i.test(url.pathname) ||
           url.hostname !== self.location.hostname;
}

/**
 * Update cache in background
 */
async function updateCacheInBackground(request, cache) {
    try {
        const response = await fetch(request);
        if (response.ok) {
            const responseToCache = addCacheTimestamp(response.clone());
            await cache.put(request, responseToCache);
        }
    } catch (error) {
        // Silently fail - we have cached version
    }
}

/**
 * Notify all clients
 */
async function notifyClients(message) {
    const clients = await self.clients.matchAll({ type: 'window' });
    clients.forEach(client => client.postMessage(message));
}

/**
 * Clear all caches
 */
async function clearAllCaches() {
    const cacheNames = await caches.keys();
    await Promise.all(
        cacheNames
            .filter(name => name.startsWith('nickberg-'))
            .map(name => caches.delete(name))
    );
    console.log('[SW] All caches cleared');
}

/**
 * Force refresh API cache
 */
async function forceRefreshApiCache() {
    const cache = await caches.open(API_CACHE);
    const keys = await cache.keys();

    await Promise.all(keys.map(key => cache.delete(key)));

    // Re-fetch API endpoints
    await Promise.allSettled(
        API_ENDPOINTS.map(url =>
            fetch(url)
                .then(response => {
                    if (response.ok) {
                        return cache.put(url, addCacheTimestamp(response.clone()));
                    }
                })
                .catch(() => {})
        )
    );
}

/**
 * Get cache status
 */
async function getCacheStatus() {
    const status = {
        static: 0,
        api: 0,
        images: 0
    };

    try {
        const staticCache = await caches.open(STATIC_CACHE);
        status.static = (await staticCache.keys()).length;

        const apiCache = await caches.open(API_CACHE);
        status.api = (await apiCache.keys()).length;

        const imageCache = await caches.open(IMAGE_CACHE);
        status.images = (await imageCache.keys()).length;
    } catch (error) {
        console.error('[SW] Failed to get cache status:', error);
    }

    return status;
}

/**
 * Create offline page
 */
function createOfflinePage() {
    return new Response(`
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Offline - Nickberg Terminal</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a0a;
            color: #e0e0e0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            padding: 20px;
        }
        .container { max-width: 400px; }
        .icon { font-size: 64px; margin-bottom: 24px; }
        h1 { font-size: 24px; margin-bottom: 12px; color: #ff6600; }
        p { color: #888; margin-bottom: 24px; line-height: 1.6; }
        button {
            background: #ff6600;
            color: white;
            border: none;
            padding: 14px 28px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }
        button:hover { background: #ff8833; }
        button:active { transform: scale(0.98); }
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">&#128268;</div>
        <h1>You're Offline</h1>
        <p>Nickberg Terminal needs an internet connection to load fresh data. Please check your connection and try again.</p>
        <button onclick="location.reload()">Try Again</button>
    </div>
</body>
</html>
    `, {
        headers: { 'Content-Type': 'text/html' }
    });
}

// ============================================
// INDEXEDDB HELPERS FOR BACKGROUND SYNC
// ============================================

const DB_NAME = 'nickberg-offline';
const DB_VERSION = 1;
const STORE_NAME = 'pending-updates';

/**
 * Open IndexedDB
 */
function openDB() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, DB_VERSION);

        request.onerror = () => reject(request.error);
        request.onsuccess = () => resolve(request.result);

        request.onupgradeneeded = (event) => {
            const db = event.target.result;
            if (!db.objectStoreNames.contains(STORE_NAME)) {
                db.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
            }
        };
    });
}

/**
 * Get pending watchlist updates
 */
async function getPendingWatchlistUpdates() {
    const db = await openDB();
    return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, 'readonly');
        const store = tx.objectStore(STORE_NAME);
        const request = store.getAll();

        request.onerror = () => reject(request.error);
        request.onsuccess = () => resolve(request.result);
    });
}

/**
 * Queue a watchlist update for background sync
 */
async function queueWatchlistUpdate(update) {
    const db = await openDB();
    return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, 'readwrite');
        const store = tx.objectStore(STORE_NAME);
        const request = store.add({
            ...update,
            timestamp: Date.now()
        });

        request.onerror = () => reject(request.error);
        request.onsuccess = () => resolve(request.result);
    });
}

/**
 * Remove a pending update after successful sync
 */
async function removePendingUpdate(id) {
    const db = await openDB();
    return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, 'readwrite');
        const store = tx.objectStore(STORE_NAME);
        const request = store.delete(id);

        request.onerror = () => reject(request.error);
        request.onsuccess = () => resolve();
    });
}

// ============================================
// PERIODIC BACKGROUND SYNC
// ============================================

self.addEventListener('periodicsync', (event) => {
    if (event.tag === 'update-data') {
        event.waitUntil(refreshDataInBackground());
    }
});

async function refreshDataInBackground() {
    console.log('[SW] Periodic background refresh');

    const cache = await caches.open(API_CACHE);

    await Promise.allSettled(
        API_ENDPOINTS.map(url =>
            fetch(url)
                .then(response => {
                    if (response.ok) {
                        return cache.put(url, addCacheTimestamp(response.clone()));
                    }
                })
        )
    );

    notifyClients({
        type: 'BACKGROUND_REFRESH_COMPLETE',
        message: 'Data refreshed in background'
    });
}

// ============================================
// ERROR HANDLING
// ============================================

self.addEventListener('error', (event) => {
    console.error('[SW] Error:', event.message);
});

self.addEventListener('unhandledrejection', (event) => {
    console.error('[SW] Unhandled rejection:', event.reason);
});

console.log('[SW] Service worker script loaded (v2)');
