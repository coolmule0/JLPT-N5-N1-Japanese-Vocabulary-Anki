"""Match Tatoeba sentences to vocabulary words and select the best example sentence per word."""

import logging
import re
from pathlib import Path

import pandas as pd

from .sentence_selector import TranscriptionThenShortestSelector

SENTENCE_PAIRS_PATH = Path("original_data", "sentence_tatoeba", "jp-eng-sentence-pairs.tsv")
SENTENCE_AUDIO_PATH = Path("original_data", "sentence_tatoeba", "sentences_with_audio.csv")
OVERRIDES_PATH = Path("original_data", "sentence_tatoeba", "sentence_overrides.csv")
TRANSCRIPTION_PATH = Path("original_data", "sentence_tatoeba", "jpn_transcriptions.tsv")

MIN_SENTENCE_CHARS = 8  # Minimum Japanese characters to have meaningful context
MAX_SENTENCE_CHARS = 45  # Total number of characters in the sentence. Want to avoid too long sentences that meander and lack the actual work to study

_KANJI_RE = re.compile(r"[一-鿿㐀-䶿豈-\ufaff]")
_TRANSCRIPT_RE = re.compile(r'\[([^\[\]|]+)\|([^\[\]|]+(?:\|[^\[\]|]+)*)\]')


def _transform_transcription(text: str) -> str:
    """Convert [kanji|r1|r2] → kanji[r1r2] with leading space, trim leading whitespace."""
    def _replace(m: re.Match) -> str:
        kanji = m.group(1)
        reading = m.group(2).replace('|', '')
        return f' {kanji}[{reading}]'
    return _TRANSCRIPT_RE.sub(_replace, text).lstrip()


def _is_kanji(char: str) -> bool:
	"""Check if a single character is a CJK unified ideograph (kanji)."""
	return _KANJI_RE.fullmatch(char) is not None


def _highlight_term(text: str, term: str) -> str:
	"""Wrap the first occurrence of term in <mark> tags."""
	pos = text.find(term)
	if pos == -1:
		return text
	return text[:pos] + '<mark>' + term + '</mark>' + text[pos + len(term):]



def _is_standalone_kanji(term: str, sentence: str, start: int, end: int) -> bool:
	"""Check if a pure-kanji term appears as a standalone token, not embedded in a kanji compound.

	A kanji term is considered standalone if the character immediately before it (if any) is not kanji and the character immediately after it (if any) is not kanji. Prevent indexing 玉 when it occurs inside Saitama, 郵便局 (post office), etc.
	"""
	if start > 0 and _is_kanji(sentence[start - 1]):
		return False
	return not (end < len(sentence) and _is_kanji(sentence[end]))


def _is_pure_kanji(term: str) -> bool:
	"""Check if a term consists entirely of kanji characters."""
	return all(_is_kanji(c) for c in term)


def _has_kanji(term: str) -> bool:
	"""Check if a term contains at least one kanji character."""
	return any(_is_kanji(c) for c in term)


def _leading_kanji(term: str) -> str:
	"""Return the leading kanji characters of a term.

	E.g. ``飾る`` → ``飾``, ``行う`` → ``行``, ``ああ`` → ``""``.
	"""
	result = ""
	for c in term:
		if _is_kanji(c):
			result += c
		else:
			break
	return result


def _kanji_reading(expression: str, reading_kana: str) -> str:
	"""Extract only the kana reading for kanji characters in expression.

	Identifies which positions in reading_kana correspond to kana characters in
	expression (1:1 mapping for kana).  Returns the remaining characters which
	belong to kanji.

	E.g. expression ``飾る`` (1 kana char), reading ``かざる`` → ``かざ``.
	     expression ``番号`` (0 kana chars), reading ``ばんごう`` → ``ばんごう``.
	     expression ``ああ`` (2 kana chars), reading ``ああ`` → ``""``.
	"""
	kana_count = sum(1 for c in expression if not _is_kanji(c))
	if kana_count == 0:
		return reading_kana
	# The last kana_count characters of reading_kana correspond to kana in expression.
	return reading_kana[:-kana_count]


def _extract_reading(text: str, pos: int, term_len: int) -> str:
	"""Extract the furigana reading following a term in transformed text.

	Given text like ``...学[がく]習...`` and the position/length of ``学``,
	returns ``がく``. Returns empty string if no furigana brackets follow.
	"""
	after = text[pos + term_len : pos + term_len + 1]
	if after != "[":
		return ""
	end = text.find("]", pos + term_len)
	if end == -1:
		return ""
	return text[pos + term_len + 1 : end]


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

def _load_sentence_transcription() -> pd.DataFrame:
	"""Load transcriptions, keep only sentence_id, username, transcription.

	Returns a column `has_username` indicating whether the username is non-empty.
	"""
	df = pd.read_csv(
		TRANSCRIPTION_PATH,
		sep="\t",
		header=None,
		names=["sentence_id", "language", "script_name", "username", "transcription"],
	)
	df = df[["sentence_id", "username", "transcription"]]
	df["has_username"] = df["username"].notna() & (df["username"].str.strip() != "")
	df = df.drop_duplicates(subset="sentence_id", keep="first")
	return df

def _load_sentence_audio() -> pd.DataFrame:
	"""Load sentences_with_audio.csv, keep only rows with a license."""
	df = pd.read_csv(
		SENTENCE_AUDIO_PATH,
		sep="\t",
		header=None,
		names=["sentence_id", "audio_id", "username", "license", "username_url"],
	)
	df = df.dropna(subset=["license"])
	df = df.drop_duplicates(subset="sentence_id", keep="first")
	return df


def _load_overrides() -> pd.DataFrame:
	"""Load manual sentence overrides from CSV.

	Returns empty DataFrame if the file does not exist or is empty.
	Expected columns: jmdict_seq, example_jp, example_en, example_sentence_id (optional)
	"""
	if not OVERRIDES_PATH.exists():
		return pd.DataFrame()
	df = pd.read_csv(OVERRIDES_PATH)
	return df


class SentenceMatcher:
	"""Matches Tatoeba sentences to vocab words and picks the best one."""

	def __init__(self, search_terms: set[str]) -> None:
		logging.info("Loading Tatoeba sentence data...")
		self.pairs = _load_sentence_pairs()
		self.audio = _load_sentence_audio()
		self.transcriptions = _load_sentence_transcription()

		self.audio_ids = set(self.audio["sentence_id"].unique())

		transc_with_user = self.transcriptions[self.transcriptions["has_username"]]
		transc_no_user = self.transcriptions[~self.transcriptions["has_username"]]
		self.trans_user_ids = set(transc_with_user["sentence_id"].unique())
		self.transc_no_user_ids = set(transc_no_user["sentence_id"].unique())
		self.transcription_map = dict(
			zip(self.transcriptions["sentence_id"], self.transcriptions["transcription"])
		)

		logging.info("Building word-to-sentence index...")
		self._index = self._build_index(search_terms)

		rank_counts = {0: 0, 1: 0, 2: 0}
		for entry in self._index.values():
			rank_counts[entry["t_rank"]] += 1
		logging.info(
			f"Sentence match distribution: "
			f"{rank_counts[0]} with transcription (username), "
			f"{rank_counts[1]} with transcription (no username), "
			f"{rank_counts[2]} without transcription"
		)

	def _transcription_rank(self, sentence_id: int) -> int:
		"""Return transcription priority rank: 0 = has username, 1 = no username, 2 = no transcription."""
		if sentence_id in self.trans_user_ids:
			return 0
		elif sentence_id in self.transc_no_user_ids:
			return 1
		else:
			return 2

	def _build_index(self, search_terms: set[str]) -> dict:
		"""Build a dict mapping (term, reading) to its best candidate sentence.

		Keys are ``(term, reading)`` tuples where ``reading`` is ``""`` for raw
		(no-furigana) sentences, or the kana reading extracted from a transcribed
		furigana annotation.  For every Japanese sentence, both the raw text and
		the transcribed text (if available) are scanned.  Among all candidates per
		key the best is kept (preferring transcription with username, then without,
		then shorter sentence).
		"""
		index: dict[tuple[str, str], dict] = {}
		pure_kanji_terms = {t for t in search_terms if _is_pure_kanji(t)}
		kanji_terms = {t for t in search_terms if _has_kanji(t)}
		selector = TranscriptionThenShortestSelector()

		sentences = self.pairs.itertuples(index=False)
		for row in sentences:
			jp = row.jp_sentence
			length = len(jp)
			if length < MIN_SENTENCE_CHARS or length > MAX_SENTENCE_CHARS:
				continue

			has_audio = row.sentence_id in self.audio_ids
			t_rank = self._transcription_rank(row.sentence_id)

			raw_transcription = self.transcription_map.get(row.sentence_id)
			jp_transcribed = _transform_transcription(raw_transcription) if raw_transcription else None

			for term in search_terms:
				# Find the term in the raw sentence first.
				pos = jp.find(term)
				if pos == -1:
					continue

				# For kanji terms, skip if embedded in a compound.
				if term in pure_kanji_terms and not _is_standalone_kanji(
					term, jp, pos, pos + len(term)
				):
					continue

				# Transcribed path — extract reading from furigana annotation (kanji only).
				if jp_transcribed is not None:
					reading = ""
					if term in kanji_terms:
						lead = _leading_kanji(term)
						if lead:
							t_pos = jp_transcribed.find(lead)
							if t_pos != -1:
								reading = _extract_reading(jp_transcribed, t_pos, len(lead))
					candidate = {
						"jp": jp_transcribed,
						"en": row.en_meaning,
						"sentence_id": row.sentence_id,
						"has_audio": has_audio,
						"length": length,
						"t_rank": t_rank,
						"term_form": f"{term}[{reading}]" if reading else term,
					}
					key = (term, reading)
					if key not in index:
						index[key] = candidate
					elif selector.is_better(candidate, index[key]):
						index[key] = candidate

				# Raw path — only for sentences that have no transcription at all.
				else:
					candidate = {
						"jp": jp,
						"en": row.en_meaning,
						"sentence_id": row.sentence_id,
						"has_audio": has_audio,
						"length": length,
						"t_rank": t_rank,
						"term_form": term,
					}
					key = (term, "")
					if key not in index:
						index[key] = candidate
					elif selector.is_better(candidate, index[key]):
						index[key] = candidate

		return index

	def find_sentence_for_word(self, search_term: str, reading: str = "") -> dict:
		"""Find the best Tatoeba sentence containing the given word.

		Parameters
		----------
		search_term : str
			The kanji or kana form to search for.
		reading : str
			The kana reading to prefer for kanji terms (e.g. `がく` for `学`). If a reading-specific match exists it is returned; otherwise falls back to the reading-agnostic entry.

		Returns
		-------
		dict
			Dict with keys ``jp``, ``en``, ``sentence_id``, ``has_audio``, and ``term_form`` (the form to highlight, e.g. 学[がく]).  Empty dict if no match found.
		"""
		if not search_term:
			return {}

		result = None
		if reading:
			result = self._index.get((search_term, reading))
		if result is None:
			result = self._index.get((search_term, ""))
		if not result:
			return {}

		return {
			"jp": result["jp"],
			"en": result["en"],
			"sentence_id": int(result["sentence_id"]),
			"has_audio": bool(result["has_audio"]),
			"term_form": result.get("term_form", search_term),
		}

	def match_all(self, df: pd.DataFrame) -> pd.DataFrame:
		"""Add example sentence columns to the vocabulary DataFrame.

		Adds columns: example_jp, example_en, example_sentence_id, example_has_audio

		Parameters
		----------
		df : pd.DataFrame
			Must have columns "expression" and "reading".

		Returns
		-------
		pd.DataFrame
			df with new sentence columns appended.
		"""
		results = []
		total = len(df)
		for i, row in df.iterrows():
			if i % 500 == 0:
				logging.debug(f"Matching sentences: {i}/{total}")
			term = row["expression"] if "[" in row.get("reading", "") else row.get("reading", "")
			reading_kana = row.get("reading_kana", "")
			if _has_kanji(term) and reading_kana:
				reading = _kanji_reading(term, reading_kana)
			else:
				reading = ""
			results.append(self.find_sentence_for_word(term, reading))

		rdf = df.copy()
		rdf["example_jp"] = [r.get("jp", "") for r in results]
		rdf["example_en"] = [r.get("en", "") for r in results]
		rdf["example_sentence_id"] = [r.get("sentence_id", None) for r in results]
		rdf["example_has_audio"] = [r.get("has_audio", False) for r in results]

		# Apply manual overrides
		rdf = self._apply_overrides(rdf)

		# Highlight matched term in example sentences
		for i, row in rdf.iterrows():
			if not row["example_jp"]:
				continue
			term_form = results[i].get("term_form", "")
			if not term_form:
				continue
			rdf.at[i, "example_jp"] = _highlight_term(row["example_jp"], term_form)

		matched = rdf["example_jp"].ne("").sum()
		with_audio = rdf["example_has_audio"].sum()
		logging.info(
			f"Matched {matched}/{total} words to sentences "
			f"({with_audio} with audio)"
		)

		return rdf

	def _apply_overrides(self, rdf: pd.DataFrame) -> pd.DataFrame:
		"""Replace auto-matched sentences with manual overrides.

		Reads overrides from a CSV keyed on jmdict_seq. Any non-empty column in the override row replaces the corresponding auto-matched value.
		"""
		overrides = _load_overrides()
		if overrides.empty:
			return rdf

		required = {"jmdict_seq", "example_jp", "example_en"}
		missing = required - set(overrides.columns)
		if missing:
			logging.warning(f"Override file missing columns: {missing}")
			return rdf

		for _, row in overrides.iterrows():
			seq = row["jmdict_seq"]
			mask = rdf["jmdict_seq"] == seq
			if not mask.any():
				logging.debug(f"Override jmdict_seq {seq} not found in vocabulary")
				continue

			if pd.notna(row.get("example_jp")) and row["example_jp"] != "":
				rdf.loc[mask, "example_jp"] = row["example_jp"]
			if pd.notna(row.get("example_en")) and row["example_en"] != "":
				rdf.loc[mask, "example_en"] = row["example_en"]
			if pd.notna(row.get("example_sentence_id")):
				rdf.loc[mask, "example_sentence_id"] = int(row["example_sentence_id"])
			if pd.notna(row.get("example_has_audio")):
				rdf.loc[mask, "example_has_audio"] = bool(row["example_has_audio"])

		overridden = overrides.shape[0]
		logging.info(f"Applied {overridden} manual sentence override(s)")
		return rdf

	def download_sentence_audio(self, df: pd.DataFrame) -> pd.DataFrame:
		"""Mark sentence audio availability (Tatoeba audio not available for direct download).

		Parameters
		----------
		df : pd.DataFrame
			Must have columns example_sentence_id and example_has_audio.

		Returns
		-------
		pd.DataFrame
			df with new column example_audio_path (always NaN since Tatoeba	audio is not available for direct download).
		"""
		rdf = df.copy()
		rdf["example_audio_path"] = pd.NA
		return rdf
