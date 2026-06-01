import json
import tempfile
import unittest
from pathlib import Path

from bead_matcher.inventory import Inventory
from bead_matcher.storage import load_inventory, save_inventory


class TestStorage(unittest.TestCase):
    def test_save_and_load(self):
        inv = Inventory(brand="Perler")
        inv.add("01", 100)
        inv.add("03", 50)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.db"
            save_inventory(inv, path)

            loaded = load_inventory(path, brand="Perler")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.brand, "Perler")
            self.assertEqual(loaded.get_quantity("01"), 100)
            self.assertEqual(loaded.get_quantity("03"), 50)

    def test_load_nonexistent_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.db"
            result = load_inventory(path, brand="Mard")
            self.assertIsNone(result)

    def test_json_format(self):
        inv = Inventory(brand="Perler")
        inv.add("01", 100)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.db"
            save_inventory(inv, path)

            loaded = load_inventory(path, brand="Perler")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.brand, "Perler")
            self.assertEqual(loaded.get_quantity("01"), 100)


if __name__ == "__main__":
    unittest.main()
