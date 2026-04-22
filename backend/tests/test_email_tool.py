import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.tools.email_tool import _normalize_recipients, send_email


class EmailToolTests(unittest.TestCase):
    def test_normalize_recipients_dedupes(self):
        recipients = _normalize_recipients("a@example.com; b@example.com, a@example.com")
        self.assertEqual(recipients, ["a@example.com", "b@example.com"])

    def test_send_email_rejects_invalid_address(self):
        result = send_email("not-an-email", "Test", "<p>hi</p>")
        self.assertFalse(result["success"])
        self.assertIn("Invalid recipient email", result["message"])


if __name__ == "__main__":
    unittest.main()
