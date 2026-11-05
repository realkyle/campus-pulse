import feedparser
import hashlib
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

UW_ALERTS_RSS = "https://www.washington.edu/safety/alert/feed/"


def fetch_alerts() -> tuple[list[dict], bool]:
    """
    Returns (alerts, feed_ok).
    Each alert dict has: id, raw_text, published.
    feed_ok is False if the live feed was unreachable.
    """
    try:
        feed = feedparser.parse(UW_ALERTS_RSS)
        if feed.bozo and not feed.entries:
            logger.error("Feed parse error: %s", feed.bozo_exception)
            raise ValueError("Feed parse error")

        alerts = []
        for entry in feed.entries:
            text = entry.get("summary") or entry.get("title") or ""
            if entry.get("title") and entry.get("summary"):
                text = f"{entry['title']}. {entry['summary']}"
            entry_id = hashlib.md5(text.encode()).hexdigest()[:12]
            published = entry.get("published", datetime.now(timezone.utc).isoformat())
            alerts.append({"id": entry_id, "raw_text": text, "published": published})

        return alerts, True

    except Exception as e:
        logger.exception("Exception fetching RSS: %s", e)
        return [], False
