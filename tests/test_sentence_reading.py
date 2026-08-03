"""Match search term to expected sentence output.

Add entries to TEST_CASES to verify sentence furigana rendering.
Each case: (term, expected_example_jp, optional: specific reading of the term (in case of multiple))

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
    ("積もる", "塵[ちり]も<mark>積[つ]もれば</mark> 山[やま]となる。"),
    ("学", "<mark>学[がく]</mark>のある 人[ひと]はとかく 無知[むち]な 人[ひと]を 軽蔑[けいべつ]する。"),
    ("食べる", "僕[ぼく]は 脚本家[きゃくほんか]で<mark>食[た]べて</mark>いく 決心[けっしん]をした。"),
    ("ビル", "あの<mark>ビル</mark>のとなりです。"), #uses the noun rather than proper name "Bill"
    ("郵便局", "あの～<mark>郵便局[ゆうびんきょく]</mark>はどちらでしょうか。"), # matches fully all 3 kanji where 2 kanjis +1 could also make a valid sentence
    ("喧嘩", "ケンと<mark>けんか</mark>したのか。"), # picks up proper nouns like ケン which aren't in the index list
    ("小さな", "その 犬[いぬ]は<mark>小[ちい]さな</mark> 男[おとこ]の 子[こ]に 向[む]かって 唸[うな]った。"), # furigana only displayed over the necessary kanji part, and cuts hiragana parts from the reading
	("金", "<mark>金[かね]</mark>の 切[き]れ 目[め]が 縁[えん]の 切[き]れ 目[め]。", "かね"),
	("金", "日本[にほん]シンクロ 界[かい]の 悲願[ひがん]である<mark>金[きん]</mark>には、 あと 一歩[いっぽ]で 届[とど]かなかった。", "きん"), # handle same expressions with different pronunciations and different meanings
	("年齢","<mark>年齢[ねんれい]</mark>は１８ 歳[さい]です。"), # numbers like １８ (full-width numbers) shouldn't have a furigana reading.
]
# ──────────────────────────────────────────────────────────────────────


def load_matcher():
	"""Load jmdict and build a SentenceMatcher (one-time cost)."""
	jmdict_dict = createJLPTDeck.load_jmdict_json_zip(
		Path("original_data/jmdict-eng-3.6.1.zip")
	)[2]
	return SentenceMatcher(jmdict_dict)


def run_matcher(matcher, terms, reading_kana=None):
	"""Run match_all on a list of terms and return results."""
	df = pd.DataFrame({"expression": terms})
	if reading_kana is not None:
		df["reading_kana"] = reading_kana
	result = matcher.match_all(df)
	return result[["expression", "example_jp", "example_en"]]


class TestSentenceReading(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.matcher = load_matcher()

	def test_sentence_readings(self):
		for case in TEST_CASES:
			term, expected = case[0], case[1]
			reading_kana = case[2] if len(case) > 2 else None
			with self.subTest(term=term):
				result = run_matcher(self.matcher, [term], reading_kana)
				actual = result["example_jp"].iloc[0]
				self.assertEqual(actual, expected,
				                 f"For term {term!r}: expected {expected!r}, got {actual!r}")

