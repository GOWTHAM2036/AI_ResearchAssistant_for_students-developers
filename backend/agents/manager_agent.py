from typing import Any, Callable, List, Optional

from backend.agents.base_agent import BaseAgent


SYSTEM_PROMPT = """You are the Manager Agent of an autonomous AI Research Crew.

Your task is to classify the user's topic query into one of these intents:
- educational: Topic explanations, definitions, advantages, disadvantages, guide, ICE comparison
- latest_news: Recent news, announcements, earnings, developments in 2026
- comparison: Product comparisons, head-to-head comparisons, feature/pricing matchups (e.g. Tesla vs BYD)
- tutorial: Setup guides, code examples, how-to procedures, configuration steps
- research: Academic topics, scientific research, benchmarks, whitepapers
- troubleshooting: Fixing errors, resolving bugs, troubleshooting specific issues
- recommendation: Best/top choices, reviews, recommendations, alternative options
- historical: History of a technology, timelines, evolution, milestones
- opinion: Balanced perspectives, debate/viewpoints from multiple angles on a topic

Map the classified intent to one of the following search strategies:
- educational, historical, opinion -> knowledge
- latest_news -> news
- comparison, recommendation -> comparison
- tutorial, troubleshooting -> tutorial
- research -> research

Return ONLY valid JSON using this exact schema:
{
  "intent": "<classified intent>",
  "topic": "<original topic from user>",
  "briefing_title": "<short clean title, max 8 words>",
  "search_strategy": "<mapped search strategy>",
  "search_queries": [
    "query 1",
    "query 2",
    "query 3",
    "query 4",
    "query 5"
  ],
  "focus_areas": ["area 1", "area 2", "area 3"],
  "deliverable_format": "HTML Technical Briefing",
  "priority": "high"
}

Rules:
- Generate exactly 5 diverse, specific search queries.
- Generate queries strictly tailored to the intent. Do NOT mix news queries with educational topics, or general tutorials with troubleshooting errors.
- Keep queries concise and search-engine friendly.
"""


def build_queries(topic: str, intent: str) -> List[str]:
    """Generate fallback/completion search queries based on intent and topic."""
    topic = (topic or "").strip()
    intent = (intent or "educational").lower()

    if intent == "educational":
        return [
            f"{topic} explained",
            f"advantages of {topic}",
            f"{topic} benefits",
            f"{topic} guide",
            f"{topic} pros and cons",
        ]
    elif intent == "comparison":
        import re
        parts = re.split(r"\s+vs\s+|\s+compared\s+to\s+", topic, flags=re.IGNORECASE)
        if len(parts) >= 2:
            e1 = parts[0].strip()
            e2 = parts[1].strip()
            # EV/Car comparison check
            ev_terms = ["tesla", "byd", "ev", "electric", "battery", "vehicle", "car", "truck"]
            is_ev = any(kw in topic.lower() for kw in ev_terms)
            spec_term = "battery" if is_ev else "specifications"
            return [
                topic,
                f"{e1} {e2} comparison",
                f"{topic} pricing",
                f"{topic} {spec_term}",
                f"{topic} performance",
            ]
        return [
            topic,
            f"{topic} comparison",
            f"{topic} comparison features",
            f"{topic} comparison cost",
            f"{topic} comparison performance",
        ]
    elif intent == "latest_news":
        return [
            f"{topic} latest news",
            f"{topic} developments 2026",
            f"{topic} earnings",
            f"{topic} announcements",
            f"{topic} updates",
        ]
    elif intent == "research":
        return [
            f"{topic} research papers",
            f"{topic} technical documentation",
            f"{topic} benchmarks",
            f"{topic} whitepapers",
            f"{topic} official documentation",
        ]
    elif intent == "troubleshooting":
        return [
            f"{topic} error",
            f"{topic} fix",
            f"{topic} documentation",
            f"{topic} github issues",
            f"{topic} stackoverflow",
        ]
    elif intent == "recommendation":
        return [
            f"best {topic}",
            f"top {topic}",
            f"{topic} alternatives",
            f"{topic} reviews",
            f"{topic} comparison",
        ]
    elif intent == "historical":
        return [
            f"{topic} history",
            f"{topic} timeline",
            f"{topic} evolution",
            f"{topic} milestones",
            f"{topic} origin",
        ]
    elif intent == "opinion":
        return [
            f"{topic} viewpoints",
            f"{topic} perspectives",
            f"{topic} reviews",
            f"{topic} pros and cons",
            f"{topic} analysis",
        ]
    elif intent == "tutorial":
        return [
            f"{topic} tutorial",
            f"{topic} guide",
            f"{topic} step by step",
            f"{topic} examples",
            f"{topic} documentation",
        ]
    else:
        return [
            f"{topic} explained",
            f"{topic} advantages",
            f"{topic} comparison",
            f"{topic} latest developments",
            f"{topic} future outlook",
        ]


class ManagerAgent(BaseAgent):
    def __init__(self, emit: Optional[Callable] = None):
        super().__init__(
            name="Manager",
            role="Research Planning and Delegation",
            color="#7c3aed",
            emit=emit,
        )

    def run(self, input_data: Any) -> dict:
        self.emit_status("working")
        topic = (input_data.get("topic") or "AI technology").strip()

        self.emit_log(f"Received research request: '{topic}'")
        self.emit_log("Generating structured research plan")

        # Programmatically determine fallback intent and strategy
        topic_l = topic.lower()
        fallback_intent = "educational"
        if any(kw in topic_l for kw in ["latest", "news", "recent", "update", "developments", "announcement"]):
            fallback_intent = "latest_news"
        elif any(kw in topic_l for kw in ["vs", "compare", "comparison", "difference between", "alternative"]):
            fallback_intent = "comparison"
        elif any(kw in topic_l for kw in ["how to", "tutorial", "guide", "steps", "install", "setup"]):
            fallback_intent = "tutorial"
        elif any(kw in topic_l for kw in ["research", "paper", "study", "benchmark", "arxiv", "scholar"]):
            fallback_intent = "research"
        elif any(kw in topic_l for kw in ["error", "fix", "bug", "issue", "troubleshoot", "fails"]):
            fallback_intent = "troubleshooting"
        elif any(kw in topic_l for kw in ["best", "top", "recommend", "review"]):
            fallback_intent = "recommendation"
        elif any(kw in topic_l for kw in ["history", "timeline", "evolution", "historical", "ancient", "origin"]):
            fallback_intent = "historical"
        elif any(kw in topic_l for kw in ["should", "opinion", "why", "what do you think", "pros and cons"]):
            fallback_intent = "opinion"

        fallback_strategy = "knowledge"
        if fallback_intent in ["educational", "historical", "opinion"]:
            fallback_strategy = "knowledge"
        elif fallback_intent == "latest_news":
            fallback_strategy = "news"
        elif fallback_intent in ["comparison", "recommendation"]:
            fallback_strategy = "comparison"
        elif fallback_intent in ["tutorial", "troubleshooting"]:
            fallback_strategy = "tutorial"
        elif fallback_intent == "research":
            fallback_strategy = "research"

        fallback_queries = build_queries(topic, fallback_intent)

        fallback = {
            "topic": topic,
            "briefing_title": topic,
            "intent": fallback_intent,
            "search_strategy": fallback_strategy,
            "search_queries": fallback_queries,
            "focus_areas": [
                "Overview and Context",
                "Key Insights",
                "Future Trajectory",
            ],
            "deliverable_format": "HTML Technical Briefing",
            "priority": "high",
        }

        user_prompt = (
            f"User topic: {topic}\n\n"
            "Create the JSON research plan now. "
            "Keep topic unchanged and create a separate short briefing_title."
        )

        try:
            response_text = self.call_llm(SYSTEM_PROMPT, user_prompt)
            plan = self.parse_json(response_text, fallback)

            # Keep original topic stable for retrieval quality.
            plan["topic"] = topic
            plan.setdefault("intent", fallback_intent)
            plan.setdefault("search_strategy", fallback_strategy)
            plan.setdefault("briefing_title", topic)
            plan.setdefault("deliverable_format", "HTML Technical Briefing")
            plan.setdefault("priority", "high")

            queries = [str(q).strip() for q in plan.get("search_queries", []) if str(q).strip()]
            deduped_queries = []
            seen = set()
            for q in queries:
                k = q.lower()
                if k in seen:
                    continue
                seen.add(k)
                deduped_queries.append(q)

            for q in fallback["search_queries"]:
                if len(deduped_queries) >= 5:
                    break
                if q.lower() not in seen:
                    deduped_queries.append(q)
                    seen.add(q.lower())

            plan["search_queries"] = deduped_queries[:5]

            focus_areas = [str(a).strip() for a in plan.get("focus_areas", []) if str(a).strip()]
            for area in fallback["focus_areas"]:
                if len(focus_areas) >= 3:
                    break
                if area not in focus_areas:
                    focus_areas.append(area)
            plan["focus_areas"] = focus_areas[:3]

            self.emit_log(
                f"Plan ready: intent={plan['intent']}, strategy={plan['search_strategy']}, {len(plan['search_queries'])} queries"
            )
            self.emit_status("done")
            return plan

        except Exception as exc:
            self.emit_log(f"Manager failed: {str(exc)[:120]} - using fallback plan")
            self.emit_status("done")
            return fallback

