"""KanjiAlive audio source — matches local MP3 files to jmdict entries."""

import ast
import logging
import string
from abc import ABC, abstractmethod
from pathlib import Path
import urllib.request
import zipfile

import pandas as pd

def extract_kanji_text(x):
	try:
		return x[0]["text"]
	except (TypeError, KeyError, IndexError):
		return None

# location for grabbing ka_data.csv
ka_data_csv_url = "https://raw.githubusercontent.com/kanjialive/kanji-data-media/refs/heads/master/language-data/ka_data.csv"
# location for grabbing .mp3 audio files
kanji_alive_audio_files_url = "https://media.kanjialive.com/examples_audio/audio-mp3.zip"

class KaAudio():
	def __init__(self) -> None:
		self._data_path = Path("original_data", "kanji_alive", "ka_data.csv")
		self._audio_path = Path("original_data", "kanji_alive", "audio-mp3")
		self._audio_zip = Path("original_data", "kanji_alive", "audio-mp3.zip")
		self.setup_data()
	
	def setup_data(self, download_new = False) -> None:
		"""_summary_

		Parameters
		----------
		download_new : bool, optional
			ignores local files and attempts to fetch and overwrite local data from the provided URLs instead, by default False
		"""
		if download_new:
			logging.debug(f"Downloading Kanji Alive files from URLS")
			urllib.request.urlretrieve(ka_data_csv_url, self._data_path)
			urllib.request.urlretrieve(kanji_alive_audio_files_url, self._audio_zip)

		# If extraction folder doesn't exist, extract
		if not self._audio_path.is_dir():
			with zipfile.ZipFile(self._audio_zip, "r") as z:
				top_dirs = {n.split("/")[0] for n in z.namelist() if "/" in n}
				if top_dirs != {"audio-mp3"}:
					raise ValueError(f"Unexpected zip structure; expected all files under a single 'audio-mp3/' top folder, found top-level entries: {sorted(top_dirs)}")
				z.extractall(self._audio_path.parent)
				logging.debug(f"Extracted Kanji Alive mp3 audio files to: {self._audio_path}")
		else:
			logging.debug(f"Extraction of Kanji Alive mp3 audio skipped; folder {self._audio_path} already exists. Assuming all data already present.")


	def add_audio(self, jmdict: pd.DataFrame, main_df: pd.DataFrame) -> pd.DataFrame:
		logging.info("Adding KanjiAlive audio...")
		audio_df = self._build_audio_lookup(jmdict)
		logging.debug(f"Matched {len(audio_df)} audio entries to jmdict")
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
