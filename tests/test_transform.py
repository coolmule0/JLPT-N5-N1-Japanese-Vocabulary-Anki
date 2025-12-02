import unittest
from pathlib import Path
import json

import pandas as pd

import createJLPTDeck

class TestTransform(unittest.TestCase):
	def test_furigana_7_days(self):
		self.assertEqual(createJLPTDeck.make_furigana("７日", "なのか"),"７日[なのか]", "Full-width numbers in the kanji field still provide correct furigana reading")
	
	def test_usually_kana_reading(self):
		columns = ['jmdict_seq', 'kana', 'kanji', 'waller_definition', 'jlpt_level',
					'reading_kanji', 'reading_kana', 'english_definition', 'grammar',
					'additional', 'misc']

		first_row = [1219960, 'いくつ', '', 'how many?,how old?', 'N5', '幾つ', 'いくつ',
					['how many'], ['adv'], [['how old']], ['uk']]

		df = pd.DataFrame([first_row], columns=columns)

		jmdict, jmdict_tags_mapping = createJLPTDeck.load_jmdict_json_zip(Path(f"original_data/jmdict-eng-3.6.1.zip"))

		df_post = createJLPTDeck.prepare_word_record(df, jmdict_tags_mapping)
		word_post = df_post.iloc[0]
		self.assertEqual(word_post["reading"], "いくつ", "Usually kana tag (uk) creates a reading that is only hiragana")
	

class TestTransformResults(unittest.TestCase):
	def setUp(self):
		"""
		The pipeline up to the transform step
		"""
		self.df, self.jmdict, self.jmdict_tags_mapping, self.wani_audio = createJLPTDeck.extract()
		self.df = createJLPTDeck.clean(self.df)

	def test_two_same_readings(self):
		"""
		A word that has no kanji (such as ああ), and a word with kanji but usually written in the same hiragana (嗚呼/ああ) should be registed as repeats.
		In particular, should only save the one with the easier JLPT.
		"""
		# Use only the entries of interest	
		json_str = """
		[
			{"id":"1565440","kanji":[{"common":false,"text":"嗚呼","tags":["sK"]}],"kana":[{"common":true,"text":"ああ","tags":[],"appliesToKanji":["*"]}],"sense":[{"partOfSpeech":["int"],"appliesToKanji":["*"],"appliesToKana":["*"],"related":[],"antonym":[],"field":[],"dialect":[],"misc":["uk"],"info":["occ. written as 嗚呼, 噫 or 嗟"],"languageSource":[],"gloss":[{"lang":"eng","gender":null,"type":null,"text":"ah!"},{"lang":"eng","gender":null,"type":null,"text":"oh!"},{"lang":"eng","gender":null,"type":null,"text":"alas!"}]}]},

			{"id":"2085080","kanji":[],"kana":[{"common":true,"text":"ああ","tags":[],"appliesToKanji":["*"]}],"sense":[{"partOfSpeech":["adv"],"appliesToKanji":["*"],"appliesToKana":["*"],"related":[["こう",1],["そう",1],["どう"]],"antonym":[],"field":[],"dialect":[],"misc":[],"info":["used for something or someone distant from both speaker and listener"],"languageSource":[],"gloss":[{"lang":"eng","gender":null,"type":null,"text":"like that"},{"lang":"eng","gender":null,"type":null,"text":"so"}]}]}
		]
		"""
		self.jmdict = pd.DataFrame(json.loads(json_str))
		self.jmdict["id"] = self.jmdict["id"].astype(int)
		word_ids = [x for x in self.jmdict["id"]]
		self.df = self.df[self.df["jmdict_seq"].isin(word_ids)].reset_index(drop=True)

		self.assertEqual(self.df.shape[0], 2, "Two words before transformation")
		post_transf = createJLPTDeck.transform(self.df, self.jmdict, self.jmdict_tags_mapping, self.wani_audio)

		print()
		self.assertEqual(post_transf.shape[0], 1, "1 row dropped due to transformation")
		self.assertNotIn("嗚呼", post_transf["expression"], "more complicated form not in list")
		self.assertIn("ああ", post_transf["reading"].iloc[0], "easier JLPT version complicated form remains")
