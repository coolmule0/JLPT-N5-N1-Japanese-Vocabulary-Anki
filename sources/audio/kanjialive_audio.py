import ast
import string
from pathlib import Path


import pandas as pd

from .etl_audio import EtlAudio


def extract_kanji_text(x):
	try:
		return x[0]["text"]
	except (TypeError, KeyError, IndexError):
		return None

class KaAudio(EtlAudio):
	def extract(self) -> pd.DataFrame:
		df = pd.read_csv(Path("original_data", "kanji_alive", "ka_data.csv"))

		df["examples_parsed"] = df["examples"].apply(ast.literal_eval)

		df = df.explode("examples_parsed").reset_index(drop=True)

		df[["word_raw", "meaning"]] = pd.DataFrame(df["examples_parsed"].tolist(), index=df.index)

		df[["word", "reading"]] = df["word_raw"].str.extract(r"^(.*?)（(.*?)）$")

		df["suffix"] = df.groupby("kname").cumcount().apply(lambda x: string.ascii_lowercase[x])

		audio_path_file = Path("original_data", "kanji_alive", "audio-mp3")
		df["audio_path"] = df.apply(
			lambda row: audio_path_file / f"{row['kname']}_06_{row['suffix']}.mp3",
			axis=1
		)

		result = df[["word", "reading", "meaning", "audio_path"]]
		return result

	def lookup(self, audiodf: pd.DataFrame, jmdict: pd.DataFrame):
		jmdict_comp_df = jmdict.copy()
		jmdict_comp_df["merge_key"] = jmdict_comp_df["kanji"].apply(extract_kanji_text)

		# Merge on kanji
		comb = audiodf.merge(
			jmdict_comp_df[["merge_key", "id"]],
			left_on="word",
			right_on="merge_key",
			how="inner"
		)
		# drop empty kanji. Otherwise they merge/match with some random yet specific entry
		comb = comb[comb["merge_key"].notna() & (comb["merge_key"] != "")]

		

		# Rename so matches expected format
		comb = comb.rename(columns={"id": "jmdict_seq"})

		print("leng:")
		print(len(comb))
		return comb[["jmdict_seq", "audio_path"]]

	def analysis(audiodf: pd.DataFrame, jmdict: pd.DataFrame):
		"""Offline analysis and exploration of the data"""
		# Loosing half the audio entries because they don't find the associated jmdict entry
		print(comb)
		print(len(comb))
		print("-----------------")
		elem = 500
		print(comb.iloc[elem])
		jmid = comb.iloc[elem]["id"]
		#1591791

		jmentry = jmdict_comp_df[jmdict_comp_df["id"] == int(jmid)]
		# jmdict_df[jmdict_df["id"] == 1591790]
		print(jmentry.to_string())


		print()
