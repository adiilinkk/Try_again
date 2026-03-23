"""
data/fetchers/nse_data.py
-------------------------
Fetch Indian market data from NSE and BSE official free APIs.
No authentication required — uses browser-like session with cookies.
"""

import logging
from datetime import datetime
from pathlib import Path

import requests
import pytz
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

NSE_BASE = "https://www.nseindia.com"
NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com",
}


# ── Session ───────────────────────────────────────────────────────────────────

def get_nse_session() -> requests.Session:
    """
    Create a requests.Session with NSE-compatible headers and session cookie.
    Visits the NSE homepage first to obtain a valid session cookie.
    Returns the configured session object.
    """
    session = requests.Session()
    session.headers.update(NSE_HEADERS)
    try:
        session.get(NSE_BASE, timeout=10)
        logger.debug("NSE session cookie obtained")
    except Exception as exc:
        logger.warning("Could not prime NSE session cookie: %s", exc)
    return session


# ── Nifty / Bank Nifty ────────────────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _fetch_nifty_raw() -> list:
    session = get_nse_session()
    resp = session.get(f"{NSE_BASE}/api/allIndices", timeout=15)
    resp.raise_for_status()
    data = resp.json().get("data", [])
    if not data:
        raise ValueError("Empty allIndices response from NSE")
    return data


def fetch_nifty_data() -> dict:
    """
    Fetch Nifty 50 and Bank Nifty from NSE allIndices endpoint.
    Retries 3 times via tenacity. Returns None values if all retries fail.

    Returns dict with keys:
        nifty50:   MarketDataPoint (last, change_pct) or None
        banknifty: MarketDataPoint (last, change_pct) or None
    """
    try:
        indices = _fetch_nifty_raw()
    except Exception as exc:
        logger.error("fetch_nifty_data: all retries exhausted: %s", exc)
        return {"nifty50": None, "banknifty": None}

    nifty50 = None
    banknifty = None
    fetched_at = datetime.now(IST)

    for idx in indices:
        name = idx.get("index", "")
        if name == "NIFTY 50":
            nifty50 = MarketDataPoint(
                value=float(idx.get("last", 0)),
                source="nse_official",
                fetched_at=fetched_at,
                data_as_of=fetched_at,
                change_pct=round(float(idx.get("percentChange", 0)), 4),
            )
        elif name == "NIFTY BANK":
            banknifty = MarketDataPoint(
                value=float(idx.get("last", 0)),
                source="nse_official",
                fetched_at=fetched_at,
                data_as_of=fetched_at,
                change_pct=round(float(idx.get("percentChange", 0)), 4),
            )

    logger.info(
        "NSE indices fetched — Nifty50=%s  BankNifty=%s",
        f"{nifty50.value:,.2f}" if nifty50 else "N/A",
        f"{banknifty.value:,.2f}" if banknifty else "N/A",
    )
    return {"nifty50": nifty50, "banknifty": banknifty}


# ── FII / DII ─────────────────────────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _fetch_fii_dii_raw():
    session = get_nse_session()
    resp = session.get(f"{NSE_BASE}/api/fiidiiTradeReact", timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_fii_dii() -> dict:
    """
    Fetch FII and DII net activity from NSE's fiidiiTradeReact endpoint.
    Always labelled as Previous Session data.

    Returns dict:
        fii_net: float (crores) or None
        dii_net: float (crores) or None
        date:    string
        source:  "nse_official"
    Never crashes the pipeline.
    """
    try:
        data = _fetch_fii_dii_raw()

        if isinstance(data, list) and data:
            entry = data[0]
        elif isinstance(data, dict):
            entry = data
        else:
            raise ValueError("Unexpected FII/DII response structure")

        fii_net = float(
            entry.get("fiiNet",
            entry.get("FII_NET",
            entry.get("buyValue", 0)))
        )
        dii_net = float(
            entry.get("diiNet",
            entry.get("DII_NET",
            entry.get("sellValue", 0)))
        )
        date = str(entry.get("date", entry.get("DATE", "Previous Session")))

        logger.info(
            "FII/DII fetched — FII Net: %.0f Cr  DII Net: %.0f Cr  (%s)",
            fii_net, dii_net, date,
        )
        return {
            "fii_net": fii_net,
            "dii_net": dii_net,
            "date": date,
            "source": "nse_official",
        }

    except Exception as exc:
        logger.error("fetch_fii_dii failed: %s — returning None values", exc)
        return {
            "fii_net": None,
            "dii_net": None,
            "date": "Previous Session",
            "source": "nse_official",
        }


# ── Top Movers ────────────────────────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _fetch_movers_raw(category: str) -> list:
    session = get_nse_session()
    resp = session.get(
        f"{NSE_BASE}/api/live-analysis-variations?index={category}",
        timeout=15,
    )
    resp.raise_for_status()
    payload = resp.json()

    stocks: list = []
    if isinstance(payload, dict):
        for section in payload.values():
            if isinstance(section, dict) and "data" in section:
                stocks = section["data"]
                break
    elif isinstance(payload, list):
        stocks = payload

    return stocks


def fetch_top_movers() -> dict:
    """
    Fetch top 5 gainers and top 5 losers from NSE live-analysis-variations.

    Returns dict:
        gainers: list of {symbol, pChange, ltp}
        losers:  list of {symbol, pChange, ltp}
    """
    gainers: list[dict] = []
    losers: list[dict] = []

    for category, key in [("gainers", "gainers"), ("loosers", "losers")]:
        try:
            stocks = _fetch_movers_raw(category)
            parsed = [
                {
                    "symbol": s.get("symbol", s.get("ticker", "")),
                    "pChange": float(
                        s.get("pctChange",
                        s.get("perChange",
                        s.get("pChange", 0)))
                    ),
                    "ltp": float(
                        s.get("ltp",
                        s.get("ltP",
                        s.get("lastPrice", 0)))
                    ),
                }
                for s in stocks[:5]
            ]
            if key == "gainers":
                gainers = parsed
            else:
                losers = parsed
        except Exception as exc:
            logger.error("fetch_top_movers[%s] failed: %s", category, exc)

    logger.info("Top movers — %d gainers, %d losers", len(gainers), len(losers))
    return {"gainers": gainers, "losers": losers}


# ── Sensex ────────────────────────────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _fetch_sensex_raw() -> dict:
    resp = requests.get(
        "https://api.bseindia.com/BseIndiaAPI/api/SensexData/w",
        headers={
            "User-Agent": NSE_HEADERS["User-Agent"],
            "Referer": "https://www.bseindia.com",
            "Accept": "application/json",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_sensex() -> MarketDataPoint | None:
    """
    Fetch Sensex from BSE India API.
    Returns a MarketDataPoint or None on failure.
    """
    try:
        data = _fetch_sensex_raw()
        last = float(data.get("CurrValue", data.get("last", 0)))
        prev = float(data.get("PrevClose", data.get("previousClose", 0)))
        change_pct = ((last - prev) / prev * 100) if prev else 0.0

        fetched_at = datetime.now(IST)
        point = MarketDataPoint(
            value=last,
            source="bse_official",
            fetched_at=fetched_at,
            data_as_of=fetched_at,
            change_pct=round(change_pct, 4),
        )
        logger.info("Sensex fetched — %.2f (%+.2f%%)", last, change_pct)
        return point

    except Exception as exc:
        logger.error("fetch_sensex failed: %s — returning None", exc)
        return None


# ── Market Status ─────────────────────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _fetch_market_status_raw() -> dict:
    session = get_nse_session()
    resp = session.get(f"{NSE_BASE}/api/marketStatus", timeout=10)
    resp.raise_for_status()
    return resp.json()


def fetch_market_status() -> str:
    """
    Fetch current NSE market status.
    Returns one of: 'open', 'closed', 'pre-open', 'unknown'.
    """
    try:
        data = _fetch_market_status_raw()
        states = data.get("marketState", [])

        for state in states:
            if state.get("market", "").upper() in ("CAPITAL MARKET", "CM"):
                status = state.get("marketStatus", "").lower()
                if "pre" in status:
                    return "pre-open"
                if "open" in status:
                    return "open"
                if "close" in status:
                    return "closed"

        if states:
            status = states[0].get("marketStatus", "").lower()
            if "pre" in status:
                return "pre-open"
            if "open" in status:
                return "open"
            if "close" in status:
                return "closed"

        logger.warning("Could not determine market status from: %s", data)
        return "unknown"

    except Exception as exc:
        logger.error("fetch_market_status failed: %s — returning unknown", exc)
        return "unknown"
