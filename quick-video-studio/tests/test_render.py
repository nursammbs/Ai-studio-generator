import unittest

from render import srt_time, wrap_text
from PIL import Image, ImageDraw, ImageFont


class RenderHelpersTest(unittest.TestCase):
    def test_srt_time_formats_milliseconds(self):
        self.assertEqual(srt_time(65.432), "00:01:05,432")

    def test_wrap_text_keeps_words_and_respects_width(self):
        image = Image.new("RGB", (400, 100))
        draw = ImageDraw.Draw(image)
        face = ImageFont.load_default()
        lines = wrap_text(draw, "one two three four five", face, 55)
        self.assertGreater(len(lines), 1)
        self.assertEqual(" ".join(lines).split(), ["one", "two", "three", "four", "five"])


if __name__ == "__main__":
    unittest.main()
