from __future__ import annotations

import html
import re
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any

import requests

from app.core.config import AppConfig
from app.orchestrator.models import EvidenceItem


@dataclass
class WebResult:
    url: str
    title: str
    snippet: str


def _strip_html(text: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class WebTools:
    def __init__(self, *, config: AppConfig) -> None:
        self._config = config

    def web_search(self, query: str) -> list[WebResult]:
        if self._config.web_provider == "stub":
            return self._stub_search(query)
        return self._wikipedia_html_search(query)

    def web_fetch(self, url: str) -> EvidenceItem | None:
        if self._config.web_provider == "stub":
            return self._stub_fetch(url)
        try:
            resp = requests.get(url, timeout=self._config.request_timeout_seconds, headers={"user-agent": "Mozilla/5.0"})
            status = resp.status_code
            if status in {403, 429}:
                return EvidenceItem(url=url, title=None, snippet=f"blocked_http_{status}", fetched_text=None)
            if not resp.ok:
                return None
            text = resp.text[: self._config.max_chars_per_page]
            cleaned = _strip_html(text)
            snippet = cleaned[: min(500, len(cleaned))]
            title = None
            m = re.search(r"<title>(.*?)</title>", resp.text, flags=re.I | re.S)
            if m:
                title = _strip_html(m.group(1))
            return EvidenceItem(url=url, title=title, snippet=snippet, fetched_text=cleaned)
        except Exception:
            return None

    def _wikipedia_html_search(self, query: str) -> list[WebResult]:
        q = query.strip()
        if not q:
            return []
        url = "https://en.wikipedia.org/w/index.php?search=" + urllib.parse.quote(q)
        try:
            resp = requests.get(url, timeout=self._config.request_timeout_seconds, headers={"user-agent": "Mozilla/5.0"})
            if not resp.ok:
                return []
            html_text = resp.text
            results: list[WebResult] = []
            for m in re.finditer(
                r'class="mw-search-result-heading"[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*title="([^"]+)"',
                html_text,
            ):
                href, title = m.group(1), m.group(2)
                full = urllib.parse.urljoin("https://en.wikipedia.org", href)
                results.append(WebResult(url=full, title=_strip_html(title), snippet=""))
                if len(results) >= max(1, self._config.max_fetches):
                    break
            if results:
                return results
            guess = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(q.replace(" ", "_"))
            return [WebResult(url=guess, title=q, snippet="")]
        except Exception:
            return []

    def _stub_search(self, query: str) -> list[WebResult]:
        q = query.lower()
        if "newton" in q:
            return [WebResult(url="https://en.wikipedia.org/wiki/Isaac_Newton", title="Isaac Newton", snippet="Isaac Newton biography")]
        if "internet" in q:
            return [WebResult(url="https://en.wikipedia.org/wiki/Internet", title="Internet", snippet="Internet definition")]
        return [WebResult(url="https://en.wikipedia.org/wiki/Internet", title="Internet", snippet="stub default")]

    def _stub_fetch(self, url: str) -> EvidenceItem:
        if url.endswith("/Isaac_Newton"):
            return EvidenceItem(
                url=url,
                title="Isaac Newton",
                snippet="Sir Isaac Newton was an English mathematician, physicist, and astronomer.",
                fetched_text="Sir Isaac Newton was an English mathematician, physicist, and astronomer.",
            )
        if url.endswith("/Internet"):
            return EvidenceItem(
                url=url,
                title="Internet",
                snippet="The Internet is the global system of interconnected computer networks that uses the Internet protocol suite (TCP/IP).",
                fetched_text="The Internet is the global system of interconnected computer networks that uses the Internet protocol suite (TCP/IP).",
            )
        return EvidenceItem(url=url, title="Stub", snippet="Stub content", fetched_text="Stub content")


def polite_delay(seconds: float) -> None:
    time.sleep(max(0.0, seconds))
