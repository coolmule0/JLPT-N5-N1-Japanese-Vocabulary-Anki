"""Match Tatoeba sentences to vocabulary words and select the best example sentence per word."""

import logging
import re
from pathlib import Path
from dataclasses import dataclass

import pandas as pd

from utils import make_furigana, make_furigana_surface

SENTENCE_PAIRS_PATH = Path("original_data", "sentence_tatoeba", "jp-eng-sentence-pairs.tsv")
# SENTENCE_AUDIO_PATH = Path("original_data", "sentence_tatoeba", "sentences_with_audio.csv")
INDICES_PATH = Path("original_data", "sentence_tatoeba", "jpn_indices.csv")

MIN_SENTENCE_CHARS = 0  # Minimum Japanese characters to have meaningful context
MAX_SENTENCE_CHARS = 200  # Total number of characters in the sentence. Want to avoid too long sentences that meander and lack the actual work to study

# KANA_RE = re.compile(r'^[\u3040-\u30FF]+$')
NUMBERS_RE = re.compile(r'^[\uFF10-\uFF19]+$')

@dataclass
class IndexToken:
	headword: str
	reading: str
	sense: int
	actual_form_in_sentence: str
	suitable: bool

@dataclass
class IndexSentence:
	sentence_id: int
	meaning_id: int
	tokens: list[IndexToken]

	"""Get the word token for a sentence"""
	def get_token(self, headword: str) -> IndexToken:
		for it in self.tokens:
			if it.headword == headword:
				return it
	@property
	def length(self) -> int:
		return sum(len(t.headword) for t in self.tokens)

# The regex style for an entry in the jpn_indices.csv file
# See https://www.edrdg.org/wiki/Sentence-Dictionary_Linking.html#Index_Format for specification
# Token pattern: headword, optional (reading), optional [sense], optional {surface}, optional ~, optional |digit
_TOKEN_RE = re.compile(
	r'^(?P<headword>[^(\[\]{~|]+)'
	r'(?:\((?P<reading>[^)]*)\))?'
	r'(?:\[(?P<sense>\d+)\])?'
	r'(?:\{(?P<surface>[^}]*)\})?'
	r'(?P<suitable>~)?'
	r'(?:\|\d+)?'
	r'$'
)

def _load_sentence_pairs() -> pd.DataFrame:
	"""Load the Tatoeba JP-EN sentence pairs TSV."""
	df = pd.read_csv(
		SENTENCE_PAIRS_PATH,
		sep="\t",
		header=None,
		names=["sentence_id", "jp_sentence", "meaning_id", "en_meaning"],
	)
	# Deduplicate Japanese sentences, keeping first occurrence
	df = df.drop_duplicates(subset="jp_sentence", keep="first")
	return df

# def _load_sentence_audio() -> pd.DataFrame:
# 	"""Load sentences_with_audio.csv, keep only rows with a license."""
# 	df = pd.read_csv(
# 		SENTENCE_AUDIO_PATH,
# 		sep="\t",
# 		header=None,
# 		names=["sentence_id", "audio_id", "username", "license", "username_url"],
# 	)
# 	df = df.dropna(subset=["license"])
# 	df = df.drop_duplicates(subset="sentence_id", keep="first")
# 	return df

def _load_sentence_indices() -> pd.DataFrame:
	df = pd.read_csv(
		INDICES_PATH,
		sep="\t",
		header=None,
		names=["sentence_id", "meaning_id", "sentence_text"],
	)
	return df



def parse_index_line(line: str) -> list[IndexToken]:
	"""Given a sentence, get the jmdict entries within."""
	tokens: list[IndexToken] = []
	for raw in line.split():
		m = _TOKEN_RE.match(raw)
		if not m:
			continue
		tokens.append(IndexToken(
			headword=m.group("headword"),
			reading=m.group("reading") or "",
			sense=int(m.group("sense")) if m.group("sense") else -1,
			actual_form_in_sentence=m.group("surface") or "",
			suitable=m.group("suitable") == "~",
		))
	return tokens

class SentenceMatcher:
	"""Matches Tatoeba sentences to vocab words and picks the best one."""

	def __init__(self, jmdict_data: dict) -> None:
		logging.info("Loading Tatoeba sentence data...")
		self.pairs = _load_sentence_pairs()
		self.pairs = self.pairs.set_index("sentence_id")
		# self.audio = _load_sentence_audio()
		self.indices = _load_sentence_indices()
		self.jmdict_data = jmdict_data

		# self.audio_ids = set(self.audio["sentence_id"].unique())

		logging.debug("Building JMDict reading index...")
		self._reading_index = self._build_reading_index()
		self._id_index = self._build_id_index()

		logging.debug("Building sentences data index...")
		self._index = self._build_index()
		self._word_index = self._build_word_index()

	def query_index(self, search_word: str, suitable_only: bool = False) -> list[IndexSentence]:
		"""Return all sentences that contain the given search word.

		Parameters
		----------
		search_word : str
			word to search on. Return all sentences that include this word
		suitable_only : bool, optional
			choose only those marked suitable as a sentence (by the jmdict definition this should be at most 1 entry, though not enforces), by default False

		Returns
		-------
		list[IndexSentence]
			All the sentence that contain this word
		"""
		results = self._word_index.get(search_word, [])
		if suitable_only:
			results = [s for s in results if s.get_token(search_word).suitable]
		return results
	
	def get_best_sentence(self, headword: str, hiragana_reading: str = "") -> IndexSentence | None:
		"""Find the best sentence for the headword out of all available sentences that match

		Parameters
		----------
		headword : str
			the sentences to filter on. Must contain this term as the main word of any given token
		hiragana_reading : str, optional
			Useful if the word has multiple readings. Will not match sentences with differing readings to provided, by default ""

		Returns
		-------
		IndexSentence | None
			The best sentence for this search filter
		"""
		sentences = self.query_index(headword)
		
		# filter out those with wrong reading
		if hiragana_reading:
			sentences = [
				s for s in sentences 
				if s.get_token(headword).reading == hiragana_reading
					or s.get_token(headword).reading == ""
			]

		# no sentence found
		if len(sentences) < 1:
			return None

		best_sentence = sentences[0]
		for s in sentences[1:]:
			if self.is_better(headword, best_sentence, s):
				best_sentence = s
		return best_sentence
		
	@staticmethod
	def is_better(word: str, curr_best: IndexSentence, new: IndexSentence) -> bool:
		"""true if the new sentence is a better fit """
		curr_best_token = curr_best.get_token(word)
		new_best_token = new.get_token(word)
		# choose the first suitable-flagged sentence
		if curr_best_token.suitable:
			return False
		if new_best_token.suitable:
			return True
		# choose the entry that has the sense/meaning closest to the main definition
		new_sense = max(new_best_token.sense, 1)
		cur_sense = max(curr_best_token.sense, 1)
		if new_sense < cur_sense:
			return True
		# Otherwise shortest sentence
		return new.length < curr_best.length

	def _build_reading_index(self) -> dict[str, str]:
		"""Build a kanji/kana text -> primary reading dict from jmdict."""
		idx: dict[str, str] = {}
		for w in self.jmdict_data["words"]:
			reading = w["kana"][0]["text"] if w["kana"] else None
			for k in w["kanji"]:
				text = k["text"]
				if text not in idx:
					idx[text] = reading
			if not w["kanji"]:
				for k in w["kana"]:
					text = k["text"]
					if text not in idx:
						idx[text] = reading
		return idx

	def _build_id_index(self) -> dict[str, str]:
		"""Build an id -> primary reading dict from jmdict."""
		idx: dict[str, str] = {}
		for w in self.jmdict_data["words"]:
			if w["kana"]:
				idx[w["id"]] = w["kana"][0]["text"]
		return idx

	def _build_index(self) -> list[IndexSentence]:
		"""_summary_

		Returns
		-------
		list[IndexSentence]
			all the sentences decomposed into word tokens
		"""
		sentenceIndeces = []
		sentences = self.indices.itertuples(index=False)
		for row in sentences:
			# Some sentence might not have an english meaning - skip them
			if row.meaning_id <= 0:
				continue
			jp = row.sentence_text
			
			# Limit sentence by size
			length = len(jp)
			if length < MIN_SENTENCE_CHARS or length > MAX_SENTENCE_CHARS:
				continue

			# has_audio = row.sentence_id in self.audio_ids
			
			tokens = parse_index_line(jp)
			i_s = IndexSentence(row.sentence_id, row.meaning_id, tokens)
			sentenceIndeces.append(i_s)
		return sentenceIndeces

	def _build_word_index(self) -> dict[str, list[IndexSentence]]:
		pairs_ids = set(self.pairs.index)
		word_index: dict[str, list[IndexSentence]] = {}
		for sentence in self._index:
			if sentence.sentence_id not in pairs_ids:
				continue
			seen: set[str] = set()
			for token in sentence.tokens:
				if token.headword not in seen:
					word_index.setdefault(token.headword, []).append(sentence)
					seen.add(token.headword)
		return word_index

	def match_all(self, df: pd.DataFrame) -> pd.DataFrame:
		results = []
		not_matches = 0
		total = len(df)
		for i, row in df.iterrows():
			if i % 500 == 0:
				logging.debug(f"Matching sentences: {i}/{total}")
			term = row["expression"]
			# Add a little extra logic for the reading_kana part in case (like in tests) there isn't a reading column. Usually expect a reading column for proper pipeline
			best = self.get_best_sentence(term, row["reading_kana"] if "reading_kana" in df.columns else "")
			if best is None:
				results.append({"jp": "", "en": ""})
				not_matches += 1
				continue
			pair = self.pairs.loc[best.sentence_id]
			best = self.fill_missing_terms(best, pair["jp_sentence"])
			jp_reading = self.make_sentence_reading(best, term)
			results.append({
				"jp": jp_reading,
				"en": pair["en_meaning"],
			})

		logging.debug(f"Not matched sentences: {not_matches}/{total} entries")
		rdf = df.copy()
		rdf["example_jp"] = [r.get("jp", "") for r in results]
		rdf["example_en"] = [r.get("en", "") for r in results]

		return rdf

	def make_sentence_reading(self, sentence: IndexSentence, markup: str = "") -> str:
		""" Take sentence tokens and make a furigana reading sentence of it.
		
		Provides furigana for conjugated forms by mapping the headword reading
		onto the surface form's kanji groups.

		Parameters
		----------
		sentence : IndexSentence
			The sentence and tokens of the word within for creating the sentence
		markup : str, optional
			If one of the words/terms should be wrapped in <mark> tags to make them more visible in html rendering, by default ""

		Returns
		-------
		str
			_description_
		"""
		resulting_sentence = []
		markup_idx = -1 # which word element to mark up
		for i, token in enumerate(sentence.tokens):
			if token.headword == markup:
				markup_idx = i
			if token.actual_form_in_sentence:
				reading = token.reading
				if reading and "#" in reading:
					reading = self.lookup_reading(int(reading.lstrip("#")))
				elif re.match(NUMBERS_RE, token.actual_form_in_sentence): # only full-width numbers - no need for furigana
					resulting_sentence.append(token.actual_form_in_sentence)
					continue
				elif not reading:
					reading = self.lookup_reading(token.headword)
				resulting_sentence.append(make_furigana_surface(token.actual_form_in_sentence, token.headword, reading))
			elif token.reading:
				if "#" in token.reading:
					token.reading = self.lookup_reading(int(token.reading.lstrip("#")))

				resulting_sentence.append(make_furigana(token.headword, token.reading))
			else:
				# default reading from the jmdict. There should only be 1 result for the headword (otherwise the #nnnn format should have been used in the data)
				reading = self.lookup_reading(token.headword)
				resulting_sentence.append(make_furigana(token.headword, reading))
		
		if markup and markup_idx == -1:
			logging.debug("Error finding term {markup} to highlight")

		result = ""
		for i, sent_elem in enumerate(resulting_sentence):
			if i == markup_idx:
				# add mark to this element
				result += f"<mark>{sent_elem}</mark>"
			elif "[" in sent_elem:
				result += " " + sent_elem
			else:
				result += sent_elem
		return result.lstrip()

	def lookup_reading(self, query: str | int) -> str:
		"""Look up the reading of a word by ID or headword.
		
		Parameters
		----------
		query : str | int
			Either a JMDict ID (int or numeric string) or a headword (kanji/kana).
		
		Returns
		-------
		str
			The kana reading, or the query itself if not found.
		"""
		if isinstance(query, int) or (isinstance(query, str) and query.isdigit()):
			return self._id_index.get(str(query), str(query))
		return self._reading_index.get(query, str(query))

	def fill_missing_terms(self, indx_sent: IndexSentence, pairs_sent: str) -> IndexSentence:
		"""Tries to find missing characters in the index sentence and add them as tokens."""
		new_tokens = []
		pos = 0

		for token in indx_sent.tokens:
			surface = token.actual_form_in_sentence or token.headword
			start = pairs_sent.find(surface, pos)

			if start == -1:
				# Can't find surface form; skip token
				continue

			if start > pos:
				# Gap of missing characters before this token
				gap = pairs_sent[pos:start]
				new_tokens.append(IndexToken(
					headword=gap,
					reading="",
					sense=-1,
					actual_form_in_sentence=gap,
					suitable=False,
				))

			new_tokens.append(token)
			pos = start + len(surface)

		# Trailing gap after all tokens
		if pos < len(pairs_sent):
			gap = pairs_sent[pos:]
			new_tokens.append(IndexToken(
				headword=gap,
				reading="",
				sense=-1,
				actual_form_in_sentence=gap,
				suitable=False,
			))

		return IndexSentence(indx_sent.sentence_id, indx_sent.meaning_id, new_tokens)