"""View model and source-selection tests independent of desktop environment."""
import time
import unittest
from ui_models import gold, is_demo, metrics, quest_view, ratio, select_snapshot, source_label


class UiModelsTests(unittest.TestCase):
    def test_real_game_data_preferred_to_demo(self):
        now = time.time()
        demo = {"available": True, "source": "experimental native DLL named pipe",
                "data": {"character": {"name": "Demo"}}}
        actual = {"available": True, "source": "WoW addon visual data strip",
                  "data": {"captured_at": now, "character": {"name": "Player"}}}
        self.assertIs(select_snapshot(demo, actual, now=now), actual)
        self.assertIn("DEMO", source_label(demo))
        self.assertTrue(is_demo(demo))

    def test_stale_real_data_never_live(self):
        now = time.time()
        visual = {"available": True, "source": "WoW addon visual data strip",
                  "data": {"captured_at": now - 1000}}
        selected = select_snapshot({"available": False}, visual, now=now)
        self.assertFalse(selected["available"])

    def test_quest_filter_and_progress(self):
        quests = [
            {"title": "Arcane Crystal", "ready_to_turn_in": True,
             "objectives": [{"text": "Find a crystal", "done": True}]},
            {"title": "Wolves", "ready_to_turn_in": False,
             "objectives": [{"text": "Wolf pelts: 3/10", "done": False}]},
        ]
        self.assertEqual([q["title"] for q in quest_view(quests, mode="Gotowe")],
                         ["Arcane Crystal"])
        self.assertEqual(len(quest_view(quests, "pelts")), 1)
        self.assertEqual(quest_view(quests)[0]["title"], "Arcane Crystal")
        self.assertEqual(metrics({"data": {"quests": quests}})["ready_count"], 1)

    def test_math_and_empty_data(self):
        self.assertEqual(ratio(50, 100), 0.5)
        self.assertEqual(ratio("x", 0), 0)
        self.assertEqual(gold(123456), "12g 34s 56c")
        self.assertEqual(metrics({"data": None})["quest_count"], 0)

    def test_null_and_malformed_fields(self):
        self.assertEqual(quest_view([None, "bad"], query="abc"), [])
        self.assertFalse(select_snapshot(None, None)["available"])
        self.assertIn("Brak", source_label(None))


if __name__ == "__main__":
    unittest.main()
