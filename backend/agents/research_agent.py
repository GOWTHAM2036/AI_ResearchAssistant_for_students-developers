"""
Research Agent: gathers high-quality web evidence for downstream analysis.
"""
import re
from typing import Any, Callable, Dict, List, Optional

from backend.agents.base_agent import BaseAgent
from backend.tools.web_search import fetch_article_body, search_news, search_web


class ResearchAgent(BaseAgent):
    def __init__(self, emit: Optional[Callable] = None):
        super().__init__(
            name="Researcher",
            role="Web Search and Data Collection",
            color="#2563eb",
            emit=emit,
        )

    def run(self, input_data: Any) -> dict:
        """
        Input: research plan dict from ManagerAgent
        Output: payload with ranked sources + scraped article evidence
        """
        self.emit_status("working")

        topic = input_data.get("topic", "AI technology")
        seed_queries = input_data.get("search_queries", [])
        queries = self._build_query_set(topic=topic, seed_queries=seed_queries)

        self.emit_log(f"Starting web research for: '{topic}'")
        self.emit_log(f"Executing {len(queries)} ranked search queries")

        collected: List[Dict] = []
        queries_succeeded = 0

        for idx, query in enumerate(queries, 1):
            self.emit_log(f"[{idx}/{len(queries)}] Search: {query}")
            try:
                hits = search_web(query, max_results=7)
                if hits:
                    queries_succeeded += 1
                    for h in hits:
                        merged = dict(h)
                        merged["matched_query"] = query
                        collected.append(merged)
            except Exception as exc:
                self.emit_log(f"Search error: {str(exc)[:120]}")

        news_hits: List[Dict] = []
        try:
            self.emit_log("Searching latest news")
            news_hits = search_news(f"{topic} latest", max_results=8)
            for n in news_hits:
                n["matched_query"] = "news"
                collected.append(n)
        except Exception as exc:
            self.emit_log(f"News search error: {str(exc)[:120]}")

        ranked_all = self._merge_and_rank(collected)
        selected_sources = self._pick_diverse_sources(ranked_all, target=6)

        self.emit_log(
            f"Found {len(ranked_all)} unique sources; selected {len(selected_sources)} high-signal sources"
        )

        full_texts: List[str] = []
        for idx, src in enumerate(selected_sources, 1):
            url = src.get("url", "")
            title = src.get("title", "Untitled")
            if not url:
                continue
            self.emit_log(f"Scraping [{idx}/{len(selected_sources)}]: {title[:60]}")
            body = fetch_article_body(url)
            if body:
                full_texts.append(
                    "\n".join(
                        [
                            f"SOURCE: {url}",
                            f"DOMAIN: {src.get('domain', '')}",
                            f"TITLE: {title}",
                            f"SCORE: {src.get('score', 0)}",
                            f"CONTENT: {body}",
                        ]
                    )
                )

        raw_search_text = "\n\n---\n\n".join(full_texts)

        # Writer expects `source` on each result for source list rendering.
        top_results = []
        for row in selected_sources:
            out = dict(row)
            out["source"] = row.get("url", "")
            top_results.append(out)

        payload = {
            "topic": topic,
            "focus_areas": input_data.get("focus_areas", []),
            "raw_search_text": raw_search_text,
            "queries_executed": queries_succeeded,
            "total_sources": len(ranked_all),
            "total_raw_sources": len(ranked_all),
            "raw_results": top_results,
            "raw_news": news_hits[:5],
        }

        self.emit_log(f"Research complete: {len(full_texts)} article bodies extracted")
        self.emit_status("done")
        return payload

    def _build_query_set(self, topic: str, seed_queries: List[str]) -> List[str]:
        queries: List[str] = []
        for q in seed_queries:
            cleaned = (q or "").strip()
            if cleaned:
                queries.append(cleaned)

        # Add robust default angles to improve retrieval completeness.
        defaults = [
            f"{topic} latest developments 2026",
            f"{topic} market size forecast",
            f"{topic} key companies products",
            f"{topic} official report statistics",
            f"{topic} risks and limitations",
        ]
        queries.extend(defaults)

        deduped: List[str] = []
        seen = set()
        for q in queries:
            key = q.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(q)

        return deduped[:6]

    def _merge_and_rank(self, rows: List[Dict]) -> List[Dict]:
        best_by_url: Dict[str, Dict] = {}

        for row in rows:
            url = row.get("canonical_url") or row.get("url")
            if not url:
                continue

            existing = best_by_url.get(url)
            if not existing:
                best_by_url[url] = dict(row)
                best_by_url[url]["query_hits"] = 1
                continue

            existing["query_hits"] = existing.get("query_hits", 1) + 1
            if float(row.get("score", 0.0)) > float(existing.get("score", 0.0)):
                for k, v in row.items():
                    existing[k] = v

        merged = list(best_by_url.values())
        merged.sort(
            key=lambda r: (
                float(r.get("score", 0.0)),
                float(r.get("source_score", 0.0)),
                float(r.get("relevance_score", 0.0)),
                int(r.get("query_hits", 1)),
            ),
            reverse=True,
        )
        return merged

    def _pick_diverse_sources(self, ranked_rows: List[Dict], target: int = 6) -> List[Dict]:
        chosen: List[Dict] = []
        seen_root_domains = set()
        seen_title_keys = set()

        # Pass 1: maximize source diversity by root-domain + title.
        for row in ranked_rows:
            domain = (row.get("domain") or "").lower()
            root_domain = self._root_domain(domain)
            title_key = self._title_key(row.get("title", ""))

            if root_domain and root_domain in seen_root_domains:
                continue
            if title_key and title_key in seen_title_keys:
                continue

            chosen.append(row)
            if root_domain:
                seen_root_domains.add(root_domain)
            if title_key:
                seen_title_keys.add(title_key)

            if len(chosen) >= target:
                return chosen

        # Pass 2: fill remaining slots by global rank but still avoid duplicate headlines.
        for row in ranked_rows:
            if row in chosen:
                continue
            title_key = self._title_key(row.get("title", ""))
            if title_key and title_key in seen_title_keys:
                continue
            chosen.append(row)
            if title_key:
                seen_title_keys.add(title_key)
            if len(chosen) >= target:
                break

        return chosen

    def _root_domain(self, domain: str) -> str:
        parts = [p for p in (domain or "").lower().split(".") if p]
        if len(parts) <= 2:
            return ".".join(parts)
        # Lightweight registrable-domain approximation.
        return ".".join(parts[-2:])

    def _title_key(self, title: str) -> str:
        words = re.findall(r"[a-z0-9]+", (title or "").lower())
        filtered = [w for w in words if len(w) > 2]
        return " ".join(filtered[:8])
