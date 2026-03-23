"""
Entry point for the PI Innovate pre-market WhatsApp bot.
Uses Python logging only — no Telegram.
"""

import logging
import os

from dotenv import load_dotenv

from monitoring.alerts import log_error, log_info

# ── environment ────────────────────────────────────────────────────────────────
load_dotenv(dotenv_path="config/secrets.env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("premarket.main")


def main() -> None:
    log_info("PI Innovate pre-market bot starting…")

    required_keys = [
        "KITE_API_KEY",
        "ANTHROPIC_API_KEY",
        "INTERAKT_API_KEY",
    ]
    missing = [k for k in required_keys if not os.getenv(k)]
    if missing:
        log_error(f"Missing required env vars: {missing}")
        raise SystemExit(1)

    log_info("Environment OK. Launching scheduler…")

    from scheduler.cron_runner import start
    start()


if __name__ == "__main__":
    main()
