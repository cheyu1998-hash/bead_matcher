import unittest

from bead_matcher.pattern import Pattern


class TestPattern(unittest.TestCase):
    def test_creation(self):
        p = Pattern(name="小熊", brand="Mard", width=10, height=10)
        self.assertEqual(p.name, "小熊")
        self.assertEqual(p.brand, "Mard")
        self.assertEqual(p.width, 10)
        self.assertEqual(p.height, 10)
        self.assertEqual(p.total_beads(), 0)
        self.assertEqual(p.unique_colors(), [])

    def test_invalid_size_with_grid(self):
        # 有 grid 时宽高必须 > 0
        with self.assertRaises(ValueError):
            Pattern(name="x", brand="Mard", width=0, height=10, grid={(0, 0): "A01"})
        with self.assertRaises(ValueError):
            Pattern(name="x", brand="Mard", width=10, height=-1, grid={(0, 0): "A01"})

    def test_manual_entry_zero_size_ok(self):
        # manual_entry 无 grid 时允许宽高为 0
        p = Pattern(
            name="manual", brand="Mard", width=0, height=0,
            color_usage={"A01": 100}, input_mode="manual_entry"
        )
        self.assertEqual(p.total_beads(), 100)

    def test_set_cell_and_usage(self):
        p = Pattern(name="test", brand="Mard", width=3, height=3)
        p.set_cell(0, 0, "A01")
        p.set_cell(1, 0, "A01")
        p.set_cell(2, 0, "B02")

        self.assertEqual(p.get_cell(0, 0), "A01")
        self.assertEqual(p.get_cell(1, 0), "A01")
        self.assertEqual(p.get_cell(2, 0), "B02")
        self.assertEqual(p.color_usage, {"A01": 2, "B02": 1})
        self.assertEqual(p.total_beads(), 3)

    def test_set_cell_out_of_range(self):
        p = Pattern(name="test", brand="Mard", width=2, height=2)
        with self.assertRaises(ValueError):
            p.set_cell(2, 0, "A01")
        with self.assertRaises(ValueError):
            p.set_cell(0, 2, "A01")

    def test_set_cell_override(self):
        p = Pattern(name="test", brand="Mard", width=2, height=2)
        p.set_cell(0, 0, "A01")
        p.set_cell(0, 0, "B02")
        self.assertEqual(p.color_usage.get("A01"), None)
        self.assertEqual(p.color_usage.get("B02"), 1)

    def test_can_make_with_inventory(self):
        p = Pattern(name="test", brand="Mard", width=2, height=2)
        p.set_cell(0, 0, "A01")
        p.set_cell(1, 0, "A01")
        p.set_cell(0, 1, "B02")

        self.assertTrue(p.can_make_with_inventory({"A01": 2, "B02": 1}))
        self.assertTrue(p.can_make_with_inventory({"A01": 5, "B02": 10}))
        self.assertFalse(p.can_make_with_inventory({"A01": 1, "B02": 1}))
        self.assertFalse(p.can_make_with_inventory({"A01": 2}))

    def test_estimate_inventory_shortage(self):
        p = Pattern(name="test", brand="Mard", width=2, height=2)
        p.set_cell(0, 0, "A01")
        p.set_cell(1, 0, "A01")
        p.set_cell(0, 1, "B02")

        shortage = p.estimate_inventory_shortage({"A01": 1, "B02": 1})
        self.assertEqual(shortage, {"A01": 1})

        shortage = p.estimate_inventory_shortage({"A01": 2, "B02": 0})
        self.assertEqual(shortage, {"B02": 1})

    def test_to_dict_roundtrip(self):
        p = Pattern(name="小熊", brand="Mard", width=2, height=2, tags=["动物"])
        p.set_cell(0, 0, "A01")
        p.set_cell(1, 0, "B02")

        data = p.to_dict()
        restored = Pattern.from_dict(data)

        self.assertEqual(restored.name, "小熊")
        self.assertEqual(restored.brand, "Mard")
        self.assertEqual(restored.width, 2)
        self.assertEqual(restored.height, 2)
        self.assertEqual(restored.grid, {(0, 0): "A01", (1, 0): "B02"})
        self.assertEqual(restored.color_usage, {"A01": 1, "B02": 1})
        self.assertEqual(restored.tags, ["动物"])

    def test_from_dict_empty_grid(self):
        data = {
            "name": "空图案",
            "brand": "Perler",
            "width": 5,
            "height": 5,
            "grid": {},
            "color_usage": {},
            "tags": [],
        }
        p = Pattern.from_dict(data)
        self.assertEqual(p.total_beads(), 0)


if __name__ == "__main__":
    unittest.main()
