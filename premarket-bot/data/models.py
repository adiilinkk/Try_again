from dataclasses import dataclass, field
from datetime import datetime, timezone
import pytz

IST = pytz.timezone("Asia/Kolkata")


def _now_ist() -> datetime:
    return datetime.now(IST)


@dataclass
class MarketDataPoint:
    value: float
    source: str
    fetched_at: datetime
    data_as_of: datetime
    is_indicative: bool = False
    confidence: float = 1.0
    fallback_used: bool = False
    change_pct: float = 0.0

    def age_minutes(self) -> float:
        """Return how many minutes old the data is (based on fetched_at)."""
        now = datetime.now(self.fetched_at.tzinfo or timezone.utc)
        return (now - self.fetched_at).total_seconds() / 60

    def is_fresh(self, max_minutes: float = 60) -> bool:
        """Return True if the data was fetched within max_minutes."""
        return self.age_minutes() <= max_minutes


@dataclass
class PreMarketData:
    # ── US markets ────────────────────────────────────────────────────────────
    sp500: MarketDataPoint | None = None
    nasdaq: MarketDataPoint | None = None
    dow: MarketDataPoint | None = None
    vix: MarketDataPoint | None = None
    vix_label: str = ""                     # e.g. "Low", "Moderate", "High", "Extreme"

    # ── Asia markets ──────────────────────────────────────────────────────────
    nikkei: MarketDataPoint | None = None
    hang_seng: MarketDataPoint | None = None

    # ── India ─────────────────────────────────────────────────────────────────
    nifty_prev_close: MarketDataPoint | None = None
    gift_nifty: MarketDataPoint | None = None
    gift_nifty_gap_pts: float = 0.0         # absolute gap in points
    gift_nifty_gap_pct: float = 0.0         # gap as a percentage
    gift_nifty_direction: str = ""          # "gap_up" | "gap_down" | "flat"

    # ── FII / DII flows ───────────────────────────────────────────────────────
    fii_net: MarketDataPoint | None = None
    dii_net: MarketDataPoint | None = None
    fii_date: str = ""                      # "YYYY-MM-DD" of the flow data
    fii_dii_interpretation: str = ""        # human-readable summary

    # ── News & sentiment ──────────────────────────────────────────────────────
    headlines: list = field(default_factory=list)       # list[dict]
    sector_signals: dict = field(default_factory=dict)  # sector -> signal str
    stock_gaps: dict = field(default_factory=dict)      # symbol -> gap info dict

    # ── Technical levels ──────────────────────────────────────────────────────
    nifty_resistance: list = field(default_factory=list)  # list[float]
    nifty_support: list = field(default_factory=list)     # list[float]

    # ── Pipeline metadata ─────────────────────────────────────────────────────
    pipeline_run_at: datetime = field(default_factory=_now_ist)
    overall_confidence: float = 1.0
    warnings: list = field(default_factory=list)         # list[str]
