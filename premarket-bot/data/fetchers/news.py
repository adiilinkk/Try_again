"""
data/fetchers/news.py
---------------------
Fetch financial news headlines from NewsAPI and Indian market RSS feeds.
NewsAPI is tried first; RSS feeds are used as fallback/supplement.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import requests
from dotenv import load_dotenv

_SECRETS = Path(__file__).resolve().parents[2] / "config" / "secrets.env"
load_dotenv(_SECRETS)

logger = logging.getLogger(__name__)

RSS_FEEDS = [
    ("Economic Times Markets", "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
    ("MoneyControl", "https://www.moneycontrol.com/rss/latestnews.xml"),
    ("LiveMint", "https://www.livemint.com/rss/markets"),
]


def fetch_news(hours_back: int = 24) -> list[dict]:
    """
    Fetch market news headlines from NewsAPI and RSS feeds.

    Returns a list of dicts with keys: title, source, url, published_at.
    NewsAPI is tried first (requires NEWS_API_KEY). RSS feeds supplement
    or replace it if the key is missing or the call fails.
    """
    headlines: list[dict] = []

    # ── NewsAPI ───────────────────────────────────────────────────────────────
    api_key = os.getenv("NEWS_API_KEY", "")
    if api_key and "your_" not in api_key:
        try:
            from_time = (
                datetime.now(timezone.utc) - timedelta(hours=hours_back)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")

            resp = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": "nifty OR sensex OR india stock market",
                    "from": from_time,
                    "language": "en",
                    "sortBy": "publishedAt",
                    "pageSize": 10,
                    "apiKey": api_key,
                },
                timeout=10,
            )
            resp.raise_for_status()
            for article in resp.json().get("articles", []):
                headlines.append({
                    "title": article.get("title", ""),
                    "source": article.get("source", {}).get("name", "NewsAPI"),
                    "url": article.get("url", ""),
                    "published_at": article.get("publishedAt", ""),
                })
            logger.info("NewsAPI: %d headlines fetched", len(headlines))
        except Exception as exc:
            logger.warning("NewsAPI failed: %s", exc)

    # ── RSS feeds ─────────────────────────────────────────────────────────────
    for feed_name, feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:5]:
                headlines.append({
                    "title": entry.get("title", ""),
                    "source": feed_name,
                    "url": entry.get("link", ""),
                    "published_at": entry.get("published", ""),
                })
            logger.info("RSS %s: %d entries fetched", feed_name, len(feed.entries[:5]))
        except Exception as exc:
            logger.warning("RSS %s failed: %s", feed_name, exc)

    logger.info("Total headlines: %d", len(headlines))
    return headlines[:20]
