import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.agents.research_agent import ResearchAgent


class ResearchAgentHelpersTests(unittest.TestCase):
    def setUp(self):
        # Avoid BaseAgent initialization; helper methods under test do not need it.
        self.agent = ResearchAgent.__new__(ResearchAgent)

    def test_merge_and_rank_keeps_best_by_url_and_counts_hits(self):
        rows = [
            {
                "url": "https://example.com/a",
                "canonical_url": "https://example.com/a",
                "score": 0.7,
                "source_score": 0.6,
                "relevance_score": 0.8,
                "domain": "example.com",
            },
            {
                "url": "https://example.com/a",
                "canonical_url": "https://example.com/a",
                "score": 0.9,
                "source_score": 0.7,
                "relevance_score": 0.9,
                "domain": "example.com",
            },
            {
                "url": "https://another.com/b",
                "canonical_url": "https://another.com/b",
                "score": 0.6,
                "source_score": 0.9,
                "relevance_score": 0.4,
                "domain": "another.com",
            },
        ]

        merged = self.agent._merge_and_rank(rows)
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["url"], "https://example.com/a")
        self.assertEqual(merged[0]["query_hits"], 2)
        self.assertEqual(merged[0]["score"], 0.9)

    def test_pick_diverse_sources_prioritizes_domain_diversity(self):
        ranked = [
            {"url": "https://a.com/1", "domain": "a.com", "score": 0.95},
            {"url": "https://a.com/2", "domain": "a.com", "score": 0.93},
            {"url": "https://b.com/1", "domain": "b.com", "score": 0.9},
            {"url": "https://c.com/1", "domain": "c.com", "score": 0.89},
        ]
        selected = self.agent._pick_diverse_sources(ranked, target=3)
        domains = [row["domain"] for row in selected]
        self.assertEqual(len(selected), 3)
        self.assertEqual(domains[0], "a.com")
        self.assertEqual(len(set(domains)), 3)


if __name__ == "__main__":
    unittest.main()
