"""
data/fetchers/global_markets.py
--------------------------------
Fetch global market index data (US, Asia, India) from Yahoo Finance via yfinance.
Each ticker is fetched independently so one failure never blocks the rest.
Results are returned as MarketDataPoint instances.
"""

import logging
import os
from datetime import datetime
from pathlib import Path

import pytz
import yfinance as yf
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log

from data.models import MarketDataPoint

# ── Environment ───────────────────────────────────────────────────────────────
_SECRETS = Path(__file__).resolve().parents[2] / "config" / "secrets.env"
load_dotenv(_SECRETS)

# ── Logging ───────────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
IST = pytz.timezone("Asia/Kolkata")
UTC = pytz.utc
SOURCE = "yfinance"
PERIOD = "5d"
INTERVAL = "1d"

TICKERS: dict[str, str] = {
    "sp500":     "^GSPC",
    "nasdaq":    "^IXIC",
    "dow":       "^DJI",
    "vix":       "^VIX",
    "nikkei":    "^N225",
    "hang_seng": "^HSI",
    "nifty":     "^NSEI",
}


# ── VIX classification ────────────────────────────────────────────────────────

def classify_vix(vix_value: float) -> str:
    """
    Return a human-readable fear label for a given VIX level.

      <  15  →  Low Fear 🟢
      <  20  →  Moderate ⚪
      <  25  →  Elevated 🟡
      <  30  →  High Fear 🔴
      >= 30  →  Extreme Fear 💀
    """
    if vix_value < 15:
        return "Low Fear 🟢"
    if vix_value < 20:
        return "Moderate ⚪"
    if vix_value < 25:
        return "Elevated 🟡"
    if vix_value < 30:
        return "High Fear 🔴"
    return "Extreme Fear 💀"


# ── Core fetch (with retry) ───────────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _fetch_ticker_raw(symbol: str) -> dict:
    """
    Download the last PERIOD of daily data for *symbol* and return a dict with
    keys: close, prev_close, data_as_of.  Raises on any failure so tenacity can
    retry.
    """
    logger.debug("Downloading %s (period=%s, interval=%s)", symbol, PERIOD, INTERVAL)
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=PERIOD, interval=INTERVAL)

    if hist is None or hist.empty:
        raise ValueError(f"Empty history returned for {symbol}")

    if len(hist) < 2:
        raise ValueError(f"Insufficient rows ({len(hist)}) for {symbol} — need ≥ 2")

    close = float(hist["Close"].iloc[-1])
    prev_close = float(hist["Close"].iloc[-2])

    # The index is a DatetimeTzAware series; grab the last timestamp
    raw_ts = hist.index[-1]
    if hasattr(raw_ts, "to_pydatetime"):
        raw_ts = raw_ts.to_pydatetime()
    if raw_ts.tzinfo is None:
        raw_ts = UTC.localize(raw_ts)

    logger.debug("%s → close=%.4f  prev_close=%.4f", symbol, close, prev_close)
    return {"close": close, "prev_close": prev_close, "data_as_of": raw_ts}


def _build_data_point(name: str, symbol: str) -> MarketDataPoint | None:
    """
    Fetch *symbol* and wrap the result in a MarketDataPoint.
    Returns None if all retries are exhausted.
    """
    fetched_at = datetime.now(IST)
    try:
        raw = _fetch_ticker_raw(symbol)
    except Exception as exc:
        logger.error(
            "All retries failed for %s (%s): %s — returning None",
            name, symbol, exc,
        )
        return None

    close = raw["close"]
    prev_close = raw["prev_close"]
    data_as_of = raw["data_as_of"]

    change_pct = ((close - prev_close) / prev_close * 100) if prev_close else 0.0

    logger.info(
        "%-10s  %10.2f  (%+.2f%%)  as_of=%s",
        name, close, change_pct, data_as_of.strftime("%Y-%m-%d"),
    )

    return MarketDataPoint(
        value=close,
        source=SOURCE,
        fetched_at=fetched_at,
        data_as_of=data_as_of,
        change_pct=round(change_pct, 4),
    )


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_global_markets() -> dict[str, MarketDataPoint | None]:
    """
    Fetch all configured market indices independently.

    Returns a dict keyed by the logical name (sp500, nasdaq, …).
    A value of None means that ticker could not be fetched after all retries.
    """
    logger.info("Starting global-markets fetch for %d tickers", len(TICKERS))
    results: dict[str, MarketDataPoint | None] = {}

    for name, symbol in TICKERS.items():
        logger.info("Fetching %-10s  (%s)", name, symbol)
        results[name] = _build_data_point(name, symbol)

    fetched = sum(1 for v in results.values() if v is not None)
    failed = len(results) - fetched
    logger.info(
        "Global-markets fetch complete — %d/%d succeeded, %d failed",
        fetched, len(results), failed,
    )

    # Attach VIX label as a convenience (not a MarketDataPoint)
    vix_point = results.get("vix")
    if vix_point is not None:
        label = classify_vix(vix_point.value)
        logger.info("VIX %.2f → %s", vix_point.value, label)
        results["vix_label"] = label          # type: ignore[assignment]
    else:
        results["vix_label"] = "Unknown"      # type: ignore[assignment]

    return results


# Alias for backward compatibility
fetch_all_global_markets = fetch_global_markets
