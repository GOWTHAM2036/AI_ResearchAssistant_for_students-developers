import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.agents.analysis_agent import AnalysisAgent
from backend.agents.writer_agent import WriterAgent


class AgentFallbackTests(unittest.TestCase):
    def test_analysis_builds_deterministic_insights_from_sources(self):
        agent = AnalysisAgent.__new__(AnalysisAgent)
        raw_results = [
            {
                "title": "Nvidia invests $2 billion in Marvell AI partnership",
                "snippet": "Reuters reported a $2 billion investment to accelerate AI infrastructure.",
                "domain": "reuters.com",
                "score": 0.91,
                "source_score": 0.9,
                "date": "2026-03-31",
            },
            {
                "title": "Google challenges Nvidia with new chips",
                "snippet": "Google introduced new accelerator chips for enterprise AI workloads.",
                "domain": "latimes.com",
                "score": 0.79,
                "source_score": 0.77,
                "date": "2026-04-20",
            },
        ]

        analysis = agent._build_from_sources(
            topic="NVIDIA AI chips 2026 roadmap and enterprise adoption",
            raw_results=raw_results,
            raw_news=[],
        )
        self.assertEqual(len(analysis["insights"]), 5)
        self.assertNotIn("Insufficient data", analysis["insights"][0]["headline"])
        self.assertGreaterEqual(analysis["confidenceScore"], 60)
        self.assertIn("competitiveLandscape", analysis)
        self.assertEqual(len(analysis["competitiveLandscape"]["players"]), 3)

    def test_writer_fallback_includes_competitive_table_and_sources(self):
        writer = WriterAgent.__new__(WriterAgent)
        html_doc = writer._wrap_fallback_html(
            topic="NVIDIA AI chips 2026 roadmap and enterprise adoption",
            summary="Enterprise demand for accelerated AI compute is rising.",
            insights=[
                {
                    "headline": "Nvidia expands enterprise partnerships",
                    "body": "Major vendors announced integrations and infrastructure programs.",
                    "priority": "High",
                    "source": "reuters.com",
                }
            ]
            * 5,
            confidence=78,
            sources=[
                {
                    "type": "web",
                    "title": "Reuters coverage",
                    "url": "https://reuters.com/example",
                    "domain": "reuters.com",
                    "date": "2026-03-31",
                }
            ],
            competitive={
                "players": ["NVIDIA", "Google", "AMD"],
                "dimensions": ["Performance", "Cost", "Maturity", "Ecosystem"],
                "data": [
                    ["High", "Premium", "High", "High"],
                    ["High", "Medium", "Medium", "High"],
                    ["Medium", "Flexible", "Medium", "Medium"],
                ],
            },
        )
        self.assertIn("Competitive Landscape", html_doc)
        self.assertIn("<table", html_doc)
        self.assertIn("https://reuters.com/example", html_doc)


if __name__ == "__main__":
    unittest.main()
