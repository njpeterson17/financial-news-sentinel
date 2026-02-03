"""
Polygon.io News Scraper for Nickberg Terminal.

Uses OpenBB's Polygon integration to fetch real-time news articles
for watchlist companies.
"""

import sys
from datetime import datetime
from typing import Iterator
from dataclasses import dataclass
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from logging_config import get_logger

logger = get_logger(__name__)

# Try to import OpenBB
try:
    from openbb import obb
    OPENBB_AVAILABLE = True
except ImportError:
    OPENBB_AVAILABLE = False
    logger.warning("OpenBB not installed. Polygon scraper will be disabled.")


@dataclass
class NewsArticle:
    """News article data structure matching scraper.py expectations."""
    url: str
    title: str
    content: str
    source: str
    published_at: datetime


class PolygonNewsScraper:
    """
    Scraper for fetching news from Polygon.io via OpenBB.
    
    This scraper fetches the latest news articles for specified tickers
    and yields them in the standard NewsArticle format used by the bot.
    """

    def __init__(self, tickers: list[str] | None = None, articles_per_ticker: int = 5):
        """
        Initialize the Polygon news scraper.

        Args:
            tickers: List of stock tickers to fetch news for
            articles_per_ticker: Number of articles to fetch per ticker
        """
        self.tickers = tickers or []
        self.articles_per_ticker = articles_per_ticker
        self.enabled = OPENBB_AVAILABLE
        
        if not self.enabled:
            logger.warning("PolygonNewsScraper initialized but OpenBB not available")
        elif not self.tickers:
            logger.warning("PolygonNewsScraper initialized with empty watchlist")
        else:
            logger.info(
                f"PolygonNewsScraper initialized for {len(self.tickers)} tickers",
                extra={
                    "tickers": self.tickers,
                    "articles_per_ticker": articles_per_ticker
                }
            )

    def add_ticker(self, ticker: str) -> None:
        """Add a ticker to the watchlist."""
        ticker = ticker.upper()
        if ticker not in self.tickers:
            self.tickers.append(ticker)
            logger.info(f"Added {ticker} to Polygon scraper watchlist")

    def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker from the watchlist."""
        ticker = ticker.upper()
        if ticker in self.tickers:
            self.tickers.remove(ticker)
            logger.info(f"Removed {ticker} from Polygon scraper watchlist")

    def fetch_news_for_ticker(self, ticker: str) -> list[NewsArticle]:
        """
        Fetch news articles for a specific ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            List of NewsArticle objects
        """
        if not self.enabled:
            logger.debug(f"Polygon scraper disabled, skipping {ticker}")
            return []

        try:
            logger.debug(f"Fetching news for {ticker} from Polygon")
            
            result = obb.news.company(
                ticker, 
                provider="polygon", 
                limit=self.articles_per_ticker
            )
            df = result.to_df()

            if df.empty:
                logger.debug(f"No news found for {ticker}")
                return []

            articles = []
            for _, row in df.iterrows():
                try:
                    # Parse published date
                    published_at = datetime.now()
                    if "published_at" in row and row["published_at"]:
                        try:
                            published_at = datetime.fromisoformat(
                                row["published_at"].replace("Z", "+00:00")
                            )
                        except (ValueError, AttributeError):
                            pass

                    # Build article URL
                    url = row.get("url", "")
                    if not url and "article_url" in row:
                        url = row["article_url"]
                    if not url:
                        # Create a unique identifier URL
                        url = f"polygon://news/{ticker}/{published_at.isoformat()}"

                    # Get publisher info
                    publisher_data = row.get("publisher", {})
                    if isinstance(publisher_data, dict):
                        source = publisher_data.get("name", "Polygon")
                    else:
                        source = "Polygon"

                    article = NewsArticle(
                        url=url,
                        title=row.get("title", "No Title"),
                        content=row.get("description", row.get("title", "")),
                        source=f"Polygon/{source}",
                        published_at=published_at
                    )
                    articles.append(article)

                except Exception as e:
                    logger.warning(f"Error processing article for {ticker}: {e}")
                    continue

            logger.debug(f"Fetched {len(articles)} articles for {ticker}")
            return articles

        except Exception as e:
            logger.error(f"Failed to fetch news for {ticker}: {e}")
            return []

    def scrape(self) -> Iterator[NewsArticle]:
        """
        Scrape news for all watchlist tickers.
        
        Yields:
            NewsArticle objects
        """
        if not self.enabled:
            logger.warning("Polygon scraper is disabled")
            return

        if not self.tickers:
            logger.warning("No tickers configured for Polygon scraper")
            return

        logger.info(
            f"Starting Polygon news scrape for {len(self.tickers)} tickers"
        )

        total_articles = 0
        for ticker in self.tickers:
            try:
                articles = self.fetch_news_for_ticker(ticker)
                for article in articles:
                    yield article
                    total_articles += 1
            except Exception as e:
                logger.error(f"Error scraping {ticker}: {e}")
                continue

        logger.info(f"Polygon scrape complete, fetched {total_articles} articles")

    def scrape_sync(self) -> list[NewsArticle]:
        """
        Synchronous version that returns all articles as a list.
        
        Returns:
            List of NewsArticle objects
        """
        return list(self.scrape())


class PolygonScraperSource:
    """
    Adapter class to integrate Polygon scraper with the existing ScraperManager.
    
    This provides a consistent interface that matches other scraper sources.
    """

    def __init__(self, config: dict | None = None):
        """
        Initialize the Polygon scraper source.

        Args:
            config: Configuration dict with keys:
                - tickers: List of tickers to track
                - articles_per_ticker: Number of articles per ticker (default 5)
                - enabled: Whether this source is enabled (default true)
        """
        self.config = config or {}
        self.enabled = self.config.get("enabled", True) and OPENBB_AVAILABLE
        
        tickers = self.config.get("tickers", [])
        articles_per_ticker = self.config.get("articles_per_ticker", 5)
        
        self.scraper = PolygonNewsScraper(
            tickers=tickers,
            articles_per_ticker=articles_per_ticker
        ) if self.enabled else None

    def fetch_articles(self) -> list[NewsArticle]:
        """
        Fetch articles from Polygon.
        
        Returns:
            List of NewsArticle objects
        """
        if not self.enabled or not self.scraper:
            return []
        
        try:
            return self.scraper.scrape_sync()
        except Exception as e:
            logger.error(f"Polygon source fetch failed: {e}")
            return []


def create_polygon_source(watchlist: dict[str, list[str]], config: dict | None = None) -> PolygonScraperSource:
    """
    Factory function to create a Polygon scraper source from watchlist.
    
    Args:
        watchlist: Dict mapping ticker to list of company names
        config: Additional configuration
        
    Returns:
        Configured PolygonScraperSource
    """
    config = config or {}
    tickers = list(watchlist.keys())
    config["tickers"] = tickers
    
    return PolygonScraperSource(config)
