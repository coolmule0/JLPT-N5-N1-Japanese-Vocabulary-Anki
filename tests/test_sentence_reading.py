"""Data-driven tests for make_sentence_reading output.

Add entries to TEST_CASES to verify sentence furigana rendering.
Each case: (term, expected_example_jp)

Run:
    pytest tests/test_sentence_reading.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest

import logging
logging.basicConfig(level=logging.DEBUG, format="%(name)s: %(message)s")

import pandas as pd

import createJLPTDeck
from sources.sentences.sentence_matcher import SentenceMatcher


# ── Edit these terms to test ──────────────────────────────────────────
TEST_CASES = [
	("越す", "また<mark>お 越[こ]し</mark>ください。"),
]
# ──────────────────────────────────────────────────────────────────────


def load_matcher():
	"""Load jmdict and build a SentenceMatcher (one-time cost)."""
	jmdict_dict = createJLPTDeck.load_jmdict_json_zip(
		Path("original_data/jmdict-eng-3.6.1.zip")
	)[2]
	return SentenceMatcher(jmdict_dict)


def run_matcher(matcher, terms):
	"""Run match_all on a list of terms and return results."""
	df = pd.DataFrame({"expression": terms})
	result = matcher.match_all(df)
	return result[["expression", "example_jp", "example_en"]]


class TestSentenceReading(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.matcher = load_matcher()

	def test_sentence_readings(self):
		for term, expected in TEST_CASES:
			with self.subTest(term=term):
				result = run_matcher(self.matcher, [term])
				actual = result["example_jp"].iloc[0]
				self.assertEqual(actual, expected,
				                 f"For term {term!r}: expected {expected!r}, got {actual!r}")


if __name__ == "__main__":
	unittest.main()
