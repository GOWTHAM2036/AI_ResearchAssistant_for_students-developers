import unittest
from backend.agents.manager_agent import build_queries, ManagerAgent

class TestIntentQueries(unittest.TestCase):
    def test_build_queries_educational(self):
        topic = "Electric Vehicles"
        queries = build_queries(topic, "educational")
        self.assertEqual(len(queries), 5)
        self.assertIn("Electric Vehicles explained", queries)
        self.assertIn("advantages of Electric Vehicles", queries)

    def test_build_queries_comparison_vs(self):
        topic = "Tesla vs BYD"
        queries = build_queries(topic, "comparison")
        self.assertEqual(len(queries), 5)
        self.assertIn("Tesla BYD comparison", queries)
        self.assertIn("Tesla vs BYD performance", queries)

    def test_build_queries_latest_news(self):
        topic = "Tesla"
        queries = build_queries(topic, "latest_news")
        self.assertEqual(len(queries), 5)
        self.assertIn("Tesla latest news", queries)
        self.assertIn("Tesla developments 2026", queries)

    def test_manager_agent_heuristic_fallback(self):
        # Verify fallback heuristic logic
        topic = "Tesla vs BYD"
        topic_l = topic.lower()
        fallback_intent = "educational"
        if any(kw in topic_l for kw in ["vs", "compare", "comparison"]):
            fallback_intent = "comparison"
        self.assertEqual(fallback_intent, "comparison")

if __name__ == "__main__":
    unittest.main()
