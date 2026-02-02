# 📰 News Sentinel Bot

A financial news monitoring bot that scrapes Reuters, Bloomberg, CNBC and other sources to detect patterns like:

- 📈 **Volume Spikes** - Unusual increase in news coverage
- 🎭 **Sentiment Shifts** - Changes in positive/negative tone
- 🚀 **Momentum Building** - Increasing coverage trend
- ⚡ **Negative Clusters** - Concentrated bad news

## Features

- **Multi-source scraping**: Reuters, Bloomberg, CNBC (RSS feeds)
- **Company extraction**: Identifies mentions of watched companies
- **Pattern detection**: Statistical analysis of coverage patterns
- **Multiple alerts**: Console, file, Telegram, webhook
- **SQLite storage**: Persistent storage with automatic cleanup

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Bot

```bash
# Run once
python src/main.py run

# Dry run (no database writes)
python src/main.py run --dry-run

# Show status
python src/main.py status
```

### 3. Web Dashboard

Launch the web dashboard for real-time monitoring:

```bash
./start-web.sh
```

Then open http://localhost:5000 in your browser.

Features:
- 📊 Real-time stats and charts
- 🚨 Active alerts with acknowledgment
- 📈 Mention timeline visualization
- 😊 Sentiment analysis dashboard
- 📰 Recent articles feed
- ▶️ Manual bot trigger

### 4. Set up Scheduled Running

Add to crontab (runs every 30 minutes):

```bash
*/30 * * * * cd /path/to/news-sentinel-bot && python src/main.py schedule
```

## Web Dashboard

The web dashboard provides a real-time view of your news monitoring:

```bash
./start-web.sh
# Open http://localhost:5000
```

### Dashboard Features

| Feature | Description |
|---------|-------------|
| **Stats Cards** | Total articles, mentions, alerts, and 24h activity |
| **Active Alerts** | Real-time alerts with severity levels and one-click acknowledge |
| **Activity Charts** | Toggle between mentions timeline, sentiment trends, and source distribution |
| **Top Companies** | Ranked list of most mentioned companies |
| **Sentiment Analysis** | Visual breakdown of positive/neutral/negative coverage |
| **Recent Articles** | Filterable feed with sentiment indicators |
| **Manual Trigger** | Run the bot on-demand from the UI |

The dashboard auto-refreshes every 60 seconds.

## Configuration

Edit `config/settings.yaml`:

### Watchlist

Add companies to track:

```yaml
companies:
  watchlist:
    AAPL: ["Apple", "AAPL"]
    TSLA: ["Tesla", "TSLA", "Elon Musk"]
    # ticker: [name variations]
```

### Alert Thresholds

```yaml
patterns:
  volume_spike_threshold: 3.0  # 3x normal coverage
  min_articles_for_alert: 3    # Min articles to trigger
```

### Telegram Alerts

```bash
export NEWS_BOT_TELEGRAM_TOKEN="your_bot_token"
export NEWS_BOT_TELEGRAM_CHAT_ID="your_chat_id"
```

Enable in config:
```yaml
alerts:
  telegram:
    enabled: true
```

## Pattern Types

### Volume Spike 🚨
Triggered when a company gets significantly more coverage than usual.

Example: *"Apple (AAPL): 8 articles in 6h (spike: 4.2x normal)"*

### Sentiment Shift 🎭
Triggered when tone changes significantly (positive or negative).

Example: *"Tesla (TSLA): Negative sentiment shift (change: -0.72)"*

### Momentum Building 🚀
Triggered when coverage is trending up over several days.

Example: *"Nvidia (NVDA): Building momentum (2 → 5 → 9 articles/day)"*

### Negative Cluster ⚡
Triggered when multiple negative articles appear in short window.

Example: *"Meta (META): Negative news cluster (4/5 recent articles negative)"*

## Commands

```bash
# Run bot
python src/main.py run

# Check status
python src/main.py status

# Add company to watchlist
python src/main.py watchlist add TSLA "Tesla,Elon Musk,Model 3"

# Clear all alerts
python src/main.py reset-alerts
```

## Database

SQLite database stores:
- Articles (title, content, source, sentiment)
- Company mentions (ticker, context)
- Alerts (pattern type, severity)

Location: `data/news_sentinel.db`

## Project Structure

```
news-sentinel-bot/
├── config/
│   └── settings.yaml          # Configuration
├── src/
│   ├── main.py                # Main entry point
│   ├── database.py            # SQLite storage
│   ├── scraper.py             # News source scrapers
│   ├── company_extractor.py   # Entity extraction
│   ├── pattern_detector.py    # Pattern algorithms
│   └── alerts.py              # Notification system
├── data/                      # SQLite database
├── logs/                      # Log files
└── requirements.txt
```

## Customization

### Adding New Sources

Edit `config/settings.yaml`:

```yaml
sources:
  your_source:
    enabled: true
    rss_feeds:
      - "https://example.com/feed.xml"
```

### Custom Patterns

Extend `src/pattern_detector.py` to add new detection algorithms.

## Troubleshooting

**No articles found?**
- Check RSS feed URLs in config
- Some sites may block scrapers (add delay)

**Too many/few alerts?**
- Adjust `volume_spike_threshold`
- Change `min_articles_for_alert`

**Database issues?**
- Delete `data/news_sentinel.db` to reset

## License

MIT
