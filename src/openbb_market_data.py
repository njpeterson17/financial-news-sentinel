"""
OpenBB Market Data Provider - Enhanced market data using OpenBB APIs.

Uses FMP for stock data, Polygon for news, and FRED for economic data.
Includes caching to minimize API calls.
"""

import os
import sys
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass

from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from logging_config import get_logger

logger = get_logger(__name__)

# Try to import OpenBB, gracefully handle if not installed
try:
    from openbb import obb
    OPENBB_AVAILABLE = True
except ImportError:
    OPENBB_AVAILABLE = False
    logger.warning("OpenBB not installed. OpenBB market data features will be disabled.")


@dataclass
class PriceData:
    """Container for price data."""
    ticker: str
    price: float
    timestamp: datetime
    change_pct: float | None = None
    volume: int | None = None


@dataclass
class CacheEntry:
    """Cache entry with timestamp for TTL."""
    data: Any
    created_at: float


@dataclass
class EconomicIndicator:
    """Container for economic indicator data."""
    symbol: str
    name: str
    value: float
    date: datetime
    change_pct: float | None = None


class OpenBBMarketDataProvider:
    """
    Fetch stock market data using OpenBB Platform APIs.
    
    Supports:
    - FMP (Financial Modeling Prep): Stock prices, financials, company profiles
    - Polygon: News, real-time data
    - FRED: Economic indicators (CPI, GDP, interest rates)
    
    Includes caching with configurable TTL to avoid repeated API calls.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize the OpenBB market data provider.

        Args:
            config: Optional configuration dict with keys:
                - enabled: bool (default True)
                - cache_ttl_minutes: int (default 15)
                - fmp_enabled: bool (default True)
                - polygon_enabled: bool (default True)
                - fred_enabled: bool (default True)
        """
        self.config = config or {}
        self.enabled = self.config.get("enabled", True) and OPENBB_AVAILABLE
        self.cache_ttl_seconds = self.config.get("cache_ttl_minutes", 15) * 60
        
        # Feature flags for each data source
        self.fmp_enabled = self.config.get("fmp_enabled", True)
        self.polygon_enabled = self.config.get("polygon_enabled", True)
        self.fred_enabled = self.config.get("fred_enabled", True)

        # Simple in-memory cache: key -> CacheEntry
        self._cache: dict[str, CacheEntry] = {}

        if not OPENBB_AVAILABLE:
            logger.warning("OpenBBMarketDataProvider initialized but OpenBB not available")
        else:
            logger.info(
                "OpenBB Market Data Provider initialized",
                extra={
                    "fmp_enabled": self.fmp_enabled,
                    "polygon_enabled": self.polygon_enabled,
                    "fred_enabled": self.fred_enabled,
                }
            )

    def _get_cached(self, key: str) -> Any | None:
        """Get value from cache if not expired."""
        if key in self._cache:
            entry = self._cache[key]
            if time.time() - entry.created_at < self.cache_ttl_seconds:
                return entry.data
            else:
                del self._cache[key]
        return None

    def _set_cached(self, key: str, data: Any) -> None:
        """Store value in cache."""
        self._cache[key] = CacheEntry(data=data, created_at=time.time())

    def _clean_cache(self) -> None:
        """Remove expired cache entries."""
        now = time.time()
        expired = [
            key for key, entry in self._cache.items()
            if now - entry.created_at >= self.cache_ttl_seconds
        ]
        for key in expired:
            del self._cache[key]

    def get_price(self, ticker: str, date: datetime | None = None) -> float | None:
        """
        Get closing price for a ticker using FMP.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL')
            date: Date to get price for (defaults to most recent trading day)

        Returns:
            Closing price or None if not available
        """
        if not self.enabled or not self.fmp_enabled:
            return None

        try:
            cache_key = f"openbb_price:{ticker}:{date.isoformat() if date else 'latest'}"
            cached = self._get_cached(cache_key)
            if cached is not None:
                return cached

            # Use FMP provider for real-time quotes
            result = obb.equity.price.quote(ticker, provider="fmp")
            df = result.to_df()
            
            if not df.empty and 'last_price' in df.columns:
                price = float(df['last_price'].iloc[0])
                self._set_cached(cache_key, price)
                logger.debug(f"Got price for {ticker} from FMP: ${price:.2f}")
                return price

            logger.debug(f"No price data available for {ticker}")
            return None

        except Exception as e:
            logger.warning(f"Failed to get price for {ticker}: {e}")
            return None

    def get_price_change(
        self, ticker: str, start: datetime, end: datetime | None = None
    ) -> float | None:
        """
        Calculate percentage price change over a period using FMP.

        Args:
            ticker: Stock ticker symbol
            start: Start date
            end: End date (defaults to now)

        Returns:
            Percentage change (e.g., 5.2 for +5.2%) or None if not available
        """
        if not self.enabled or not self.fmp_enabled:
            return None

        try:
            end = end or datetime.now()
            cache_key = f"openbb_change:{ticker}:{start.date()}:{end.date()}"
            cached = self._get_cached(cache_key)
            if cached is not None:
                return cached

            # Get historical data
            result = obb.equity.price.historical(
                ticker, 
                start_date=start.strftime("%Y-%m-%d"),
                end_date=end.strftime("%Y-%m-%d"),
                provider="fmp"
            )
            df = result.to_df()

            if len(df) >= 2:
                start_price = float(df["close"].iloc[0])
                end_price = float(df["close"].iloc[-1])

                if start_price > 0:
                    change_pct = ((end_price - start_price) / start_price) * 100
                    self._set_cached(cache_key, round(change_pct, 2))
                    return round(change_pct, 2)

            logger.debug(f"Insufficient data for price change calculation for {ticker}")
            return None

        except Exception as e:
            logger.warning(f"Failed to get price change for {ticker}: {e}")
            return None

    def get_intraday_change(self, ticker: str) -> float | None:
        """
        Get today's price change using FMP.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Percentage change from open to current price, or None if not available
        """
        if not self.enabled or not self.fmp_enabled:
            return None

        try:
            cache_key = f"openbb_intraday:{ticker}:{datetime.now().date()}"
            cached = self._get_cached(cache_key)
            if cached is not None:
                return cached

            result = obb.equity.price.quote(ticker, provider="fmp")
            df = result.to_df()

            if not df.empty and 'change_percent' in df.columns:
                change_pct = float(df['change_percent'].iloc[0])
                self._set_cached(cache_key, round(change_pct, 2))
                return round(change_pct, 2)

            logger.debug(f"No intraday data available for {ticker}")
            return None

        except Exception as e:
            logger.warning(f"Failed to get intraday change for {ticker}: {e}")
            return None

    def get_historical_prices(self, ticker: str, days: int = 30) -> dict[str, float] | None:
        """
        Get price history for a ticker using FMP.

        Args:
            ticker: Stock ticker symbol
            days: Number of days of history to fetch

        Returns:
            Dict mapping date strings (YYYY-MM-DD) to closing prices,
            or None if not available
        """
        if not self.enabled or not self.fmp_enabled:
            return None

        try:
            cache_key = f"openbb_history:{ticker}:{days}"
            cached = self._get_cached(cache_key)
            if cached is not None:
                return cached

            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            result = obb.equity.price.historical(
                ticker,
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                provider="fmp"
            )
            df = result.to_df()

            if not df.empty:
                prices = {
                    date.strftime("%Y-%m-%d"): round(float(row["close"]), 2)
                    for date, row in df.iterrows()
                }
                self._set_cached(cache_key, prices)
                return prices

            logger.debug(f"No historical data available for {ticker}")
            return None

        except Exception as e:
            logger.warning(f"Failed to get historical prices for {ticker}: {e}")
            return None

    def get_company_profile(self, ticker: str) -> dict[str, Any] | None:
        """
        Get company profile information using FMP.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dict with company info (name, sector, industry, etc.) or None
        """
        if not self.enabled or not self.fmp_enabled:
            return None

        try:
            cache_key = f"openbb_profile:{ticker}"
            cached = self._get_cached(cache_key)
            if cached is not None:
                return cached

            result = obb.equity.profile(ticker, provider="fmp")
            df = result.to_df()

            if not df.empty:
                profile = {
                    "name": df.get("name", [ticker]).iloc[0],
                    "sector": df.get("sector", ["Unknown"]).iloc[0],
                    "industry": df.get("industry", ["Unknown"]).iloc[0],
                    "employees": int(df.get("employees", [0]).iloc[0]),
                    "website": df.get("website", [""]).iloc[0],
                    "description": df.get("description", [""]).iloc[0],
                }
                self._set_cached(cache_key, profile)
                return profile

            return None

        except Exception as e:
            logger.warning(f"Failed to get company profile for {ticker}: {e}")
            return None

    def get_financial_summary(self, ticker: str) -> dict[str, Any] | None:
        """
        Get financial summary using FMP.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dict with revenue, profit, etc. or None
        """
        if not self.enabled or not self.fmp_enabled:
            return None

        try:
            cache_key = f"openbb_financials:{ticker}"
            cached = self._get_cached(cache_key)
            if cached is not None:
                return cached

            result = obb.equity.fundamental.income(ticker, provider="fmp", limit=1)
            df = result.to_df()

            if not df.empty:
                financials = {
                    "revenue": float(df.get("revenue", [0]).iloc[0]),
                    "gross_profit": float(df.get("gross_profit", [0]).iloc[0]),
                    "net_income": float(df.get("net_income", [0]).iloc[0]),
                }
                self._set_cached(cache_key, financials)
                return financials

            return None

        except Exception as e:
            logger.warning(f"Failed to get financials for {ticker}: {e}")
            return None

    def get_market_context(self, ticker: str) -> dict[str, Any] | None:
        """
        Get comprehensive market context for a ticker using FMP.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dict with current_price, day_change_pct, week_change_pct,
            company_info, financials, or None if not available
        """
        if not self.enabled:
            return None

        try:
            current_price = self.get_price(ticker)
            if current_price is None:
                return None

            day_change = self.get_intraday_change(ticker)

            # Calculate week change
            week_ago = datetime.now() - timedelta(days=7)
            week_change = self.get_price_change(ticker, week_ago)

            # Get company profile
            profile = self.get_company_profile(ticker) if self.fmp_enabled else None

            context = {
                "current_price": round(current_price, 2),
                "day_change_pct": day_change,
                "week_change_pct": week_change,
                "timestamp": datetime.now().isoformat(),
                "provider": "openbb",
            }

            if profile:
                context["company_name"] = profile.get("name")
                context["sector"] = profile.get("sector")
                context["industry"] = profile.get("industry")

            return context

        except Exception as e:
            logger.warning(f"Failed to get market context for {ticker}: {e}")
            return None

    def is_significant_move(
        self, ticker: str, threshold_pct: float = 2.0, days: int = 1
    ) -> bool | None:
        """
        Check if ticker has made a significant price move.

        Args:
            ticker: Stock ticker symbol
            threshold_pct: Percentage threshold for significance (default 2%)
            days: Number of days to look back

        Returns:
            True if move exceeds threshold, False if not, None if data unavailable
        """
        if not self.enabled:
            return None

        try:
            if days <= 1:
                change = self.get_intraday_change(ticker)
            else:
                start = datetime.now() - timedelta(days=days)
                change = self.get_price_change(ticker, start)

            if change is not None:
                return abs(change) >= threshold_pct

            return None

        except Exception as e:
            logger.warning(f"Failed to check significant move for {ticker}: {e}")
            return None

    # =============================================================================
    # Polygon News Integration
    # =============================================================================

    def get_news(self, ticker: str, limit: int = 5) -> list[dict[str, Any]] | None:
        """
        Get news for a ticker using Polygon.

        Args:
            ticker: Stock ticker symbol
            limit: Maximum number of articles to return

        Returns:
            List of news articles or None
        """
        if not self.enabled or not self.polygon_enabled:
            return None

        try:
            cache_key = f"openbb_news:{ticker}:{limit}"
            cached = self._get_cached(cache_key)
            if cached is not None:
                return cached

            result = obb.news.company(ticker, provider="polygon", limit=limit)
            df = result.to_df()

            if not df.empty:
                articles = []
                for _, row in df.iterrows():
                    article = {
                        "title": row.get("title", ""),
                        "publisher": row.get("publisher", ""),
                        "published_at": row.get("published_at", ""),
                        "url": row.get("url", ""),
                        "tickers": row.get("tickers", []),
                    }
                    articles.append(article)
                
                self._set_cached(cache_key, articles)
                return articles

            return None

        except Exception as e:
            logger.warning(f"Failed to get news for {ticker}: {e}")
            return None

    # =============================================================================
    # FRED Economic Data Integration
    # =============================================================================

    def get_economic_indicator(
        self, 
        symbol: str, 
        name: str | None = None
    ) -> EconomicIndicator | None:
        """
        Get economic indicator data from FRED.

        Args:
            symbol: FRED series symbol (e.g., 'DGS10' for 10Y Treasury)
            name: Human-readable name for the indicator

        Returns:
            EconomicIndicator or None
        """
        if not self.enabled or not self.fred_enabled:
            return None

        try:
            cache_key = f"openbb_fred:{symbol}"
            cached = self._get_cached(cache_key)
            if cached is not None:
                return cached

            result = obb.economy.fred_series(symbol=symbol, limit=2)
            df = result.to_df()

            if not df.empty and len(df) >= 1:
                latest_value = float(df.iloc[-1].iloc[0])
                latest_date = df.index[-1]
                
                # Calculate change if we have previous data
                change_pct = None
                if len(df) >= 2:
                    prev_value = float(df.iloc[-2].iloc[0])
                    if prev_value != 0:
                        change_pct = ((latest_value - prev_value) / prev_value) * 100

                indicator = EconomicIndicator(
                    symbol=symbol,
                    name=name or symbol,
                    value=latest_value,
                    date=latest_date,
                    change_pct=round(change_pct, 2) if change_pct else None
                )
                
                self._set_cached(cache_key, indicator)
                return indicator

            return None

        except Exception as e:
            logger.warning(f"Failed to get economic indicator {symbol}: {e}")
            return None

    def get_key_economic_indicators(self) -> dict[str, EconomicIndicator | None]:
        """
        Get key economic indicators from FRED.

        Returns:
            Dict of indicator name -> EconomicIndicator
        """
        if not self.enabled or not self.fred_enabled:
            return {}

        indicators = {
            "treasury_10y": ("DGS10", "10-Year Treasury Rate"),
            "treasury_2y": ("DGS2", "2-Year Treasury Rate"),
            "fed_funds": ("FEDFUNDS", "Federal Funds Rate"),
            "unemployment": ("UNRATE", "Unemployment Rate"),
            "cpi": ("CPIAUCSL", "Consumer Price Index"),
            "gdp": ("GDP", "Gross Domestic Product"),
            "sp500": ("SP500", "S&P 500"),
        }

        results = {}
        for key, (symbol, name) in indicators.items():
            results[key] = self.get_economic_indicator(symbol, name)

        return results


def create_market_data_provider(config: dict[str, Any] | None = None) -> Any:
    """
    Factory function to create the appropriate market data provider.
    
    Checks environment variable MARKET_DATA_PROVIDER to decide which provider to use.
    Defaults to yfinance-based provider if OpenBB is not configured.
    
    Args:
        config: Optional configuration dict
        
    Returns:
        MarketDataProvider or OpenBBMarketDataProvider instance
    """
    provider_type = os.getenv("MARKET_DATA_PROVIDER", "yfinance").lower()
    
    if provider_type == "openbb" and OPENBB_AVAILABLE:
        logger.info("Using OpenBB Market Data Provider")
        return OpenBBMarketDataProvider(config)
    else:
        # Import and use the original yfinance-based provider
        from market_data import MarketDataProvider
        logger.info(f"Using MarketDataProvider (type: {provider_type})")
        return MarketDataProvider(config)
