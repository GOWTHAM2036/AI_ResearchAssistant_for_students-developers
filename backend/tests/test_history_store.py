import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.history_store import get_history_entry, save_history_entry, list_history_entries


class HistoryStoreTests(unittest.TestCase):
    def test_save_and_get_history_entry(self):
        new_id = save_history_entry(
            topic="History Store Test",
            email="",
            delivered=False,
            delivery_message="Saved for UI",
            elapsed_seconds=1.2,
            html="<html><body>test</body></html>",
        )
        self.assertGreater(new_id, 0)

        entry = get_history_entry(new_id)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["id"], new_id)
        self.assertEqual(entry["topic"], "History Store Test")
        self.assertIn("<html>", entry["html"])

    def test_list_history_entries_returns_rows(self):
        save_history_entry(
            topic="History Store List Seed",
            email="",
            delivered=False,
            delivery_message="seed",
            elapsed_seconds=0.5,
            html="<html><body>seed</body></html>",
        )
        rows = list_history_entries(limit=5)
        self.assertIsInstance(rows, list)
        self.assertGreaterEqual(len(rows), 1)
        self.assertIn("id", rows[0])
        self.assertIn("topic", rows[0])


if __name__ == "__main__":
    unittest.main()
