"""
Alert and monitoring utilities.
Uses Python logging + file logging only — no external alerting service.
  - Errors    → logs/errors.log
  - Delivery  → logs/delivery_log.json
  - Console   → stdout via logging
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

# ── log directory ──────────────────────────────────────────────────────────────
LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

ERROR_LOG = LOGS_DIR / "errors.log"
DELIVERY_LOG = LOGS_DIR / "delivery_log.json"

# ── console + error-file logger ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(ERROR_LOG, encoding="utf-8"),
    ],
)

logger = logging.getLogger("premarket.alerts")


# ── public helpers ─────────────────────────────────────────────────────────────

def log_error(message: str, exc: Exception | None = None) -> None:
    """Log an error to console and logs/errors.log."""
    if exc:
        logger.error("%s — %s: %s", message, type(exc).__name__, exc, exc_info=exc)
    else:
        logger.error(message)


def log_info(message: str) -> None:
    """Log an informational message to console."""
    logger.info(message)


def log_delivery(
    recipient: str,
    channel: str,
    status: str,
    detail: str = "",
) -> None:
    """
    Append a delivery result record to logs/delivery_log.json.

    Each record:
        {
            "timestamp": "2026-03-23T04:00:00Z",
            "recipient": "+91XXXXXXXXXX",
            "channel": "whatsapp",
            "status": "success" | "failed",
            "detail": "..."
        }
    """
    record = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
        "recipient": recipient,
        "channel": channel,
        "status": status,
        "detail": detail,
    }

    # Load existing records (create file if absent)
    records: list[dict] = []
    if DELIVERY_LOG.exists():
        try:
            with open(DELIVERY_LOG, encoding="utf-8") as fh:
                records = json.load(fh)
        except (json.JSONDecodeError, OSError):
            records = []

    records.append(record)

    with open(DELIVERY_LOG, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)

    level = logging.INFO if status == "success" else logging.WARNING
    logger.log(level, "Delivery [%s] %s → %s  %s", channel, recipient, status, detail)
