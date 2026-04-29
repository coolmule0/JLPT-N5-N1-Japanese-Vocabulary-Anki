import ast
import string
from pathlib import Path


import pandas as pd

from .etl_audio import EtlAudio


# df = pd.read_csv(Path("original_data", "kanji_alive", "ka_data.csv"))

# df["examples_parsed"] = df["examples"].apply(ast.literal_eval)

# df = df.explode("examples_parsed").reset_index(drop=True)

# df[["word_raw", "meaning"]] = pd.DataFrame(df["examples_parsed"].tolist(), index=df.index)

# df[["word", "reading"]] = df["word_raw"].str.extract(r"^(.*?)（(.*?)）$")

# df["suffix"] = df.groupby("kname").cumcount().apply(lambda x: string.ascii_lowercase[x])

# audio_path_file = Path("original_data", "kanji_alive", "audio-mp3")
# df["audio_path"] = df.apply(
# 	lambda row: audio_path_file / f"{row['kname']}_{row['suffix']}.mp3",
# 	axis=1
# )

# result = df[["kname", "word", "reading", "meaning", "audio_path"]]

# print(result)

# df1 = result.copy()
# df2 = pd.read_csv(Path("output", "full.csv"))



# merge_kanji = df1.merge(
# 	df2,
# 	left_on="word",
# 	right_on="expression",
# 	how="inner"
# )

# matches = merge_kanji
# # matches = pd.concat([merge_kanji, merge_reading]).drop_duplicates()

# print(matches)

# matches.to_csv("foo.csv", index=False)

# def construct_KA_df() -> pd.DataFrame:
# 	df = pd.read_csv(Path("original_data", "kanji_alive", "ka_data.csv"))

# 	df["examples_parsed"] = df["examples"].apply(ast.literal_eval)

# 	df = df.explode("examples_parsed").reset_index(drop=True)

# 	df[["word_raw", "meaning"]] = pd.DataFrame(df["examples_parsed"].tolist(), index=df.index)

# 	df[["word", "reading"]] = df["word_raw"].str.extract(r"^(.*?)（(.*?)）$")

# 	df["suffix"] = df.groupby("kname").cumcount().apply(lambda x: string.ascii_lowercase[x])

# 	audio_path_file = Path("original_data", "kanji_alive", "audio-mp3")
# 	df["audio_path"] = df.apply(
# 		lambda row: audio_path_file / f"{row['kname']}_{row['suffix']}.mp3",
# 		axis=1
# 	)

# 	result = df[["word", "reading", "meaning", "audio_path"]]
# 	return result

# def extract_kanji_text(x):
#     try:
#         return x[0]["text"]
#     except (TypeError, KeyError, IndexError):
#         return None

# def enrich(audio_df, jmdict_df) -> pd.DataFrame:
# 	## Finds the entries with audio and gets the matching jmdict_id for that word
# 	jmdict_comp_df = jmdict_df.copy()
# 	jmdict_comp_df["merge_key"] = jmdict_comp_df["kanji"].apply(extract_kanji_text)



# 	comb = audio_df.merge(
# 		jmdict_comp_df[["merge_key", "id"]],
# 		left_on="word",
# 		right_on="merge_key",
# 		how="inner"
# 	)
# 	# Loosing half the audio entries because they don't find the associated jmdict entry
# 	print(comb)
# 	print(len(comb))
# 	print("-----------------")
# 	elem = 500
# 	print(comb.iloc[elem])
# 	jmid = comb.iloc[elem]["id"]
# 	#1591791

# 	jmentry = jmdict_df[jmdict_df["id"] == int(jmid)]
# 	# jmdict_df[jmdict_df["id"] == 1591790]
# 	print(jmentry.to_string())


# 	print()

# 	return comb

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

		comb = audiodf.merge(
			jmdict_comp_df[["merge_key", "id"]],
			left_on="word",
			right_on="merge_key",
			how="inner"
		)

		comb["jmdict_seq"] = comb["id"]
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
