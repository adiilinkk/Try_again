"""
Entry point for the PI Innovate pre-market WhatsApp bot.
Runs a 10-step pipeline to fetch, analyse, and broadcast the morning briefing.
"""

import logging
import os

from dotenv import load_dotenv

from monitoring.alerts import log_error, log_info

# ── Environment ────────────────────────────────────────────────────────────────
load_dotenv(dotenv_path="config/secrets.env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

logger = logging.getLogger("premarket.main")


# ── Pipeline ───────────────────────────────────────────────────────────────────

def run_pipeline() -> None:
    """Execute the full 10-step pre-market pipeline."""

    log_info("Pipeline starting…")

    from data.models import PreMarketData
    report = PreMarketData()

    # ── STEP 1: Global markets (S&P, Nasdaq, Dow, VIX, Nikkei, Hang Seng) ──────
    log_info("STEP 1 — Fetching global markets via yfinance…")
    try:
        from data.fetchers.global_markets import fetch_all_global_markets
        global_markets = fetch_all_global_markets()
        report.sp500      = global_markets.get("sp500")
        report.nasdaq     = global_markets.get("nasdaq")
        report.dow        = global_markets.get("dow")
        report.vix        = global_markets.get("vix")
        report.vix_label  = global_markets.get("vix_label", "Unknown")
        report.nikkei     = global_markets.get("nikkei")
        report.hang_seng  = global_markets.get("hang_seng")
        log_info("STEP 1 complete.")
    except Exception as exc:
        log_error("STEP 1 failed", exc)
        report.warnings.append(f"Global markets fetch failed: {exc}")

    # ── STEP 2: Nifty 50 and Bank Nifty from NSE official API ──────────────────
    log_info("STEP 2 — Fetching Nifty 50 and Bank Nifty from NSE…")
    nifty_data = {"nifty50": None, "banknifty": None}
    try:
        from data.fetchers.nse_data import fetch_nifty_data
        nifty_data = fetch_nifty_data()
        report.nifty_prev_close = nifty_data.get("nifty50")
        log_info("STEP 2 complete.")
    except Exception as exc:
        log_error("STEP 2 failed", exc)
        report.warnings.append(f"NSE Nifty fetch failed: {exc}")

    # ── STEP 3: Gift Nifty (indicative proxy via ^NSEI from yfinance) ──────────
    log_info("STEP 3 — Fetching Gift Nifty (indicative) from yfinance…")
    try:
        from data.fetchers.global_markets import fetch_gift_nifty
        gift = fetch_gift_nifty()
        report.gift_nifty = gift

        if gift is not None and report.nifty_prev_close is not None:
            prev = report.nifty_prev_close.value
            if prev:
                gap_pts = gift.value - prev
                gap_pct = (gap_pts / prev) * 100
                report.gift_nifty_gap_pts = round(gap_pts, 2)
                report.gift_nifty_gap_pct = round(gap_pct, 2)
                if gap_pct > 0.15:
                    report.gift_nifty_direction = "gap_up"
                elif gap_pct < -0.15:
                    report.gift_nifty_direction = "gap_down"
                else:
                    report.gift_nifty_direction = "flat"
                logger.info(
                    "Gift Nifty gap: %+.2f pts (%+.2f%%) — %s",
                    gap_pts, gap_pct, report.gift_nifty_direction,
                )
        log_info("STEP 3 complete.")
    except Exception as exc:
        log_error("STEP 3 failed", exc)
        report.warnings.append(f"Gift Nifty fetch failed: {exc}")

    # ── STEP 4: FII / DII flows from NSE ───────────────────────────────────────
    log_info("STEP 4 — Fetching FII/DII data from NSE…")
    try:
        from data.fetchers.nse_data import fetch_fii_dii
        fii_dii = fetch_fii_dii()
        report.fii_date = fii_dii.get("date", "Previous Session")
        log_info("STEP 4 complete — FII: %s  DII: %s", fii_dii.get("fii_net"), fii_dii.get("dii_net"))
    except Exception as exc:
        log_error("STEP 4 failed", exc)
        report.warnings.append(f"FII/DII fetch failed: {exc}")

    # ── STEP 5: Top gainers and losers from NSE ─────────────────────────────────
    log_info("STEP 5 — Fetching top movers from NSE…")
    try:
        from data.fetchers.nse_data import fetch_top_movers
        movers = fetch_top_movers()
        report.stock_gaps = movers
        log_info(
            "STEP 5 complete — %d gainers, %d losers",
            len(movers.get("gainers", [])),
            len(movers.get("losers", [])),
        )
    except Exception as exc:
        log_error("STEP 5 failed", exc)
        report.warnings.append(f"Top movers fetch failed: {exc}")

    # ── STEP 6: News from NewsAPI and RSS feeds ─────────────────────────────────
    log_info("STEP 6 — Fetching market news…")
    try:
        from data.fetchers import news as news_fetcher  # type: ignore[attr-defined]
        report.headlines = news_fetcher.fetch_news()
        log_info("STEP 6 complete — %d headlines", len(report.headlines))
    except (ImportError, AttributeError):
        logger.warning("STEP 6 — news fetcher not yet implemented, skipping")
        report.warnings.append("News fetcher not yet implemented")
    except Exception as exc:
        log_error("STEP 6 failed", exc)
        report.warnings.append(f"News fetch failed: {exc}")

    # ── STEP 7: Analysis — sector mapping and Nifty levels ─────────────────────
    log_info("STEP 7 — Running analysis…")
    try:
        from analysis import sector_mapper  # type: ignore[attr-defined]
        report.sector_signals = sector_mapper.run(report.headlines)
    except (ImportError, AttributeError):
        logger.warning("STEP 7 — sector_mapper not yet implemented, skipping")
        report.warnings.append("sector_mapper not yet implemented")
    except Exception as exc:
        log_error("STEP 7 sector_mapper failed", exc)

    try:
        from analysis import levels  # type: ignore[attr-defined]
        nifty_val = report.nifty_prev_close.value if report.nifty_prev_close else None
        if nifty_val:
            lvls = levels.compute_nifty_levels(nifty_val)
            report.nifty_resistance = lvls.get("resistance", [])
            report.nifty_support    = lvls.get("support", [])
    except (ImportError, AttributeError):
        logger.warning("STEP 7 — compute_nifty_levels not yet implemented, skipping")
    except Exception as exc:
        log_error("STEP 7 levels failed", exc)

    log_info("STEP 7 complete.")

    # ── STEP 8: Confidence check ────────────────────────────────────────────────
    log_info("STEP 8 — Checking confidence score…")
    fetched_count = sum(1 for f in [
        report.sp500, report.nasdaq, report.dow, report.vix,
        report.nifty_prev_close, report.gift_nifty,
    ] if f is not None)
    report.overall_confidence = round(fetched_count / 6, 2)
    logger.info("Confidence score: %.2f (%d/6 key data points)", report.overall_confidence, fetched_count)

    if report.overall_confidence < 0.60:
        log_error(
            f"Confidence {report.overall_confidence:.2f} below minimum 0.60 — "
            "aborting pipeline. Check data sources."
        )
        return

    log_info("STEP 8 complete — confidence OK.")

    # ── STEP 9: Generate AI report via Claude API ───────────────────────────────
    log_info("STEP 9 — Generating AI report…")
    ai_report: str = ""
    try:
        from ai import reporter  # type: ignore[attr-defined]
        ai_report = reporter.generate(report)
        log_info("STEP 9 complete — report generated (%d chars)", len(ai_report))
    except (ImportError, AttributeError):
        logger.warning("STEP 9 — AI reporter not yet implemented, skipping")
        report.warnings.append("AI reporter not yet implemented")
    except Exception as exc:
        log_error("STEP 9 failed", exc)
        report.warnings.append(f"AI report generation failed: {exc}")

    # ── STEP 10: Broadcast via Interakt ────────────────────────────────────────
    log_info("STEP 10 — Broadcasting via Interakt…")
    try:
        from delivery import interakt  # type: ignore[attr-defined]
        interakt.broadcast(ai_report, report)
        log_info("STEP 10 complete — broadcast sent.")
    except (ImportError, AttributeError):
        logger.warning("STEP 10 — Interakt delivery not yet implemented, skipping")
        report.warnings.append("Interakt delivery not yet implemented")
    except Exception as exc:
        log_error("STEP 10 failed", exc)
        report.warnings.append(f"Broadcast failed: {exc}")

    if report.warnings:
        logger.warning("Pipeline completed with %d warning(s):", len(report.warnings))
        for w in report.warnings:
            logger.warning("  • %s", w)
    else:
        log_info("Pipeline completed successfully with no warnings.")


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    log_info("PI Innovate pre-market bot starting…")

    required_keys = ["ANTHROPIC_API_KEY"]
    missing = [k for k in required_keys if not os.getenv(k)]
    if missing:
        log_error(f"Missing required env vars: {missing}")
        raise SystemExit(1)

    log_info("Environment OK. Launching scheduler…")

    from scheduler.cron_runner import start
    start()


if __name__ == "__main__":
    main()
