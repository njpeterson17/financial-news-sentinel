/**
 * Web Worker for background data preloading
 * Fetches stock data without blocking the main thread
 */

// Message handler
self.onmessage = async function(e) {
    const { type, data } = e.data;

    switch (type) {
        case 'preload':
            await preloadStockData(data.tickers);
            break;
        case 'fetchPrice':
            await fetchPrice(data.ticker);
            break;
        case 'fetchBatch':
            await fetchBatchPrices(data.tickers);
            break;
    }
};

/**
 * Preload stock data for multiple tickers
 */
async function preloadStockData(tickers) {
    if (!tickers || tickers.length === 0) {
        self.postMessage({ type: 'preload_complete', data: {} });
        return;
    }

    const results = {};
    const batchSize = 5;

    // Process in batches to avoid overwhelming the server
    for (let i = 0; i < tickers.length; i += batchSize) {
        const batch = tickers.slice(i, i + batchSize);

        try {
            // Fetch prices for batch
            const response = await fetch(`/api/prices?tickers=${batch.join(',')}`);
            if (response.ok) {
                const prices = await response.json();
                Object.assign(results, prices);
            }
        } catch (error) {
            console.warn('[Worker] Batch fetch failed:', error);
        }

        // Small delay between batches
        if (i + batchSize < tickers.length) {
            await sleep(100);
        }
    }

    self.postMessage({ type: 'preload_complete', data: results });
}

/**
 * Fetch price for a single ticker
 */
async function fetchPrice(ticker) {
    try {
        const response = await fetch(`/api/prices?tickers=${ticker}`);
        if (response.ok) {
            const data = await response.json();
            self.postMessage({
                type: 'price_update',
                data: { ticker, price: data[ticker] }
            });
        }
    } catch (error) {
        self.postMessage({
            type: 'price_error',
            data: { ticker, error: error.message }
        });
    }
}

/**
 * Fetch prices for multiple tickers
 */
async function fetchBatchPrices(tickers) {
    try {
        const response = await fetch(`/api/prices?tickers=${tickers.join(',')}`);
        if (response.ok) {
            const data = await response.json();
            self.postMessage({
                type: 'batch_prices',
                data: data
            });
        }
    } catch (error) {
        self.postMessage({
            type: 'batch_error',
            data: { error: error.message }
        });
    }
}

/**
 * Sleep utility
 */
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}
