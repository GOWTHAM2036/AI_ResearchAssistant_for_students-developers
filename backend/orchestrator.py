"""
Orchestrator: chains agents and streams SSE events.
Pipeline: Manager -> Research -> Analysis -> Writer -> Delivery
"""
import json
import time
from typing import Generator

from backend.agents.analysis_agent import AnalysisAgent
from backend.agents.delivery_agent import DeliveryAgent
from backend.agents.manager_agent import ManagerAgent, build_queries
from backend.agents.research_agent import ResearchAgent
from backend.agents.writer_agent import WriterAgent
from backend.history_store import save_history_entry


class Orchestrator:
    """Runs the full 5-agent pipeline as a streaming generator."""

    def run(self, topic: str, email: str = "") -> Generator[str, None, None]:
        events = []

        def emit(event_type: str, payload: dict):
            events.append({"type": event_type, **payload})

        def flush_events() -> Generator[str, None, None]:
            while events:
                ev = events.pop(0)
                yield f"data: {json.dumps(ev)}\n\n"

        start = time.time()

        emit("pipeline", {"status": "started", "topic": topic})
        yield from flush_events()

        # Stage 1: Manager
        try:
            emit(
                "log",
                {
                    "agent": "System",
                    "color": "#64748b",
                    "message": "Stage 1/5: Manager Agent - Planning",
                    "timestamp": time.time(),
                },
            )
            yield from flush_events()

            manager = ManagerAgent(emit=emit)
            plan = manager.run({"topic": topic})
            yield from flush_events()

            emit(
                "result",
                {
                    "agent": "Manager",
                    "data": {
                        "intent": plan.get("intent", "educational"),
                        "search_strategy": plan.get("search_strategy", "knowledge"),
                        "search_queries": len(plan.get("search_queries", [])),
                        "focus_areas": len(plan.get("focus_areas", [])),
                    },
                },
            )
            yield from flush_events()

        except Exception as exc:
            emit("error", {"agent": "Manager", "message": str(exc)[:200]})
            yield from flush_events()
            
            # Simple heuristic fallback classification
            topic_l = topic.lower()
            inferred_intent = "educational"
            if any(kw in topic_l for kw in ["latest", "news", "recent", "update", "developments", "announcement"]):
                inferred_intent = "latest_news"
            elif any(kw in topic_l for kw in ["vs", "compare", "comparison", "difference between", "alternative"]):
                inferred_intent = "comparison"
            elif any(kw in topic_l for kw in ["how to", "tutorial", "guide", "steps", "install", "setup"]):
                inferred_intent = "tutorial"
            
            inferred_strategy = "knowledge"
            if inferred_intent == "latest_news":
                inferred_strategy = "news"
            elif inferred_intent == "comparison":
                inferred_strategy = "comparison"
            elif inferred_intent == "tutorial":
                inferred_strategy = "tutorial"

            fallback_queries = build_queries(topic, inferred_intent)
            plan = {
                "topic": topic,
                "intent": inferred_intent,
                "search_strategy": inferred_strategy,
                "search_queries": fallback_queries,
                "focus_areas": ["Overview and Context"],
            }

        # Stage 2: Research
        try:
            emit(
                "log",
                {
                    "agent": "System",
                    "color": "#64748b",
                    "message": "Stage 2/5: Research Agent - Web Search",
                    "timestamp": time.time(),
                },
            )
            yield from flush_events()

            researcher = ResearchAgent(emit=emit)
            research_data = researcher.run(plan)
            yield from flush_events()

            emit(
                "result",
                {
                    "agent": "Researcher",
                    "data": {
                        "total_sources": research_data.get("total_sources", 0),
                        "queries_executed": research_data.get("queries_executed", 0),
                    },
                },
            )
            yield from flush_events()

        except Exception as exc:
            emit("error", {"agent": "Researcher", "message": str(exc)[:200]})
            yield from flush_events()
            research_data = {
                "topic": topic,
                "intent": plan.get("intent", "educational"),
                "search_strategy": plan.get("search_strategy", "knowledge"),
                "focus_areas": plan.get("focus_areas", []),
                "raw_search_text": "",
                "queries_executed": 0,
                "total_sources": 0,
                "raw_results": [],
                "raw_news": [],
            }

        # Stage 3: Analysis
        try:
            emit(
                "log",
                {
                    "agent": "System",
                    "color": "#64748b",
                    "message": "Stage 3/5: Analysis Agent - Synthesizing",
                    "timestamp": time.time(),
                },
            )
            yield from flush_events()

            analyst = AnalysisAgent(emit=emit)
            analysis = analyst.run(research_data)
            yield from flush_events()

            emit(
                "result",
                {
                    "agent": "Analyst",
                    "data": {
                        "insights_count": len(analysis.get("insights", [])),
                        "confidence": analysis.get("confidenceScore", 0),
                    },
                },
            )
            yield from flush_events()

        except Exception as exc:
            emit("error", {"agent": "Analyst", "message": str(exc)[:200]})
            yield from flush_events()
            analysis = {
                "topic": topic,
                "intent": research_data.get("intent", "educational"),
                "search_strategy": research_data.get("search_strategy", "knowledge"),
                "insights": [],
                "executiveSummary": f"Analysis failed for {topic}",
                "confidenceScore": 40,
                "competitiveLandscape": {
                    "players": ["Unknown", "Unknown", "Unknown"],
                    "dimensions": ["Performance", "Cost", "Maturity", "Ecosystem"],
                    "data": [["-", "-", "-", "-"]] * 3,
                },
                "raw_results": research_data.get("raw_results", []),
                "raw_news": research_data.get("raw_news", []),
            }

        # Stage 4: Writer
        try:
            emit(
                "log",
                {
                    "agent": "System",
                    "color": "#64748b",
                    "message": "Stage 4/5: Writer Agent - Drafting Briefing",
                    "timestamp": time.time(),
                },
            )
            yield from flush_events()

            writer = WriterAgent(emit=emit)
            briefing = writer.run(analysis)
            yield from flush_events()

            emit(
                "result",
                {
                    "agent": "Writer",
                    "data": {"word_count": briefing.get("word_count", 0)},
                },
            )
            yield from flush_events()

        except Exception as exc:
            emit("error", {"agent": "Writer", "message": str(exc)[:200]})
            yield from flush_events()
            briefing = {
                "topic": topic,
                "intent": analysis.get("intent", "educational"),
                "search_strategy": analysis.get("search_strategy", "knowledge"),
                "html": "<p>Briefing generation failed.</p>",
                "word_count": 0,
            }

        # Stage 5: Delivery
        try:
            emit(
                "log",
                {
                    "agent": "System",
                    "color": "#64748b",
                    "message": "Stage 5/5: Delivery Agent - Distribution",
                    "timestamp": time.time(),
                },
            )
            yield from flush_events()

            delivery_input = {
                "topic": topic,
                "html": briefing.get("html", ""),
                "email": email,
                "intent": briefing.get("intent", "educational"),
                "search_strategy": briefing.get("search_strategy", "knowledge"),
            }
            delivery = DeliveryAgent(emit=emit)
            result = delivery.run(delivery_input)
            yield from flush_events()

        except Exception as exc:
            emit("error", {"agent": "Delivery", "message": str(exc)[:200]})
            yield from flush_events()
            result = {
                "delivered": False,
                "message": str(exc),
                "html": briefing.get("html", ""),
            }

        elapsed = round(time.time() - start, 1)
        history_id = None

        final_html = result.get("html", briefing.get("html", ""))
        delivery_message = result.get("message", "")
        delivered = result.get("delivered", False)

        try:
            history_id = save_history_entry(
                topic=topic,
                email=result.get("email", email),
                delivered=bool(delivered),
                delivery_message=delivery_message,
                elapsed_seconds=elapsed,
                html=final_html,
            )
        except Exception as exc:
            emit(
                "log",
                {
                    "agent": "System",
                    "color": "#f59e0b",
                    "message": f"History save warning: {str(exc)[:120]}",
                    "timestamp": time.time(),
                },
            )

        emit(
            "log",
            {
                "agent": "System",
                "color": "#22c55e",
                "message": f"Pipeline complete in {elapsed}s",
                "timestamp": time.time(),
            },
        )

        emit(
            "pipeline",
            {
                "status": "complete",
                "elapsed": elapsed,
                "html": final_html,
                "delivered": delivered,
                "delivery_message": delivery_message,
                "history_id": history_id,
            },
        )
        yield from flush_events()
