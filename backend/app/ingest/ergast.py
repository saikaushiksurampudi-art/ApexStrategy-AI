"""Thin, polite client for the Ergast-compatible F1 API (Jolpica).

The public Jolpica mirror enforces a burst limit of roughly 4 requests/second
and a few hundred requests per hour, so this client:

* throttles every call,
* retries on 429/5xx with exponential backoff,
* caches every raw JSON response on disk.

The cache doubles as the "raw dataset" layer of the pipeline -- in AWS the same
files are what gets uploaded to S3 under ``datasets/raw/``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"
PAGE_LIMIT = 100


class ErgastClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        min_interval: float = 0.30,
        use_cache: bool = True,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (base_url or settings.ergast_base_url).rstrip("/")
        self.cache_dir = Path(cache_dir or DEFAULT_CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_interval = min_interval
        self.use_cache = use_cache
        self._last_call = 0.0
        self._client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": "ApexStrategy-AI/0.1 (educational project)"},
        )

    # -- plumbing ---------------------------------------------------------
    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ErgastClient:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def _cache_path(self, path: str, params: Dict[str, Any]) -> Path:
        key = json.dumps({"p": path, "q": params}, sort_keys=True)
        digest = hashlib.sha1(key.encode()).hexdigest()[:16]
        safe = path.strip("/").replace("/", "_") or "root"
        return self.cache_dir / f"{safe}__{digest}.json"

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call = time.monotonic()

    def get(self, path: str, **params: Any) -> Dict[str, Any]:
        """GET one page, using the on-disk cache when available."""
        params = {"format": "json", **params}
        cache_file = self._cache_path(path, params)
        if self.use_cache and cache_file.exists():
            try:
                return json.loads(cache_file.read_text())
            except json.JSONDecodeError:
                cache_file.unlink(missing_ok=True)

        url = f"{self.base_url}/{path.strip('/')}/"
        delay = 1.0
        last_error: Optional[Exception] = None
        for attempt in range(5):
            self._throttle()
            try:
                response = self._client.get(url, params=params)
                if response.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPStatusError(
                        f"retryable {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                payload = response.json()
                cache_file.write_text(json.dumps(payload))
                return payload
            except (httpx.HTTPError, json.JSONDecodeError) as exc:
                last_error = exc
                logger.warning(
                    "Request failed (%s/5) %s %s: %s", attempt + 1, url, params, exc
                )
                time.sleep(delay)
                delay = min(delay * 2, 30)
        raise RuntimeError(f"Giving up on {url} {params}: {last_error}")

    def paginate(self, path: str, **params: Any) -> Iterator[Dict[str, Any]]:
        """Yield every page of a collection endpoint."""
        offset = 0
        while True:
            payload = self.get(path, limit=PAGE_LIMIT, offset=offset, **params)
            mr = payload["MRData"]
            yield mr
            total = int(mr.get("total", 0))
            offset += PAGE_LIMIT
            if offset >= total:
                return

    # -- typed helpers ----------------------------------------------------
    def season_races(self, season: int) -> List[Dict[str, Any]]:
        races: List[Dict[str, Any]] = []
        for page in self.paginate(f"{season}/races"):
            races.extend(page["RaceTable"]["Races"])
        return races

    def season_results(self, season: int) -> List[Dict[str, Any]]:
        return self._merge_races(self.paginate(f"{season}/results"), "Results")

    def season_qualifying(self, season: int) -> List[Dict[str, Any]]:
        return self._merge_races(self.paginate(f"{season}/qualifying"), "QualifyingResults")

    def season_sprint(self, season: int) -> List[Dict[str, Any]]:
        try:
            return self._merge_races(self.paginate(f"{season}/sprint"), "SprintResults")
        except RuntimeError:
            return []

    def race_pitstops(self, season: int, rnd: int) -> List[Dict[str, Any]]:
        stops: List[Dict[str, Any]] = []
        for page in self.paginate(f"{season}/{rnd}/pitstops"):
            races = page["RaceTable"]["Races"]
            if races:
                stops.extend(races[0].get("PitStops", []))
        return stops

    def race_laps(self, season: int, rnd: int) -> List[Dict[str, Any]]:
        laps: List[Dict[str, Any]] = []
        for page in self.paginate(f"{season}/{rnd}/laps"):
            races = page["RaceTable"]["Races"]
            if races:
                laps.extend(races[0].get("Laps", []))
        return laps

    def driver_standings(self, season: int, rnd: Optional[int] = None) -> List[Dict[str, Any]]:
        path = f"{season}/{rnd}/driverstandings" if rnd else f"{season}/driverstandings"
        payload = self.get(path, limit=PAGE_LIMIT)
        lists = payload["MRData"]["StandingsTable"]["StandingsLists"]
        return lists[0]["DriverStandings"] if lists else []

    def constructor_standings(
        self, season: int, rnd: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        path = (
            f"{season}/{rnd}/constructorstandings"
            if rnd
            else f"{season}/constructorstandings"
        )
        payload = self.get(path, limit=PAGE_LIMIT)
        lists = payload["MRData"]["StandingsTable"]["StandingsLists"]
        return lists[0]["ConstructorStandings"] if lists else []

    @staticmethod
    def _merge_races(pages: Iterator[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
        """Stitch paginated race collections back into whole races.

        A race's entries can straddle a page boundary, so rounds are merged by
        round number rather than appended blindly.
        """
        by_round: Dict[str, Dict[str, Any]] = {}
        order: List[str] = []
        for page in pages:
            for race in page["RaceTable"]["Races"]:
                rnd = race["round"]
                if rnd not in by_round:
                    by_round[rnd] = {**race, key: []}
                    order.append(rnd)
                by_round[rnd][key].extend(race.get(key, []))
        return [by_round[r] for r in order]
