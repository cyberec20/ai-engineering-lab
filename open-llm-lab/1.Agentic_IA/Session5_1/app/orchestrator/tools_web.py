from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus

import requests

from app.core.config import AppConfig


@dataclass(frozen=True)
class SearchResult:
    url: str
    title: str


def _clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text


class WebTools:
    def __init__(self, *, config: AppConfig) -> None:
        self._config = config
        self._cache: dict[str, Any] = {}
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": "Session5_1ResearchOperator/0.1 (+local)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )

    def web_search(self, query: str) -> list[SearchResult]:
        q = _clean_text(query)
        if not q:
            return []
        cache_key = f"search::{q.lower()}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        if self._config.web_provider == "stub":
            results = [
                SearchResult(url="https://en.wikipedia.org/wiki/Isaac_Newton", title="Isaac Newton - Wikipedia"),
                SearchResult(url="https://en.wikipedia.org/wiki/Internet", title="Internet - Wikipedia"),
            ]
            self._cache[cache_key] = results
            return results

        url = f"https://en.wikipedia.org/w/index.php?search={quote_plus(q)}"
        try:
            resp = self._session.get(url, timeout=self._config.request_timeout_seconds)
        except Exception:
            return []
        if resp.status_code >= 400:
            return []

        # Extremely lightweight parse: extract first 5 /wiki/ links from search results page.
        links = re.findall(r'href=\"(/wiki/[^\"#:]+)\"', resp.text or "")
        unique: list[str] = []
        for href in links:
            if href.startswith("/wiki/Special:"):
                continue
            if href not in unique:
                unique.append(href)
            if len(unique) >= max(5, self._config.max_fetches):
                break
        results = [SearchResult(url="https://en.wikipedia.org" + h, title=h.replace("/wiki/", "").replace("_", " ")) for h in unique]
        self._cache[cache_key] = results
        return results

    def web_fetch(self, url: str) -> dict[str, Any]:
        u = (url or "").strip()
        if not u:
            return {"blocked": False, "url": "", "title": "", "snippet": ""}
        cache_key = f"fetch::{u}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        if self._config.web_provider == "stub":
            if "Isaac_Newton" in u:
                out = {"blocked": False, "url": u, "title": "Isaac Newton", "snippet": "Isaac Newton was an English mathematician and physicist who formulated the laws of motion and universal gravitation."}
            elif "Internet" in u:
                out = {"blocked": False, "url": u, "title": "Internet", "snippet": "The Internet is the global system of interconnected computer networks that uses the Internet protocol suite (TCP/IP)."}
            else:
                out = {"blocked": False, "url": u, "title": "", "snippet": ""}
            self._cache[cache_key] = out
            return out

        try:
            resp = self._session.get(u, timeout=self._config.request_timeout_seconds)
        except Exception:
            out = {"blocked": False, "url": u, "title": "", "snippet": ""}
            self._cache[cache_key] = out
            return out

        blocked = resp.status_code in {401, 403, 429}
        if blocked:
            out = {"blocked": True, "url": u, "title": "", "snippet": ""}
            self._cache[cache_key] = out
            return out

        html = resp.text or ""
        title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        title = _clean_text(title_match.group(1)) if title_match else ""
        title = title.replace(" - Wikipedia", "")

        # Naive snippet extraction: first paragraph text-ish.
        para_match = re.search(r"<p>(.*?)</p>", html, re.IGNORECASE | re.DOTALL)
        para = para_match.group(1) if para_match else ""
        para = re.sub(r"<[^>]+>", " ", para)
        snippet = _clean_text(para)[: self._config.max_chars_per_page]

        out = {"blocked": False, "url": u, "title": title, "snippet": snippet}
        self._cache[cache_key] = out
        return out


def polite_delay(seconds: float) -> None:
    time.sleep(max(0.0, seconds))

