import unittest

import createJLPTDeck

class TestTransform(unittest.TestCase):
	def test_furigana_7_days(self):
		self.assertEqual(createJLPTDeck.make_furigana("７日", "なのか"),"７日[なのか]")