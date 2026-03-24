"""
data/fetchers/gift_nifty.py
---------------------------
Gift Nifty indicative proxy using ^NSEI from yfinance.
Re-exports fetch_gift_nifty from global_markets and provides calculate_gap.
"""

from data.fetchers.global_markets import fetch_gift_nifty  # noqa: F401


def calculate_gap(gift_value: float, prev_close: float) -> tuple[float, float, str]:
    """
    Calculate the gap between Gift Nifty and previous Nifty close.

    Returns (gap_pts, gap_pct, direction) where direction is one of:
      'gap_up'   — gap_pct > +0.15%
      'gap_down' — gap_pct < -0.15%
      'flat'     — within ±0.15%
    """
    gap_pts = gift_value - prev_close
    gap_pct = (gap_pts / prev_close * 100) if prev_close else 0.0

    if gap_pct > 0.15:
        direction = "gap_up"
    elif gap_pct < -0.15:
        direction = "gap_down"
    else:
        direction = "flat"

    return round(gap_pts, 2), round(gap_pct, 2), direction
