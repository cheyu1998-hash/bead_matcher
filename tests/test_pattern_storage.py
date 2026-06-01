import tempfile
import unittest
from pathlib import Path

from bead_matcher.pattern import Pattern
from bead_matcher.pattern_storage import PatternLibrary


class TestPatternLibrary(unittest.TestCase):
    def test_add_and_get(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lib = PatternLibrary(Path(tmpdir) / "test.db")
            p = Pattern(name="小熊", brand="Mard", width=3, height=3)
            p.set_cell(0, 0, "A01")

            lib.add(p)
            self.assertEqual(len(lib), 1)

            fetched = lib.get("小熊")
            self.assertIsNotNone(fetched)
            self.assertEqual(fetched.name, "小熊")
            self.assertEqual(fetched.color_usage, {"A01": 1})

    def test_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.db"
            lib = PatternLibrary(path)
            p = Pattern(name="小猫", brand="Perler", width=2, height=2)
            p.set_cell(0, 0, "01")
            lib.add(p)

            # 重新加载
            lib2 = PatternLibrary(path)
            self.assertEqual(len(lib2), 1)
            self.assertIsNotNone(lib2.get("小猫"))
            self.assertEqual(lib2.get("小猫").brand, "Perler")

    def test_remove(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lib = PatternLibrary(Path(tmpdir) / "test.db")
            lib.add(Pattern(name="A", brand="Mard", width=1, height=1))

            self.assertTrue(lib.remove("A"))
            self.assertEqual(len(lib), 0)
            self.assertFalse(lib.remove("A"))

    def test_list_names(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lib = PatternLibrary(Path(tmpdir) / "test.db")
            lib.add(Pattern(name="B", brand="Mard", width=1, height=1))
            lib.add(Pattern(name="A", brand="Mard", width=1, height=1))

            self.assertEqual(lib.list_names(), ["A", "B"])

    def test_list_by_brand(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lib = PatternLibrary(Path(tmpdir) / "test.db")
            lib.add(Pattern(name="A", brand="Mard", width=1, height=1))
            lib.add(Pattern(name="B", brand="Perler", width=1, height=1))

            self.assertEqual(len(lib.list_by_brand("Mard")), 1)
            self.assertEqual(lib.list_by_brand("Mard")[0].name, "A")

    def test_find_matching_patterns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lib = PatternLibrary(Path(tmpdir) / "test.db")

            p1 = Pattern(name="小熊", brand="Mard", width=2, height=2)
            p1.set_cell(0, 0, "A01")
            p1.set_cell(1, 0, "A01")

            p2 = Pattern(name="大熊", brand="Mard", width=2, height=2)
            p2.set_cell(0, 0, "A01")
            p2.set_cell(1, 0, "A01")
            p2.set_cell(0, 1, "B02")

            lib.add(p1)
            lib.add(p2)

            # 库存只够小熊
            matches = lib.find_matching_patterns({"A01": 2})
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0].name, "小熊")

            # 库存够两个
            matches = lib.find_matching_patterns({"A01": 10, "B02": 10})
            self.assertEqual(len(matches), 2)

    def test_find_partially_matching_patterns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lib = PatternLibrary(Path(tmpdir) / "test.db")

            p1 = Pattern(name="小熊", brand="Mard", width=2, height=2)
            p1.set_cell(0, 0, "A01")
            p1.set_cell(1, 0, "A01")

            p2 = Pattern(name="大熊", brand="Mard", width=2, height=2)
            p2.set_cell(0, 0, "A01")
            p2.set_cell(1, 0, "A01")
            p2.set_cell(0, 1, "B02")
            p2.set_cell(1, 1, "B02")

            lib.add(p1)
            lib.add(p2)

            results = lib.find_partially_matching_patterns({"A01": 2})
            # 小熊不缺，大熊缺 2 个 B02
            self.assertEqual(results[0][0].name, "小熊")
            self.assertEqual(results[0][1], {})
            self.assertEqual(results[1][0].name, "大熊")
            self.assertEqual(results[1][1], {"B02": 2})


if __name__ == "__main__":
    unittest.main()
