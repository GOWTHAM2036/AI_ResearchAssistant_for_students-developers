"""
Web search and extraction helpers for the research pipeline.
The module focuses on three quality levers:
- ranking by query relevance
- source quality scoring
- URL canonicalization and dedupe
"""
import re
import time
import traceback
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from duckduckgo_search import DDGS


TRUSTED_DOMAINS = {
    "reuters.com",
    "apnews.com",
    "bloomberg.com",
    "ft.com",
    "wsj.com",
    "cnbc.com",
    "nytimes.com",
    "nature.com",
    "science.org",
    "arxiv.org",
    "who.int",
    "worldbank.org",
    "imf.org",
    "oecd.org",
    "europa.eu",
    "gov",
    "edu",
}

LOW_SIGNAL_DOMAINS = {
    "pinterest.com",
    "instagram.com",
    "tiktok.com",
    "facebook.com",
    "quora.com",
}

TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "source",
    "spm",
}

STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "for",
    "with",
    "into",
    "from",
    "latest",
    "news",
    "about",
    "what",
    "how",
    "why",
    "when",
    "where",
    "which",
    "that",
    "this",
    "are",
    "was",
    "were",
    "can",
    "will",
    "2026",
}

MAX_ARTICLE_CHARS = 6000


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def extract_domain(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        domain = parsed.netloc.lower().strip()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def normalize_url(url: str) -> str:
    """
    Normalize URLs to improve dedupe:
    - lowercase scheme/domain
    - remove fragments
    - remove tracking query params
    - sort remaining query params
    - strip redundant trailing slash
    """
    if not url:
        return ""
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        scheme = (parsed.scheme or "https").lower()
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        path = parsed.path or "/"
        path = re.sub(r"/{2,}", "/", path)
        if path != "/":
            path = path.rstrip("/")

        filtered_qs: List[Tuple[str, str]] = []
        for key, value in parse_qsl(parsed.query, keep_blank_values=False):
            k = key.lower().strip()
            if k.startswith("utm_") or k in TRACKING_QUERY_KEYS:
                continue
            filtered_qs.append((k, value.strip()))
        filtered_qs.sort(key=lambda kv: kv[0])
        query = urlencode(filtered_qs, doseq=True)

        return urlunparse((scheme, domain, path, "", query, ""))
    except Exception:
        return _clean_text(url)


def _parse_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    txt = str(value).strip()
    if not txt:
        return None

    try:
        return datetime.fromisoformat(txt.replace("Z", "+00:00"))
    except ValueError:
        pass

    formats = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%d %b %Y",
        "%d %B %Y",
        "%b %d, %Y",
        "%B %d, %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(txt, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _tokenize_query(query: str) -> List[str]:
    tokens = []
    for tok in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9\-+\.]{1,}", (query or "").lower()):
        if tok in STOPWORDS:
            continue
        tokens.append(tok)
    return list(dict.fromkeys(tokens))


def _score_relevance(query: str, title: str, snippet: str, domain: str) -> float:
    tokens = _tokenize_query(query)
    if not tokens:
        return 0.4

    title_l = (title or "").lower()
    snippet_l = (snippet or "").lower()
    domain_l = (domain or "").lower()

    title_hits = sum(1 for t in tokens if t in title_l)
    snippet_hits = sum(1 for t in tokens if t in snippet_l)
    domain_hits = sum(1 for t in tokens if t in domain_l)

    max_points = max(1, len(tokens) * 3)
    raw = (title_hits * 2 + snippet_hits + domain_hits) / max_points
    return min(1.0, max(0.0, raw))


def _score_source_quality(domain: str, snippet: str, date_value: str, url: str) -> float:
    domain_l = (domain or "").lower()
    quality = 0.45

    if url.lower().startswith("https://"):
        quality += 0.05

    if any(domain_l == d or domain_l.endswith(f".{d}") for d in TRUSTED_DOMAINS):
        quality += 0.2

    if any(domain_l == d or domain_l.endswith(f".{d}") for d in LOW_SIGNAL_DOMAINS):
        quality -= 0.25

    snippet_len = len(_clean_text(snippet))
    if snippet_len >= 120:
        quality += 0.15
    elif snippet_len >= 80:
        quality += 0.1
    elif snippet_len >= 40:
        quality += 0.05
    else:
        quality -= 0.1

    parsed_date = _parse_date(date_value)
    if parsed_date:
        now = datetime.now(timezone.utc)
        delta_days = abs((now - parsed_date.astimezone(timezone.utc)).days)
        if delta_days <= 14:
            quality += 0.1
        elif delta_days <= 60:
            quality += 0.05

    return min(1.0, max(0.0, quality))


def rank_results(query: str, raw_results: Sequence[Dict], max_results: int) -> List[Dict[str, str]]:
    """
    Rank and dedupe search results with a combined score.
    """
    best_by_url: Dict[str, Dict[str, str]] = {}

    for item in raw_results:
        title = _clean_text(item.get("title", ""))
        url = _clean_text(item.get("url", item.get("href", item.get("link", ""))))
        snippet = _clean_text(item.get("snippet", item.get("body", "")))
        date_value = _clean_text(item.get("date", ""))

        canonical = normalize_url(url)
        if not canonical:
            continue

        domain = extract_domain(canonical)
        relevance = _score_relevance(query, title, snippet, domain)
        source_quality = _score_source_quality(domain, snippet, date_value, canonical)
        combined_score = round((relevance * 0.65 + source_quality * 0.35), 4)

        enriched = {
            "title": title,
            "url": canonical,
            "canonical_url": canonical,
            "domain": domain,
            "snippet": snippet,
            "date": date_value,
            "relevance_score": round(relevance, 4),
            "source_score": round(source_quality, 4),
            "score": combined_score,
        }

        existing = best_by_url.get(canonical)
        if not existing or enriched["score"] > existing["score"]:
            best_by_url[canonical] = enriched

    ranked = sorted(
        best_by_url.values(),
        key=lambda r: (r["score"], r["relevance_score"], r["source_score"]),
        reverse=True,
    )
    return ranked[:max_results]


def _ddgs_call(call_type: str, query: str, max_results: int) -> List[Dict]:
    results: List[Dict] = []
    for attempt in range(3):
        try:
            with DDGS() as ddgs:
                if call_type == "text":
                    raw = ddgs.text(query, max_results=max_results)
                else:
                    raw = ddgs.news(query, max_results=max_results)
                for row in raw:
                    results.append(dict(row))
            return results
        except Exception as exc:
            msg = str(exc).lower()
            if "429" in msg or "ratelimit" in msg:
                time.sleep((2 ** attempt) + 0.2)
                continue
            print(f"[WebSearch:{call_type}] attempt {attempt + 1} failed: {exc}")
            traceback.print_exc()
            if attempt == 2:
                return results
            time.sleep(1)
    return results


def search_web(query: str, max_results: int = 8) -> List[Dict[str, str]]:
    """
    Search web results and return ranked, deduped documents.
    """
    fetch_size = max(max_results * 3, max_results)
    raw = _ddgs_call("text", query, fetch_size)
    return rank_results(query=query, raw_results=raw, max_results=max_results)


def search_news(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Search news results and return ranked, deduped documents.
    """
    fetch_size = max(max_results * 3, max_results)
    raw = _ddgs_call("news", query, fetch_size)
    return rank_results(query=query, raw_results=raw, max_results=max_results)


def fetch_article_body(url: str, timeout: int = 8) -> str:
    """
    Fetch and parse the main readable content from an article page.
    """
    import requests
    from bs4 import BeautifulSoup

    if not url:
        return ""

    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ResearchAgent/1.0)"},
        )
        if response.status_code >= 400:
            return ""

        content_type = response.headers.get("Content-Type", "").lower()
        if "html" not in content_type:
            return ""

        soup = BeautifulSoup(response.text, "html.parser")
        for bad in soup(["nav", "footer", "script", "style", "aside", "noscript", "form"]):
            bad.decompose()

        candidate_blocks: List[str] = []

        for article in soup.find_all("article"):
            text = _clean_text(article.get_text(separator=" ", strip=True))
            if len(text) >= 240:
                candidate_blocks.append(text)

        if not candidate_blocks:
            paragraphs = []
            for p in soup.find_all("p"):
                txt = _clean_text(p.get_text(" ", strip=True))
                if len(txt) >= 60:
                    paragraphs.append(txt)
            if paragraphs:
                candidate_blocks.append(" ".join(paragraphs[:30]))

        if not candidate_blocks:
            fallback = _clean_text(soup.get_text(" ", strip=True))
            candidate_blocks.append(fallback)

        best = max(candidate_blocks, key=len) if candidate_blocks else ""
        return best[:MAX_ARTICLE_CHARS]
    except Exception as exc:
        print(f"[FetchArticle] Error fetching {url}: {exc}")
        return ""
