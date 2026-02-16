"""
Wikipedia Context Fetcher
Fetches relevant Wikipedia articles as fallback when user documents are missing.
Uses the French Wikipedia API exclusively.
"""

import logging
import re
from typing import Dict, List, Any, Optional

import requests

logger = logging.getLogger(__name__)

# French Wikipedia API endpoint
_WIKI_API = "https://fr.wikipedia.org/w/api.php"

# Limits
_MAX_ARTICLES = 3
_MAX_CHARS_PER_ARTICLE = 2000
_REQUEST_TIMEOUT = 10  # seconds


class WikipediaContextFetcher:
    """Fetches context from French Wikipedia articles."""

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    @staticmethod
    def fetch(
        themes: Optional[List[str]] = None,
        location: Optional[str] = None,
        period: Optional[Dict[str, int]] = None,
    ) -> List[Dict[str, Any]]:
        """Search French Wikipedia and return relevant article extracts.

        Args:
            themes: Historical themes to search for.
            location: Primary location / territory.
            period: Dict with ``start_year`` and ``end_year``.

        Returns:
            A list of dicts, each with keys:
            ``title``, ``extract``, ``url``, ``source``.
        """
        queries = WikipediaContextFetcher._build_search_queries(themes, location, period)
        if not queries:
            logger.warning("[Wikipedia] No search queries could be built — skipping fetch")
            return []

        logger.info("[Wikipedia] Searching with %d queries: %s", len(queries), queries)

        seen_titles: set = set()
        results: List[Dict[str, Any]] = []

        for query in queries:
            if len(results) >= _MAX_ARTICLES:
                break
            try:
                articles = WikipediaContextFetcher._search_and_extract(query)
                for article in articles:
                    if article["title"] not in seen_titles and len(results) < _MAX_ARTICLES:
                        seen_titles.add(article["title"])
                        results.append(article)
            except Exception as exc:
                logger.warning("[Wikipedia] Query '%s' failed: %s", query, exc)

        logger.info("[Wikipedia] Fetched %d articles", len(results))
        return results

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------

    @staticmethod
    def _build_search_queries(
        themes: Optional[List[str]],
        location: Optional[str],
        period: Optional[Dict[str, int]],
    ) -> List[str]:
        """Build a short list of search queries from themes, location & period."""
        queries: List[str] = []

        period_str = ""
        if period:
            start = period.get("start_year")
            end = period.get("end_year")
            if start and end:
                period_str = f" {start}-{end}"
            elif start:
                period_str = f" {start}"

        # Combine location + each theme
        if themes and location:
            for theme in themes[:3]:
                queries.append(f"{theme} {location}{period_str}")

        # Location alone (often yields a good overview article)
        if location:
            queries.append(f"{location}{period_str}")

        # Themes alone
        if themes:
            for theme in themes[:2]:
                queries.append(f"{theme}{period_str}")

        # Deduplicate while keeping order
        seen: set = set()
        unique: List[str] = []
        for q in queries:
            q_norm = q.strip().lower()
            if q_norm not in seen:
                seen.add(q_norm)
                unique.append(q.strip())

        return unique[:5]  # max 5 queries

    @staticmethod
    def _search_and_extract(query: str) -> List[Dict[str, Any]]:
        """Run a Wikipedia search and return extracts for the top results."""
        # Headers with User-Agent to avoid 403 errors
        headers = {
            "User-Agent": "MemoireDesTerritoires/1.0 (Educational history project; emile@laplateforme.io)"
        }
        
        # Step 1 – search for page titles
        search_params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": 2,
            "format": "json",
            "utf8": 1,
        }
        resp = requests.get(_WIKI_API, params=search_params, headers=headers, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        titles = [
            hit["title"]
            for hit in data.get("query", {}).get("search", [])
        ]
        if not titles:
            return []

        # Step 2 – fetch extracts for found titles
        extract_params = {
            "action": "query",
            "prop": "extracts",
            "exintro": False,  # get full extract, not just intro
            "explaintext": True,
            "titles": "|".join(titles),
            "format": "json",
            "utf8": 1,
            "exlimit": len(titles),
            "exchars": _MAX_CHARS_PER_ARTICLE,
        }
        resp = requests.get(_WIKI_API, params=extract_params, headers=headers, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        pages = resp.json().get("query", {}).get("pages", {})

        results: List[Dict[str, Any]] = []
        for _page_id, page in pages.items():
            title = page.get("title", "")
            extract = page.get("extract", "")
            if not extract or len(extract.strip()) < 50:
                continue

            # Clean up whitespace
            extract = re.sub(r"\n{3,}", "\n\n", extract).strip()

            results.append({
                "title": title,
                "extract": extract[:_MAX_CHARS_PER_ARTICLE],
                "url": f"https://fr.wikipedia.org/wiki/{title.replace(' ', '_')}",
                "source": "Wikipedia (fr)",
            })

        return results
