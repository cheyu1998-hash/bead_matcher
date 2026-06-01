import tempfile
import unittest
from pathlib import Path

from PIL import Image

from bead_matcher.pattern_converter import convert_image_to_pattern, suggest_grid_size


class TestConvertImageToPattern(unittest.TestCase):
    def test_simple_conversion(self):
        """用纯色图测试转换逻辑"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建 4x4 近白色图片（匹配 Mard H02 #FEFFFF）
            img = Image.new("RGB", (4, 4), color=(254, 255, 255))
            path = Path(tmpdir) / "white.png"
            img.save(path)

            pattern = convert_image_to_pattern(
                image_path=path,
                brand="Mard",
                target_width=4,
                target_height=4,
                name="纯白",
            )

            self.assertEqual(pattern.name, "纯白")
            self.assertEqual(pattern.brand, "Mard")
            self.assertEqual(pattern.width, 4)
            self.assertEqual(pattern.height, 4)
            self.assertEqual(pattern.input_mode, "pixel_convert")
            # 白色最接近 Mard H02 (Grey 02 #FEFFFF)
            self.assertEqual(pattern.grid[(0, 0)], "H02")
            self.assertEqual(pattern.color_usage.get("H02"), 16)
            self.assertEqual(pattern.total_beads(), 16)

    def test_two_color_image(self):
        """测试双色图片转换"""
        with tempfile.TemporaryDirectory() as tmpdir:
            img = Image.new("RGB", (4, 4))
            # 左半边红色（匹配 Mard F02 #FC3D46），右半边蓝色（匹配 Mard C05 #01ACEB）
            for y in range(4):
                for x in range(2):
                    img.putpixel((x, y), (252, 61, 70))
                for x in range(2, 4):
                    img.putpixel((x, y), (1, 172, 235))
            path = Path(tmpdir) / "rb.png"
            img.save(path)

            pattern = convert_image_to_pattern(
                image_path=path,
                brand="Mard",
                target_width=4,
                target_height=4,
                name="红蓝",
            )

            self.assertEqual(pattern.color_usage.get("F02"), 8)  # Red
            self.assertEqual(pattern.color_usage.get("C05"), 8)  # Blue
            self.assertEqual(pattern.total_beads(), 16)

    def test_unknown_brand_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            img = Image.new("RGB", (2, 2))
            path = Path(tmpdir) / "x.png"
            img.save(path)

            with self.assertRaises(ValueError):
                convert_image_to_pattern(path, "Unknown", 2, 2, "x")


class TestSuggestGridSize(unittest.TestCase):
    def test_suggestion(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # 480x320 的图片，期望建议约 48x32
            img = Image.new("RGB", (480, 320))
            path = Path(tmpdir) / "suggest.png"
            img.save(path)

            w, h = suggest_grid_size(path)
            self.assertGreater(w, 0)
            self.assertGreater(h, 0)
            # 长边应该在常见候选值附近
            self.assertIn(max(w, h), [32, 48, 64, 80, 96, 128])


if __name__ == "__main__":
    unittest.main()
