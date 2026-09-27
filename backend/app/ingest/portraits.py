"""Fetch driver portraits from Wikimedia Commons.

Every driver row already carries a Wikipedia URL from the Ergast dataset, so
the lead image of that article is the natural portrait source. These images are
freely licensed, but nearly all of them require attribution, so the author and
licence are stored alongside the URL and rendered next to the photo in the UI.

Nothing here is essential: a driver without a portrait falls back to a generated
monogram, so a failed fetch degrades the visuals and nothing else.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, Optional
from urllib.parse import unquote

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Driver

logger = logging.getLogger(__name__)

WIKI_REST = "https://en.wikipedia.org/api/rest_v1/page/summary"
WIKI_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "ApexStrategy-AI/0.1 (educational project; contact via repository)"
THUMB_WIDTH = 500


def _title_from_url(url: Optional[str]) -> Optional[str]:
    """Pull the article title out of a Wikipedia URL."""
    if not url:
        return None
    match = re.search(r"/wiki/(.+)$", url)
    return unquote(match.group(1)) if match else None


def _get_with_retry(
    client: httpx.Client, url: str, params: Optional[Dict[str, Any]] = None, attempts: int = 4
) -> Optional[httpx.Response]:
    """GET with exponential backoff.

    Wikipedia rate-limits anonymous clients aggressively, and a 429 here is
    routine rather than exceptional -- so it is retried rather than logged as a
    failure on the first hit.
    """
    delay = 1.0
    for attempt in range(attempts):
        try:
            response = client.get(url, params=params)
            if response.status_code == 404:
                return response
            if response.status_code == 429 or response.status_code >= 500:
                time.sleep(delay)
                delay = min(delay * 2, 16)
                continue
            response.raise_for_status()
            return response
        except httpx.HTTPError as exc:
            logger.debug("request failed (%s/%s) %s: %s", attempt + 1, attempts, url, exc)
            time.sleep(delay)
            delay = min(delay * 2, 16)
    return None


def _strip_html(value: Optional[str]) -> Optional[str]:
    """Attribution fields arrive as HTML fragments; keep only the text."""
    if not value:
        return None
    text = re.sub(r"<[^>]+>", "", value)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:300] or None


def _file_licence(client: httpx.Client, filename: str) -> Dict[str, Optional[str]]:
    """Look up the author and licence for one Commons file."""
    response = _get_with_retry(
        client,
        WIKI_API,
        params={
            "action": "query",
            "format": "json",
            "titles": f"File:{filename}",
            "prop": "imageinfo",
            "iiprop": "extmetadata",
            "iiextmetadatafilter": "Artist|LicenseShortName|LicenseUrl",
        },
    )
    if response is None:
        return {"author": None, "license": None, "license_url": None}
    try:
        pages = response.json().get("query", {}).get("pages", {})
        for page in pages.values():
            info = (page.get("imageinfo") or [{}])[0].get("extmetadata", {})
            if not info:
                continue
            return {
                "author": _strip_html(info.get("Artist", {}).get("value")),
                "license": _strip_html(info.get("LicenseShortName", {}).get("value")),
                "license_url": info.get("LicenseUrl", {}).get("value"),
            }
    except (ValueError, KeyError) as exc:
        logger.debug("licence lookup failed for %s: %s", filename, exc)
    return {"author": None, "license": None, "license_url": None}


def fetch_portrait(client: httpx.Client, title: str) -> Optional[Dict[str, Any]]:
    """Return the lead image of a Wikipedia article, with attribution."""
    response = _get_with_retry(client, f"{WIKI_REST}/{title.replace(' ', '_')}")
    if response is None or response.status_code == 404:
        return None
    try:
        payload = response.json()
    except ValueError as exc:
        logger.warning("unparseable summary for %s: %s", title, exc)
        return None

    thumbnail = payload.get("thumbnail") or {}
    source = thumbnail.get("source")
    if not source:
        return None

    # Request a larger render than the default and drop the analytics params.
    source = re.sub(r"/\d+px-", f"/{THUMB_WIDTH}px-", source).split("?")[0]

    original = (payload.get("originalimage") or {}).get("source", "")
    filename = unquote(original.split("/")[-1].split("?")[0]) if original else None

    licence = _file_licence(client, filename) if filename else {}
    return {
        "image_url": source,
        "image_author": licence.get("author"),
        "image_license": licence.get("license"),
        "image_license_url": licence.get("license_url"),
    }


def sync_driver_portraits(
    db: Session, only_missing: bool = True, delay: float = 1.0
) -> Dict[str, int]:
    """Populate portrait columns for drivers in the database."""
    query = select(Driver)
    if only_missing:
        query = query.where(Driver.image_url.is_(None))
    drivers = db.scalars(query).all()

    stats = {"checked": 0, "updated": 0, "missing": 0}
    with httpx.Client(timeout=30.0, headers={"User-Agent": USER_AGENT}) as client:
        for driver in drivers:
            stats["checked"] += 1
            title = _title_from_url(driver.url) or f"{driver.given_name} {driver.family_name}"
            portrait = fetch_portrait(client, title)
            if not portrait:
                stats["missing"] += 1
                logger.info("no portrait for %s", driver.ref)
                time.sleep(delay)
                continue
            for field, value in portrait.items():
                setattr(driver, field, value)
            stats["updated"] += 1
            logger.info("portrait for %-22s %s", driver.ref, portrait["image_license"])
            time.sleep(delay)
    db.commit()
    return stats
