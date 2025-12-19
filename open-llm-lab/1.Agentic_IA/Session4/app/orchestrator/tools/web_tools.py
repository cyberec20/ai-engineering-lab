from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.parse import parse_qs, unquote, urlparse
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from app.orchestrator.utils.text import compact_whitespace
from app.orchestrator.utils.time import now_iso


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str


@dataclass(frozen=True)
class FetchResult:
    url: str
    title: str | None
    text: str
    content_type: str | None
    fetched_at: str


class WebTools:
    def __init__(
        self,
        *,
        timeout_seconds: int = 20,
        user_agent: str = DEFAULT_USER_AGENT,
        max_results: int = 5,
        min_delay_seconds: float = 0.6,
        cache_ttl_seconds: int = 900,
        cache_max_entries: int = 256,
    ):
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent
        self.max_results = max_results
        self.min_delay_seconds = min_delay_seconds
        self._last_request_ts = 0.0
        self._cache_ttl_seconds = max(0, int(cache_ttl_seconds))
        self._cache_max_entries = max(0, int(cache_max_entries))
        self._cache: dict[str, tuple[float, int, dict[str, str], bytes]] = {}
        self._session = requests.Session()

    def _cache_key(self, *, url: str, params: dict | None = None) -> str:
        if not params:
            return url
        # deterministic order
        return url + "?" + urlencode(sorted(params.items()), doseq=True)

    def _cache_get(self, key: str) -> tuple[int, dict[str, str], bytes] | None:
        if self._cache_ttl_seconds <= 0 or self._cache_max_entries <= 0:
            return None
        hit = self._cache.get(key)
        if not hit:
            return None
        ts, status, headers, body = hit
        if (time.time() - ts) > self._cache_ttl_seconds:
            self._cache.pop(key, None)
            return None
        return status, headers, body

    def _cache_set(self, key: str, *, status: int, headers: dict[str, str], body: bytes) -> None:
        if self._cache_ttl_seconds <= 0 or self._cache_max_entries <= 0:
            return
        if len(self._cache) >= self._cache_max_entries:
            # drop oldest
            oldest_key = min(self._cache.items(), key=lambda kv: kv[1][0])[0]
            self._cache.pop(oldest_key, None)
        self._cache[key] = (time.time(), status, dict(headers), body)

    def _get(self, url: str, *, params: dict | None = None, headers: dict[str, str] | None = None) -> requests.Response:
        key = self._cache_key(url=url, params=params)
        cached = self._cache_get(key)
        if cached:
            status, cached_headers, body = cached
            resp = requests.Response()
            resp.status_code = status
            resp._content = body
            resp.headers.update(cached_headers)
            resp.url = key
            try:
                resp.encoding = requests.utils.get_encoding_from_headers(resp.headers) or "utf-8"
            except Exception:
                resp.encoding = "utf-8"
            return resp

        self._throttle()
        resp = self._session.get(url, params=params, headers=headers, timeout=self.timeout_seconds)
        resp.raise_for_status()
        self._cache_set(key, status=resp.status_code, headers=dict(resp.headers), body=resp.content)
        return resp

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request_ts
        if elapsed < self.min_delay_seconds:
            time.sleep(self.min_delay_seconds - elapsed)
        self._last_request_ts = time.time()

    def web_search(self, query: str) -> list[SearchResult]:
        url = "https://duckduckgo.com/html/?" + urlencode({"q": query})
        headers = {"User-Agent": self.user_agent}
        resp = self._get(url, headers=headers)

        soup = BeautifulSoup(resp.text, "html.parser")
        results = self._parse_ddg_html_results(soup)
        if results:
            return results[: self.max_results]

        # Fallback: DuckDuckGo lite (different HTML, often more stable)
        lite_url = "https://lite.duckduckgo.com/lite/?" + urlencode({"q": query})
        resp2 = self._get(lite_url, headers=headers)
        soup2 = BeautifulSoup(resp2.text, "html.parser")
        results2 = self._parse_ddg_lite_results(soup2)
        return results2[: self.max_results]

    @staticmethod
    def _normalize_ddg_url(href: str) -> str:
        href = (href or "").strip()
        if not href:
            return href
        if href.startswith("//"):
            href = "https:" + href
        if href.startswith("http"):
            # Handle ddg redirect links like /l/?uddg=<encoded>
            parsed = urlparse(href)
            if "duckduckgo.com" in (parsed.netloc or "") and parsed.path.startswith("/l/"):
                qs = parse_qs(parsed.query)
                uddg = (qs.get("uddg") or [None])[0]
                if uddg:
                    return unquote(uddg)
            return href
        if href.startswith("/l/?"):
            parsed = urlparse("https://duckduckgo.com" + href)
            qs = parse_qs(parsed.query)
            uddg = (qs.get("uddg") or [None])[0]
            if uddg:
                return unquote(uddg)
        return href

    def _parse_ddg_html_results(self, soup: BeautifulSoup) -> list[SearchResult]:
        results: list[SearchResult] = []
        for a in soup.select("a.result__a"):
            href = a.get("href") or ""
            url = self._normalize_ddg_url(href)
            if not url.startswith("http"):
                continue
            title = compact_whitespace(a.get_text(" ", strip=True))
            container = a.find_parent("div", class_="result") or a.find_parent("div")
            snippet_el = None
            if container is not None:
                snippet_el = container.select_one("a.result__snippet") or container.select_one("div.result__snippet")
            snippet = compact_whitespace(snippet_el.get_text(" ", strip=True) if snippet_el else "")
            results.append(SearchResult(title=title, url=url, snippet=snippet))
        return results

    def _parse_ddg_lite_results(self, soup: BeautifulSoup) -> list[SearchResult]:
        results: list[SearchResult] = []
        # In lite, results are usually in a table with links; snippets may be in adjacent rows.
        links = soup.select("a")
        for a in links:
            href = a.get("href") or ""
            url = self._normalize_ddg_url(href)
            if not url.startswith("http"):
                continue
            title = compact_whitespace(a.get_text(" ", strip=True))
            if not title or title.lower() in {"next", "previous"}:
                continue
            snippet = ""
            tr = a.find_parent("tr")
            if tr is not None:
                nxt = tr.find_next_sibling("tr")
                if nxt is not None:
                    snippet = compact_whitespace(nxt.get_text(" ", strip=True))
            results.append(SearchResult(title=title, url=url, snippet=snippet))
        # lite parsing is noisy; de-dupe by URL
        dedup: dict[str, SearchResult] = {}
        for r in results:
            dedup.setdefault(r.url, r)
        return list(dedup.values())

    def web_fetch(self, url: str) -> FetchResult:
        headers = {"User-Agent": self.user_agent}
        resp = self._get(url, headers=headers)
        content_type = resp.headers.get("content-type")

        title: str | None = None
        text = resp.text
        try:
            soup = BeautifulSoup(resp.text, "html.parser")
            title_el = soup.find("title")
            if title_el:
                title = compact_whitespace(title_el.get_text(" ", strip=True))
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            body = soup.body or soup
            text = compact_whitespace(body.get_text(" ", strip=True))
        except Exception:
            text = compact_whitespace(text)

        if len(text) > 6000:
            text = text[:6000]

        return FetchResult(
            url=url,
            title=title,
            text=text,
            content_type=content_type,
            fetched_at=now_iso(),
        )

    def wikipedia_search(self, query: str, *, lang: str = "en") -> list[SearchResult]:
        """
        Wikipedia OpenSearch (no API keys). Often works when general web search is blocked.
        """
        api = f"https://{lang}.wikipedia.org/w/api.php"
        params = {
            "action": "opensearch",
            "search": query,
            "limit": str(self.max_results),
            "namespace": "0",
            "format": "json",
        }
        headers = {"User-Agent": self.user_agent}
        resp = self._get(api, params=params, headers=headers)
        data = resp.json()
        titles = data[1] if len(data) > 1 else []
        snippets = data[2] if len(data) > 2 else []
        urls = data[3] if len(data) > 3 else []

        results: list[SearchResult] = []
        for t, s, u in zip(titles, snippets, urls):
            if not u or not isinstance(u, str):
                continue
            results.append(SearchResult(title=str(t), url=str(u), snippet=str(s)))
        return results[: self.max_results]

    def wikipedia_fetch(self, url: str, *, lang: str = "en") -> FetchResult:
        """
        Fetch a Wikipedia article as plaintext extract via MediaWiki API.
        Accepts /wiki/<Title> URLs.
        """
        headers = {"User-Agent": self.user_agent}
        parsed = urlparse(url)
        title = None
        if parsed.path.startswith("/wiki/"):
            title = unquote(parsed.path.split("/wiki/", 1)[1])
        if not title:
            title = url

        api = f"https://{lang}.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "format": "json",
            "prop": "extracts",
            "explaintext": "1",
            "redirects": "1",
            "titles": title,
            "exintro": "0",
        }
        resp = self._get(api, params=params, headers=headers)
        data = resp.json()
        pages = (data.get("query") or {}).get("pages") or {}
        page = next(iter(pages.values()), {}) if isinstance(pages, dict) else {}
        page_title = page.get("title")
        extract = page.get("extract") or ""
        extract = compact_whitespace(extract)
        if len(extract) > 6000:
            extract = extract[:6000]

        canonical_url = url
        if page_title and isinstance(page_title, str):
            canonical_url = f"https://{lang}.wikipedia.org/wiki/{quote(page_title.replace(' ', '_'))}"

        return FetchResult(
            url=canonical_url,
            title=page_title,
            text=extract,
            content_type="text/plain",
            fetched_at=now_iso(),
        )

    @staticmethod
    def asdict(obj: Any) -> dict:
        if hasattr(obj, "__dict__"):
            return dict(obj.__dict__)
        return dict(obj)
