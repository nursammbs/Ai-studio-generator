import tempfile
import unittest
from pathlib import Path

from core import (
    Word,
    _srt_time,
    load_transcript,
    save_transcript,
    suggest_candidates,
    write_srt,
)


class ClipperCoreTests(unittest.TestCase):
    def test_srt_time(self):
        self.assertEqual(_srt_time(61.234), "00:01:01,234")

    def test_candidates_stay_on_complete_sentence_boundaries(self):
        words = []
        cursor = 0.0
        for sentence in [
            "Why does this matter?",
            "Because the result changes everything.",
            "Here is the practical lesson.",
            "And this unfinished thought",
        ]:
            for token in sentence.split():
                words.append(Word(token, cursor, cursor + 0.5))
                cursor += 0.5
        result = suggest_candidates(words, min_duration=5, max_duration=20, max_candidates=5)
        self.assertTrue(result)
        for item in result:
            self.assertGreaterEqual(item.end - item.start, 5)
            self.assertLessEqual(item.end - item.start, 20)
            self.assertRegex(item.text, r'[.!?]["\')\]]?$')
            self.assertNotIn("unfinished", item.text)

    def test_incomplete_leading_continuation_is_not_suggested(self):
        words = []
        cursor = 0.0
        for sentence in ["And the next thing matters.", "This is the complete explanation.", "It has a clear ending."]:
            for token in sentence.split():
                words.append(Word(token, cursor, cursor + 0.75))
                cursor += 0.75
        result = suggest_candidates(words, min_duration=5, max_duration=20, max_candidates=10)
        self.assertTrue(result)
        self.assertTrue(all(not item.text.startswith("And ") for item in result))

    def test_candidate_limit_zero_returns_no_results(self):
        self.assertEqual(suggest_candidates([], min_duration=1, max_duration=2, max_candidates=0), [])

    def test_unsorted_transcript_is_rejected(self):
        words = [Word("first", 2, 3), Word("second.", 1, 2)]
        with self.assertRaisesRegex(ValueError, "ordered"):
            suggest_candidates(words, min_duration=1, max_duration=4)

    def test_srt_groups_words_into_readable_phrases(self):
        words = [
            Word("I", 0.0, 0.2),
            Word("really", 0.2, 0.4),
            Word("learned", 0.4, 0.7),
            Word("something", 0.7, 1.0),
            Word("important", 1.0, 1.3),
            Word("today.", 1.3, 1.6),
        ]
        with tempfile.TemporaryDirectory() as folder:
            target = write_srt(words, 0, 2, Path(folder) / "clip.srt")
            content = target.read_text(encoding="utf-8")
        self.assertIn("00:00:00,000 --> 00:00:01,600", content)
        self.assertIn("I really learned something\nimportant today.", content)
        self.assertEqual(content.count("-->"), 1)

    def test_srt_clips_word_timing_at_clip_boundaries(self):
        words = [Word("Before", 0, 0.5), Word("inside", 0.5, 1.0), Word("After", 1.0, 1.5)]
        with tempfile.TemporaryDirectory() as folder:
            target = write_srt(words, 0.25, 1.25, Path(folder) / "clip.srt")
            content = target.read_text(encoding="utf-8")
        self.assertIn("00:00:00,000 --> 00:00:01,000", content)
        self.assertIn("Before inside After", content)

    def test_transcript_round_trip(self):
        words = [Word("Hello", 0.0, 0.4), Word("world.", 0.4, 0.8)]
        with tempfile.TemporaryDirectory() as folder:
            path = save_transcript(words, Path(folder) / "transcript.json")
            self.assertEqual(load_transcript(path), words)


if __name__ == "__main__":
    unittest.main()

