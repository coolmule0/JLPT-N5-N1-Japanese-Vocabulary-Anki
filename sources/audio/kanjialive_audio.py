"""KanjiAlive audio source — matches local MP3 files to jmdict entries."""

import ast
import logging
import string
from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd

def extract_kanji_text(x):
	try:
		return x[0]["text"]
	except (TypeError, KeyError, IndexError):
		return None


class KaAudio():
	def __init__(self) -> None:
		self._data_path = Path("original_data", "kanji_alive", "ka_data.csv")
		self._audio_path = Path("original_data", "kanji_alive", "audio-mp3")

	def add_audio(self, jmdict: pd.DataFrame, main_df: pd.DataFrame) -> pd.DataFrame:
		logging.info("Adding KanjiAlive audio...")
		audio_df = self._build_audio_lookup(jmdict)
		logging.debug(f"Matched {len(audio_df)} entries to jmdict")
		result = main_df.merge(audio_df, on="jmdict_seq", how="left")
		logging.debug(f"Rows with audio: {result['audio_path'].notna().sum()}/{len(result)}")
		return result

	def _build_audio_lookup(self, jmdict: pd.DataFrame) -> pd.DataFrame:
		"""Read the Ka CSV, match each row to a jmdict entry, return [jmdict_seq, audio_path]."""
		df = pd.read_csv(self._data_path)

		df["examples_parsed"] = df["examples"].apply(ast.literal_eval)
		df = df.explode("examples_parsed").reset_index(drop=True)
		df[["word_raw", "meaning"]] = pd.DataFrame(df["examples_parsed"].tolist(), index=df.index)
		df[["word", "reading"]] = df["word_raw"].str.extract(r"^(.*?)（(.*?)）$")
		df["suffix"] = df.groupby("kname").cumcount().apply(lambda x: string.ascii_lowercase[x])
		df["audio_path"] = df.apply(
			lambda row: self._audio_path / f"{row['kname']}_06_{row['suffix']}.mp3",
			axis=1,
		)

		# Drop multi-pronunciation entries (e.g. 得る (える/うる))
		df = df[~df["reading"].str.contains(r"/", na=False)]

		# Build jmdict lookup with both kanji text and kana reading
		# Each (kanji, reading) pair gets its own row so matching is unambiguous
		jmdict_rows = []
		for _, entry in jmdict.iterrows():
			kanji_text = extract_kanji_text(entry["kanji"])
			if not kanji_text:
				continue
			for kana_item in entry.get("kana", []):
				jmdict_rows.append({
					"merge_key": kanji_text,
					"reading": kana_item["text"],
					"id": entry["id"],
				})
		jmdict_key = pd.DataFrame(jmdict_rows)

		# Match to jmdict via both kanji text AND reading
		merged = df.merge(
			jmdict_key[["merge_key", "reading", "id"]],
			left_on=["word", "reading"],
			right_on=["merge_key", "reading"],
			how="left",
		)
		merged = merged[merged["merge_key"].notna() & (merged["merge_key"] != "")]
		merged = merged.drop_duplicates(subset=["merge_key", "reading"])

		return merged.rename(columns={"id": "jmdict_seq"})[["jmdict_seq", "audio_path"]]
