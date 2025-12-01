import unittest
from pathlib import Path

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