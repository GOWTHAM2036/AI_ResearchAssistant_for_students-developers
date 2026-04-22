import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.tools.web_search import fetch_article_body, normalize_url, rank_results


class DummyResponse:
    def __init__(self, text, status_code=200, headers=None):
        self.text = text
        self.status_code = status_code
        self.headers = headers or {"Content-Type": "text/html; charset=utf-8"}


class WebSearchTests(unittest.TestCase):
    def test_normalize_url_removes_tracking_and_fragment(self):
        url = "https://www.example.com/path/?utm_source=x&b=2&a=1#section"
        normalized = normalize_url(url)
        self.assertEqual(normalized, "https://example.com/path?a=1&b=2")

    def test_rank_results_dedupes_and_prefers_higher_quality(self):
        raw = [
            {
                "title": "NVIDIA reports AI chip growth",
                "href": "https://www.reuters.com/world/us/nvidia-ai-chip-growth/?utm_source=x",
                "body": "NVIDIA reported quarterly revenue growth with strong demand for AI chips across cloud providers.",
            },
            {
                "title": "NVIDIA reports AI chip growth",
                "href": "https://www.reuters.com/world/us/nvidia-ai-chip-growth/",
                "body": "Short.",
            },
            {
                "title": "Cool board",
                "href": "https://www.pinterest.com/ideas/chips/",
                "body": "Images and inspiration.",
            },
        ]

        ranked = rank_results("nvidia ai chip revenue", raw, max_results=5)
        self.assertEqual(len(ranked), 2)
        self.assertEqual(ranked[0]["domain"], "reuters.com")
        self.assertGreater(ranked[0]["score"], ranked[1]["score"])

    @patch("requests.get")
    def test_fetch_article_body_prefers_article_content(self, mock_get):
        html = """
        <html>
          <body>
            <nav>menu links</nav>
            <article>
              <p>NVIDIA announced a new architecture with improved throughput for inference workloads.</p>
              <p>The company reported that demand continues from hyperscale cloud providers.</p>
            </article>
            <footer>footer links</footer>
          </body>
        </html>
        """
        mock_get.return_value = DummyResponse(html)

        text = fetch_article_body("https://example.com/story")
        self.assertIn("NVIDIA announced a new architecture", text)
        self.assertNotIn("menu links", text)


if __name__ == "__main__":
    unittest.main()
