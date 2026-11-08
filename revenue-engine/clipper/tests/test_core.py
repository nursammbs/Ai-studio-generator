import tempfile, unittest
from pathlib import Path
from core import Word, _srt_time, suggest_candidates, write_srt

class ClipperCoreTests(unittest.TestCase):
    def test_srt_time(self):
        self.assertEqual(_srt_time(61.234),"00:01:01,234")
    def test_candidates_are_bounded(self):
        words=[]; cursor=0.0
        for sentence in ["Why does this matter?","Because the result changes everything.","Here is the practical lesson."]:
            for token in sentence.split():
                words.append(Word(token,cursor,cursor+2.0)); cursor+=2.0
        result=suggest_candidates(words,min_duration=5,max_duration=20,max_candidates=5)
        self.assertTrue(result)
        for item in result:
            self.assertGreaterEqual(item.end-item.start,5)
            self.assertLessEqual(item.end-item.start,20)
    def test_srt_relative_to_clip(self):
        words=[Word("Hello",10,10.5),Word("world.",10.5,11)]
        with tempfile.TemporaryDirectory() as folder:
            target=write_srt(words,10,11,Path(folder)/"clip.srt")
            content=target.read_text(encoding="utf-8")
            self.assertIn("00:00:00,000 --> 00:00:00,500",content)
            self.assertIn("Hello",content)

if __name__=="__main__": unittest.main()
