"""
Manager Agent: creates a stable, complete research plan.
"""
from typing import Any, Callable, Optional

from backend.agents.base_agent import BaseAgent


SYSTEM_PROMPT = """You are the Manager Agent of an autonomous AI Research Crew.

Return ONLY valid JSON using this exact schema:
{
  "topic": "<original topic from user>",
  "briefing_title": "<short clean title, max 8 words>",
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
- Cover: latest developments, technical details, market/commercial data, key players, risks/future outlook.
- Keep queries concise and search-engine friendly.
"""


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

        fallback = {
            "topic": topic,
            "briefing_title": topic,
            "search_queries": [
                f"{topic} latest developments 2026",
                f"{topic} technical architecture explained",
                f"{topic} market size and forecast",
                f"{topic} key companies products comparison",
                f"{topic} future outlook risks",
            ],
            "focus_areas": [
                "Technology advancements",
                "Market and business impact",
                "Risks and future trajectory",
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
                f"Plan ready: {len(plan['search_queries'])} queries, {len(plan['focus_areas'])} focus areas"
            )
            self.emit_status("done")
            return plan

        except Exception as exc:
            self.emit_log(f"Manager failed: {str(exc)[:120]} - using fallback plan")
            self.emit_status("done")
            return fallback
