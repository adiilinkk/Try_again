"""
Cron / schedule runner for the pre-market bot.
Uses the `schedule` library + Python logging only. No external alerting.
"""

import logging
import time

import schedule

from monitoring.alerts import log_error, log_info

logger = logging.getLogger("premarket.scheduler")


def run_premarket_job() -> None:
    """Placeholder for the pre-market report generation + WhatsApp delivery job."""
    log_info("Running pre-market job…")
    try:
        # TODO: wire up data fetch → analysis → AI → delivery pipeline
        log_info("Pre-market job completed successfully.")
    except Exception as exc:
        log_error("Pre-market job failed", exc)


def start() -> None:
    """Register jobs and start the blocking scheduler loop."""
    # Run every weekday at 08:00 IST (adjust TZ handling as needed)
    schedule.every().monday.at("08:00").do(run_premarket_job)
    schedule.every().tuesday.at("08:00").do(run_premarket_job)
    schedule.every().wednesday.at("08:00").do(run_premarket_job)
    schedule.every().thursday.at("08:00").do(run_premarket_job)
    schedule.every().friday.at("08:00").do(run_premarket_job)

    log_info("Scheduler started. Waiting for jobs…")
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    start()
