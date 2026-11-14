import importlib.util
import unittest
from pathlib import Path


@unittest.skipUnless(importlib.util.find_spec("streamlit"), "CI installs Streamlit for the UI smoke test")
class StreamlitUiSmokeTests(unittest.TestCase):
    def test_app_opens_and_exposes_the_video_upload(self):
        from streamlit.testing.v1 import AppTest

        app = Path(__file__).resolve().parents[1] / "app.py"
        result = AppTest.from_file(str(app), default_timeout=60).run()
        self.assertFalse(result.exception)
        self.assertTrue(any(title.value == "Local Clipper" for title in result.title))
        upload_labels = {uploader.label for uploader in result.file_uploader}
        self.assertEqual(
            upload_labels,
            {
                "Upload a video you own or are authorized to process",
                "Optional reference transcript for WER measurement",
            },
        )


if __name__ == "__main__":
    unittest.main()

