import unittest

from bead_matcher.inventory import Inventory, InventoryItem


class TestInventoryItem(unittest.TestCase):
    def test_valid_creation(self):
        item = InventoryItem("01", 100)
        self.assertEqual(item.code, "01")
        self.assertEqual(item.quantity, 100)

    def test_negative_quantity_raises(self):
        with self.assertRaises(ValueError):
            InventoryItem("01", -1)


class TestInventory(unittest.TestCase):
    def setUp(self):
        self.inv = Inventory(brand="Mard")

    def test_add_new_color(self):
        self.inv.add("01", 100)
        self.assertEqual(self.inv.get_quantity("01"), 100)

    def test_add_existing_color(self):
        self.inv.add("01", 50)
        self.inv.add("01", 30)
        self.assertEqual(self.inv.get_quantity("01"), 80)

    def test_add_non_positive_raises(self):
        with self.assertRaises(ValueError):
            self.inv.add("01", 0)
        with self.assertRaises(ValueError):
            self.inv.add("01", -5)

    def test_remove_success(self):
        self.inv.add("01", 100)
        self.inv.remove("01", 30)
        self.assertEqual(self.inv.get_quantity("01"), 70)

    def test_remove_to_zero_deletes(self):
        self.inv.add("01", 50)
        self.inv.remove("01", 50)
        self.assertIsNone(self.inv.get("01"))

    def test_remove_insufficient_raises(self):
        self.inv.add("01", 10)
        with self.assertRaises(ValueError):
            self.inv.remove("01", 20)

    def test_remove_nonexistent_raises(self):
        with self.assertRaises(KeyError):
            self.inv.remove("99", 10)

    def test_set_quantity(self):
        self.inv.set("01", 200)
        self.assertEqual(self.inv.get_quantity("01"), 200)

    def test_set_to_zero_removes(self):
        self.inv.add("01", 100)
        self.inv.set("01", 0)
        self.assertIsNone(self.inv.get("01"))

    def test_total_count(self):
        self.inv.add("01", 100)
        self.inv.add("02", 50)
        self.assertEqual(self.inv.total_count(), 150)

    def test_to_dict_roundtrip(self):
        self.inv.add("A01", 100)
        self.inv.add("B01", 50)
        data = self.inv.to_dict()
        restored = Inventory.from_dict(data)
        self.assertEqual(restored.brand, "Mard")
        self.assertEqual(restored.get_quantity("A01"), 100)
        self.assertEqual(restored.get_quantity("B01"), 50)

    def test_validate_against_chart(self):
        self.inv.add("A01", 10)
        self.inv.add("Z99", 10)  # 不在 Mard 221 色中
        invalid = self.inv.validate_against_chart()
        self.assertIn("Z99", invalid)
        self.assertNotIn("A01", invalid)


if __name__ == "__main__":
    unittest.main()
