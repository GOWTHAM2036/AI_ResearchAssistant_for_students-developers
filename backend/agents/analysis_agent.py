"""
Analysis Agent: synthesizes researched evidence into structured insights.
Includes deterministic non-LLM synthesis so final output remains useful
when the model endpoint is unavailable.
"""
import re
from typing import Any, Callable, Dict, List, Optional

from backend.agents.base_agent import BaseAgent


SYSTEM_PROMPT = """You are an Analyst Agent. Below are REAL search results about '{topic}'.
Your job is to extract specific facts only.

INTENT-SPECIFIC FOCUS:
{intent_guidance}

SEARCH DATA:
{raw_search_text}

Strict output rules:
- Every insight must contain at least one concrete entity: company, product, number, percentage, or date.
- If data is weak, use: 'Insufficient data'.
- In the competitiveLandscape, identify actual entities (companies, products, organizations, frameworks, technologies).
- NEVER use domains, TLDs, or news websites (e.g. NEVER use 'insideevs', 'fleetworld', 'reuters.com' etc. as players).
- Return ONLY valid JSON with this schema:
{
  "insights": [
    {
      "headline": "specific headline",
      "body": "2-3 factual sentences",
      "priority": "Critical|High|Medium|Low",
      "source": "domain"
    }
  ],
  "executiveSummary": "3 concise factual sentences",
  "confidenceScore": 0.0,
  "competitiveLandscape": {
    "players": ["Player1", "Player2", "Player3"],
    "dimensions": ["Performance", "Cost", "Maturity", "Ecosystem"],
    "data": [
      ["v", "v", "v", "v"],
      ["v", "v", "v", "v"],
      ["v", "v", "v", "v"]
    ]
  }
}
"""

COMPANY_HINTS = [
    "NVIDIA",
    "AMD",
    "Intel",
    "Google",
    "Microsoft",
    "Amazon",
    "Meta",
    "OpenAI",
    "Anthropic",
    "Tesla",
    "Marvell",
    "TSMC",
    "Broadcom",
    "Qualcomm",
]

DOMAIN_PLAYER_MAP = {
    "nvidia.com": "NVIDIA",
    "amd.com": "AMD",
    "intel.com": "Intel",
    "google.com": "Google",
    "microsoft.com": "Microsoft",
    "amazon.com": "Amazon",
    "meta.com": "Meta",
    "openai.com": "OpenAI",
    "anthropic.com": "Anthropic",
    "marvell.com": "Marvell",
    "tsmc.com": "TSMC",
    "broadcom.com": "Broadcom",
    "qualcomm.com": "Qualcomm",
}


def _normalize_confidence(value):
    if value is None:
        return 0.5
    try:
        val = float(value)
    except (TypeError, ValueError):
        return 0.5

    if val > 1.0:
        return min(max(val / 100.0, 0.0), 1.0)
    return min(max(val, 0.0), 1.0)


def _avg_source_score(raw_results) -> float:
    if not raw_results:
        return 0.5
    vals = []
    for row in raw_results:
        try:
            vals.append(float(row.get("source_score", row.get("score", 0.5))))
        except (TypeError, ValueError):
            continue
    if not vals:
        return 0.5
    return max(0.0, min(1.0, sum(vals) / len(vals)))


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _is_generic_insight(insight: Dict) -> bool:
    headline = _clean(insight.get("headline", "")).lower()
    body = _clean(insight.get("body", "")).lower()
    return "insufficient data" in headline or "could not extract" in body


def _domain_to_label(domain: str) -> str:
    root = _root_domain(domain)
    mapped = DOMAIN_PLAYER_MAP.get(root)
    if mapped:
        return mapped

    raw = (root or "unknown").split(".")[0]
    if not raw:
        return "Unknown"
    return raw[:1].upper() + raw[1:]


def _root_domain(domain: str) -> str:
    parts = [p for p in (domain or "").lower().split(".") if p]
    if len(parts) <= 2:
        return ".".join(parts)
    return ".".join(parts[-2:])


class AnalysisAgent(BaseAgent):
    def __init__(self, emit: Optional[Callable] = None):
        super().__init__(
            name="Analyst",
            role="Data Synthesis and Insight Extraction",
            color="#059669",
            emit=emit,
        )

    def run(self, input_data: Any) -> dict:
        self.emit_status("working")

        topic = input_data.get("topic", "Unknown topic")
        intent = input_data.get("intent", "educational")
        search_strategy = input_data.get("search_strategy", "knowledge")
        raw_search_text = input_data.get("raw_search_text", "")
        raw_results = input_data.get("raw_results", [])
        raw_news = input_data.get("raw_news", [])

        self.emit_log(f"Analyzing {len(raw_search_text)} characters of evidence")

        # Dynamically customize intent focus instructions
        intent_guidance = ""
        if intent == "educational":
            intent_guidance = (
                "Since this is an Educational topic, focus your 5 key insights and executive summary on explaining the topic, "
                "detailing its advantages, disadvantages, practical applications, and addressing common FAQs."
            )
        elif intent == "comparison":
            intent_guidance = (
                "Since this is a Comparison topic, focus your 5 key insights and executive summary on comparing the options/entities, "
                "highlighting their strengths and weaknesses, comparing them across dimensions (e.g. Performance, Cost, Maturity, Ecosystem), "
                "and declaring/recommending a clear winner/recommendation."
            )
        elif intent == "latest_news":
            intent_guidance = (
                "Since this is a News topic, focus your 5 key insights and executive summary on a timeline of events, major developments, "
                "immediate industry/market impact, and future implications."
            )
        elif intent == "recommendation":
            intent_guidance = (
                "Since this is a Recommendation topic, focus your 5 key insights and executive summary on pros, cons, target audience "
                "(who should choose it), and price/performance value."
            )
        elif intent == "research":
            intent_guidance = (
                "Since this is a Research topic, focus your 5 key insights and executive summary on research methodology, empirical evidence, "
                "limitations of the studies, and areas/directions for future work."
            )
        elif intent == "tutorial":
            intent_guidance = (
                "Since this is a Tutorial topic, focus your 5 key insights and executive summary on step-by-step instructions, code/setup configuration, "
                "concrete examples, and common pitfalls."
            )
        elif intent == "troubleshooting":
            intent_guidance = (
                "Since this is a Troubleshooting topic, focus your 5 key insights and executive summary on error symptoms, root causes, "
                "diagnostic/investigation steps, and fix resolutions/prevention."
            )
        elif intent == "historical":
            intent_guidance = (
                "Since this is a Historical topic, focus your 5 key insights and executive summary on historical milestones, timeline, "
                "evolution of the topic, and long-term context."
            )
        elif intent == "opinion":
            intent_guidance = (
                "Since this is an Opinion/Analysis topic, focus your 5 key insights and executive summary on presenting balanced viewpoints, "
                "neutral and objective evaluation of different arguments, and expert perspectives."
            )
        else:
            intent_guidance = (
                "Focus your 5 key insights and executive summary on key facts, technical architecture, and future outlook."
            )

        prompt = SYSTEM_PROMPT.replace("{topic}", topic).replace("{raw_search_text}", raw_search_text).replace("{intent_guidance}", intent_guidance)
        user_prompt = f"Analyze the data and return strict JSON for topic: {topic}"

        fallback = self._build_fallback(topic)

        try:
            response_text = self.call_llm(prompt, user_prompt)
            analysis = self.parse_json(response_text, fallback)
            analysis = self._normalize_analysis(analysis, topic, raw_results, raw_news)

            if self._needs_deterministic_override(analysis):
                self.emit_log("LLM analysis weak; switching to deterministic evidence synthesis")
                analysis = self._build_from_sources(topic, raw_results, raw_news)

        except Exception as exc:
            self.emit_log(f"Analysis failed: {str(exc)[:120]} - using deterministic synthesis")
            analysis = self._build_from_sources(topic, raw_results, raw_news)
            
        analysis["intent"] = intent
        analysis["search_strategy"] = search_strategy
        
        self.emit_log(
            f"Analysis complete: {len(analysis['insights'])} insights, confidence {analysis['confidenceScore']}%"
        )
        self.emit_status("done")
        return analysis

    def _normalize_analysis(self, analysis: Dict, topic: str, raw_results: List[Dict], raw_news: List[Dict]) -> Dict:
        insights = analysis.get("insights", [])
        if not isinstance(insights, list):
            insights = []

        normalized_insights = []
        for ins in insights:
            if not isinstance(ins, dict):
                continue
            normalized_insights.append(
                {
                    "headline": _clean(ins.get("headline", "Insufficient data available")) or "Insufficient data available",
                    "body": _clean(ins.get("body", "Could not extract specific facts for this section."))
                    or "Could not extract specific facts for this section.",
                    "priority": _clean(ins.get("priority", "Medium")).title() or "Medium",
                    "source": _clean(ins.get("source", "Unknown")) or "Unknown",
                }
            )

        while len(normalized_insights) < 5:
            normalized_insights.append(
                {
                    "headline": "Insufficient data available",
                    "body": "Could not extract specific facts for this section.",
                    "priority": "Medium",
                    "source": "Unknown",
                }
            )

        analysis["insights"] = normalized_insights[:5]

        confidence_llm = _normalize_confidence(
            analysis.get("confidenceScore", analysis.get("confidence_score"))
        )
        confidence_sources = _avg_source_score(raw_results)
        confidence = (confidence_llm * 0.7) + (confidence_sources * 0.3)
        confidence_pct = int(round(max(0.0, min(1.0, confidence)) * 100))

        analysis["confidenceScore"] = confidence_pct
        analysis["confidence_score"] = round(confidence, 4)

        if not analysis.get("executiveSummary"):
            analysis["executiveSummary"] = f"Evidence summary generated for {topic}."

        competitive = analysis.get("competitiveLandscape")
        if not isinstance(competitive, dict):
            competitive = self._build_competitive(topic, raw_results)
        competitive.setdefault("players", ["Unknown", "Unknown", "Unknown"])
        competitive.setdefault("dimensions", ["Performance", "Cost", "Maturity", "Ecosystem"])
        competitive.setdefault(
            "data",
            [
                ["-", "-", "-", "-"],
                ["-", "-", "-", "-"],
                ["-", "-", "-", "-"],
            ],
        )
        analysis["competitiveLandscape"] = competitive

        analysis["topic"] = topic
        analysis["raw_results"] = raw_results
        analysis["raw_news"] = raw_news
        return analysis

    def _needs_deterministic_override(self, analysis: Dict) -> bool:
        insights = analysis.get("insights", [])
        if not insights:
            return True
        generic_count = sum(1 for ins in insights if _is_generic_insight(ins))
        summary = _clean(analysis.get("executiveSummary", "")).lower()
        weak_summary = ("unable to parse" in summary) or (len(summary) < 40)
        return generic_count >= 3 or weak_summary

    def _build_from_sources(self, topic: str, raw_results: List[Dict], raw_news: List[Dict]) -> Dict:
        if not raw_results:
            fb = self._build_fallback(topic)
            fb["raw_news"] = raw_news
            return fb

        top = raw_results[:5]
        insights = []
        for idx, row in enumerate(top, 1):
            title = _clean(row.get("title", f"Source insight {idx}"))
            snippet = _clean(row.get("snippet", ""))
            domain = _clean(row.get("domain", "Unknown"))
            date_value = _clean(row.get("date", ""))
            score = float(row.get("score", row.get("source_score", 0.5)))
            score_pct = int(round(max(0.0, min(1.0, score)) * 100))

            priority = "Medium"
            if idx == 1 and score >= 0.8:
                priority = "Critical"
            elif idx <= 2:
                priority = "High"

            headline = title
            body_parts = []
            if snippet:
                body_parts.append(snippet)
            if date_value:
                body_parts.append(f"The source references timing around {date_value}.")
            body_parts.append(f"Source credibility signal from {domain} is {score_pct}% in the ranking pipeline.")
            body = " ".join(body_parts)

            insights.append(
                {
                    "headline": headline,
                    "body": body,
                    "priority": priority,
                    "source": domain or "Unknown",
                }
            )

        while len(insights) < 5:
            filler = raw_results[min(len(raw_results) - 1, 0)] if raw_results else {}
            insights.append(
                {
                    "headline": _clean(filler.get("title", "Additional market signal")) or "Additional market signal",
                    "body": _clean(filler.get("snippet", "More source data is available in the references section."))
                    or "More source data is available in the references section.",
                    "priority": "Medium",
                    "source": _clean(filler.get("domain", "Unknown")) or "Unknown",
                }
            )

        domains = []
        for row in raw_results[:4]:
            d = _clean(row.get("domain", ""))
            label = _domain_to_label(d) if d else ""
            if label and label not in domains and label != "Unknown":
                domains.append(label)
        domain_text = ", ".join(domains[:3]) if domains else "multiple sources"

        summary = (
            f"Recent coverage on {topic} indicates active enterprise momentum across major vendors and partners. "
            f"Top-ranked signals include: {insights[0]['headline']}; {insights[1]['headline']}; and {insights[2]['headline']}. "
            f"Evidence quality is strongest from {domain_text}, based on retrieval relevance and source-scoring."
        )

        source_conf = _avg_source_score(raw_results)
        volume_bonus = min(0.15, len(raw_results) * 0.02)
        confidence = min(0.95, source_conf + volume_bonus)

        return {
            "insights": insights[:5],
            "executiveSummary": summary,
            "confidenceScore": int(round(confidence * 100)),
            "confidence_score": round(confidence, 4),
            "competitiveLandscape": self._build_competitive(topic, raw_results),
            "topic": topic,
            "raw_results": raw_results,
            "raw_news": raw_news,
        }

    def _build_competitive(self, topic: str, raw_results: List[Dict]) -> Dict:
        # Extract entities using LLM reasoning from titles and snippets
        corpus_list = []
        for r in raw_results[:8]:
            title = r.get("title", "")
            snippet = r.get("snippet", "")
            if title or snippet:
                corpus_list.append(f"- Title: {title} | Snippet: {snippet}")
        corpus = "\n".join(corpus_list)

        system_prompt = (
            "You are an entity extractor. Identify the top 3 actual entities (companies, products, organizations, frameworks, technologies) "
            "relevant to the topic from the provided search results. "
            "Do NOT extract domains, news websites, TLDs, or search engine names (e.g. avoid 'techcrunch.com', 'insideevs', 'fleetworld', 'google search', etc.). "
            "Return ONLY a JSON list of strings, for example: [\"Entity1\", \"Entity2\", \"Entity3\"]."
        )
        user_prompt = f"Topic: {topic}\nSearch Results:\n{corpus}"

        players = []
        if getattr(self, "client", None) is not None:
            try:
                res = self.call_llm(system_prompt, user_prompt, temperature=0.1)
                players = self.parse_json(res, [])
                if not isinstance(players, list):
                    players = []
                players = [str(p).strip() for p in players if p and str(p).strip()]
            except Exception as exc:
                if hasattr(self, "_emit"):
                    self.emit_log(f"Entity extraction LLM call failed: {exc}")

        # Fallback to topic seeds if LLM fails or doesn't return enough players
        for seed in self._topic_seed_players(topic):
            if seed not in players:
                players.append(seed)

        # If still not enough, let's fall back to predefined COMPANY_HINTS that are in the corpus
        corpus_lower = corpus.lower()
        for name in COMPANY_HINTS:
            if name.lower() in corpus_lower and name not in players:
                players.append(name)
            if len(players) >= 3:
                break

        # Filter out domains or typical news/TLD sites just in case
        clean_players = []
        for p in players:
            p_lower = p.lower()
            if any(ext in p_lower for ext in [".com", ".org", ".net", ".co.uk", "insideevs", "fleetworld", "news", "press"]):
                continue
            if p not in clean_players:
                clean_players.append(p)

        players = clean_players[:3]
        while len(players) < 3:
            players.append("Unknown")

        dimensions = ["Performance", "Cost", "Maturity", "Ecosystem"]
        data = []
        for idx, player in enumerate(players[:3]):
            if player == "Unknown":
                data.append(["Unknown", "Unknown", "Unknown", "Unknown"])
                continue

            if idx == 0:
                data.append(["High", "Premium", "High", "High"])
            elif idx == 1:
                data.append(["High", "Medium", "Medium", "High"])
            else:
                data.append(["Medium", "Flexible", "Medium", "Medium"])

        return {
            "players": players[:3],
            "dimensions": dimensions,
            "data": data,
        }

    def _topic_seed_players(self, topic: str) -> List[str]:
        t = (topic or "").lower()
        if "nvidia" in t:
            return ["NVIDIA", "AMD", "Google"]
        if "amd" in t:
            return ["AMD", "NVIDIA", "Intel"]
        if "intel" in t:
            return ["Intel", "NVIDIA", "AMD"]
        if "openai" in t:
            return ["OpenAI", "Anthropic", "Google"]
        return []

    def _build_fallback(self, topic: str) -> dict:
        return {
            "insights": [
                {
                    "headline": "Insufficient data available",
                    "body": "Could not extract specific facts for this section.",
                    "priority": "Medium",
                    "source": "Unknown",
                }
                for _ in range(5)
            ],
            "executiveSummary": f"Unable to parse deep analysis for {topic}.",
            "confidenceScore": 50,
            "confidence_score": 0.5,
            "competitiveLandscape": {
                "players": ["Unknown", "Unknown", "Unknown"],
                "dimensions": ["Performance", "Cost", "Maturity", "Ecosystem"],
                "data": [
                    ["-", "-", "-", "-"],
                    ["-", "-", "-", "-"],
                    ["-", "-", "-", "-"],
                ],
            },
            "topic": topic,
            "raw_results": [],
            "raw_news": [],
        }
