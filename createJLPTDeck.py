"""Japanese Vocabulary Flashcard Generator

This script creates an anki-ready .apkg file for import into the Anki software. The .apkg file contains vocabulary cards ordered by JLPT difficulty.
Uses the information stored in the csvs about words/jlpt-level, and the jmdict dictionary to create information-rich words for study.
"""

import json
import os
import re
import logging
from pathlib import Path
import zipfile

import pandas as pd

from jlpt_anki import AnkiPackage
from wanikani_audio import download_missing_wanikani_audio

####################
## Extract/load data from files

def extract_jlpt_csvs_from_folder(folder_path: Path) -> pd.DataFrame:
	"""Coalate all the lines together from files called n5.csv, n2.csv etc.

	The csv should have the following columns: jmdict_seq,kana,kanji,waller_definition

	Parameters
	----------
	folder_path : Path
		Location holding files entitled n5.csv, n4.csv ... n1.csv

	Returns
	-------
	pd.DataFrame
		japanese vocabulary per row, including jlpt level information per word
	"""
	dfs = []
	
	for level in ["n5", "n4", "n3", "n2", "n1"]:
		csv_path = os.path.join(folder_path, f"{level}.csv")
		if os.path.exists(csv_path):
			df = pd.read_csv(csv_path)
			df["jlpt_level"] = level.upper()
			dfs.append(df)
	
	assert(len(dfs) > 0)
	
	merged_df = pd.concat(dfs, ignore_index=True)
	return merged_df

def load_jmdict_json_zip(jmdict_zip_file: Path) -> tuple[pd.DataFrame, dict[str, str]]:
	"""Unzip and extract the jm_dictionary in zipped json format.

	Parameters
	----------
	jmdict_zip_file : Path
		location of the jmdict file zip. Within the zip is just the .json version of the dictionary

	Returns
	-------
	tuple[pd.DataFrame, dict[str, str]]
		DataFrame version of the dictionary, and a mapping of the tags used in the dictionary to a more verbose human-understandable explanation

	Raises
	------
	ValueError
		Zip file should contain only one file within - the json formatted dictionary.
	"""

	# extraction folder is same place as zip (e.g., "data.zip" → "data")
	# extract_dir = os.path.splitext(jmdict_zip_file)[0]
	unzip_file = jmdict_zip_file.with_suffix(".json")
	folder = jmdict_zip_file.parents[0]

	# If extraction folder doesn't exist, extract
	if not os.path.exists(unzip_file):
		with zipfile.ZipFile(jmdict_zip_file, "r") as z:
			names = z.namelist()

			if len(names) != 1:
				raise ValueError(f"Expected exactly one file in the ZIP, found: {names}")
			
			path_name = z.extract(names[0], folder)
			unzip_file = Path(path_name)
			logging.debug(f"Extracted to: {unzip_file}")
	else:
		logging.debug(f"Extraction skipped; jmdict json already exists: {unzip_file}")
		
			
	with open(unzip_file, "r") as f:
		data = json.load(f)

	jmdict = pd.DataFrame(data["words"])
	jmdict["id"] = jmdict["id"].astype(int)

	# What the short tags used in the dictionary mean
	jmdict_tags_mapping = data["tags"]
	# custom changes:
	jmdict_tags_mapping["n"] = "noun"
	jmdict_tags_mapping["hon"] = "honorific/尊敬語"
	jmdict_tags_mapping["pol"] = "polite/丁寧語"
	jmdict_tags_mapping["hum"] = "humble/謙譲語"

	return (jmdict, jmdict_tags_mapping)

def extract_saved_wanikani_audio(audio_folder: Path) -> pd.DataFrame:
	"""Check what audio files already exist.

	Should be named with as a "interger.ext" e.g. 13456744.mp3, where the integer corresponds to the jmdict entry for the word

	Parameters
	----------
	audio_folder : Path
		Folder to search within for audio.

	Returns
	-------
	pd.DataFrame
		A row for each existing audio file.
	"""

	audio_files_dicts = []
	for child in audio_folder.iterdir():
		audio_file_dict = {
			"wani_audio_path": child,
			"jmdict_seq": int(child.stem),
		}
		audio_files_dicts.append(audio_file_dict)

	return pd.DataFrame(audio_files_dicts)

def extract() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, str], pd.DataFrame]:
	"""Extract data from sources.

	Returns
	-------
	tuple[pd.DataFrame, pd.DataFrame, dict[str, str], pd.DataFrame]
		The various data sources.
	"""

	# Extract dictionary from json
	jmdict, jmdict_tags_mapping = load_jmdict_json_zip(Path("original_data/jmdict-eng-3.6.1.zip"))
	logging.info("Extracted jmdict from zipped json.")

	# Extract JLPT-by-level from .csv(s)
	df = extract_jlpt_csvs_from_folder(Path("original_data"))
	logging.info("Extracted JLPT words from csvs.")

	# Extract any existing wanikani audio files
	wani_audio = extract_saved_wanikani_audio(Path("original_data", "wanikani"))
	logging.info("Extracted existing wanikani audio.")

	return df, jmdict, jmdict_tags_mapping, wani_audio

####################
## Transform helpers

def find_addition_engl(entry: pd.DataFrame) -> list[list[str]]:
	"""Read from the dictionary columns further english definitions of the word

	A word can have multiple different meanings beyond the primary.
	E.g. 川 has a primary definition of "river", and 1 additional meaning as "the *something* river". This function returns "the *something* river".

	Parameters
	----------
	entry : pd.DataFrame
		An entry from the jmdict for a given word/id

	Returns
	-------
	list[list[str]]
		English meanings for the word. Each inner list are related entries. Each outer list are distinct entries.
		For example "read" in the dictionary has outer entries for the past tense, for the present tense.
		And it has multiple inner entries for each outer entry, such as [to look at words, to say the words]
	"""

	adds = []
	# Every sense after the first
	for i in entry["sense"].iloc[0][1:]:
		accept = True
		for m in i["misc"]:
			# not an archaic usage, nor place name
			if m in ["arch", "place"]:
				accept = False
		# grammar usage is the same.
		# E.g. reject english definitions when the verb is intransitive rather than the primary definition usage
		if i["partOfSpeech"] != entry["sense"].iloc[0][0]["partOfSpeech"]:
			accept = False
		# Combine the texts together in an array
		if accept:
			adds.append([x["text"] for x in i["gloss"]])
	return adds

def make_furigana(kanji: str, kana: str) -> str:
	"""Generate a furigana word from associated kanji and kana. Is able to handle words with kana between the kanji.

	Parameters
	----------
	kanji : str
		Kanji of the word (can include kana as well)
	kana : str
		(hira/kata)kana of the word

	Returns
	-------
	str
		Kanji word with furigana
	"""

	if not kana:
		assert False, "No kana reading provided."
		return
	if not kanji:
		return kana
	# what to put the furigana inside
	f_l = "["
	f_r = "]"

	KANJI_PATTERN = r"[一-龯々０-９Ａ–Ｚ]+"
	KANA_PATTERN = r"[ぁ-んァ-ヿ]+"

	# keep track of extra character spaces that are 'eaten' by kanjis
	tt = 0
	# furigana-kanji lists
	outWord = ""
	lastMatchLoc = 0
	fk = []
	# for each kanji in the word
	if kanji:
		# Search over kanji
		for m in re.finditer(KANJI_PATTERN, kanji):
			kanjiWordPos = m.span()[0]
			kanaWordPos = kanjiWordPos + tt

			# find the next furigana(s) in the kanji word
			searchLoc = m.span()[1]

			# Search over hiragana and katakana
			m2 = re.search(KANA_PATTERN, kanji[searchLoc:])
			if m2:
				# find this kana match in the kana word
				searchLoc = searchLoc + tt
				m3 = re.search(m2.group(), kana[searchLoc:])
				# if no matching found, assume something wrong with the input
				if not m3:
					return ""

				# get the kana between these
				s = kana[kanaWordPos : searchLoc + m3.span()[0]]

				# update number of kanas 'eaten' by kanjis
				tt = tt + m3.span()[0]

			else:
				s = kana[kanaWordPos:]

			# the furigana'd kanji string, separated by space
			out = " " + m.group() + f_l + s + f_r
			outWord = outWord + kanji[lastMatchLoc:kanjiWordPos] + out
			fk.append(out)

			# update position of last kanji searched
			lastMatchLoc = m.span()[1]

	# update the out word for tailing kanas
	outWord = outWord + kanji[lastMatchLoc:]
	if outWord == "":
		logging.debug(f"Returning empty furigana-word for {kana}")
	return outWord.strip()

def filter_english_definitions(additional_lst: list[list[str]], primary_eng_defns: list[str]) -> list[str]:
	"""Limit the additional english definitions obtained to parameters. 

	Remove duplicate entries. Limit total entries to not have too much info.

	Parameters
	----------
	additional_lst : list[list[str]]
		The additional definitions of the word in English
	primary_eng_defns : list[str]
		The primary English definitions of the word

	Returns
	-------
	list[str]
		The additional english definitions for the word
	"""

	letter_limit = 200 # How many letters to limit the return string
	first_defs = set(defn.lower() for defn in primary_eng_defns)
	
	# Use the rest of the english definitions, without repeating those
	filtered_defs = []
	seen = set()  # To track duplicates (case-insensitive).

	for senses in additional_lst:
		for s in senses:
		
		# for defn in sense.get("english_definitions", []):
			defn_lower = s.lower()
			# Add if not in first sense and not already seen
			if defn_lower not in first_defs and defn_lower not in seen:
				filtered_defs.append(s)
				seen.add(defn_lower)
	# Limit the total letters.
	letter_count = 0
	for i in range(len(filtered_defs)):
		single_def = filtered_defs[i]
		letter_count += len(single_def)
		if letter_count > letter_limit:
			filtered_defs = filtered_defs[:i]
			break
			
	return filtered_defs

####################
## Transforms

def clean(df: pd.DataFrame) -> pd.DataFrame:
	"""Fix issues in the source data before transforming.

	Parameters
	----------
	df : pd.DataFrame
		The dataframe with a row per Japanese word

	Returns
	-------
	pd.DataFrame
		Cleaned dataframe
	"""

	rdf = df.copy()
	rdf = rdf.dropna(subset=["jmdict_seq"]).copy()  # Drop any rows with NaN values
	rdf["jmdict_seq"] = rdf["jmdict_seq"].astype(int) # convert from floats to ints
	
	# Drop duplicates in jmdict_seq, keeping the lowest/easiest level (which comes first in the df)
	dupes = rdf[rdf.duplicated(subset="jmdict_seq", keep="first")]
	logging.debug("Duplicated jmdict_seq rows dropped:")
	logging.debug(dupes["jmdict_seq"])
	rdf = rdf.drop(dupes.index)


	# fill NAN kanji with blank, since these values should be empty, it's not an error
	rdf["kanji"] = rdf["kanji"].fillna("")
	return rdf

def lookup_dict(dict_id: int, jmdict: pd.DataFrame) -> dict[str, str|list[str]]:
	"""Look up the information about a given entry in the JMDict

	Parameters
	----------
	dict_id : int
		id of japanese word in the JMDict
	jmdict : pd.DataFrame
		the jmdict in json form (https://github.com/scriptin/jmdict-simplified/) imported as a pandas dataframe

	Returns
	-------
	dict[str, str|list[str]]
		JMDict information for the word
	"""

	entry = jmdict[jmdict["id"] == dict_id]
	if len(entry) < 1:
		logging.error(f"Not found {dict_id}")
	if len(entry) > 1:
		logging.error(f"Too many entries found in dictionary for id {dict_id}")

	# Need .iloc[0][0] structure due to importing nested json into dataframe
	
	kanji = entry["kanji"].iloc[0][0]["text"] if len(entry["kanji"].iloc[0])  > 0 else ""
	kana = entry["kana"].iloc[0][0]["text"] if len(entry["kana"].iloc[0])  > 0 else ""

	additional = find_addition_engl(entry)
			
	newdict = {
		# "expression": entry.kanji_forms[0],
		"reading_kanji": kanji,
		"reading_kana": kana,
		"english_definition": [x["text"] for x in entry["sense"].iloc[0][0]["gloss"]],
		"grammar": entry["sense"].iloc[0][0]["partOfSpeech"],
		"additional": additional,
		"misc": entry["sense"].iloc[0][0]["misc"],
	}
	return newdict
	# expression,reading,english_definition,grammar,additional,tags,japanese_reading

def prepare_word_record(df: pd.DataFrame, jmdict_tags_mapping: dict[str, str]) -> pd.DataFrame:
	"""Enhance the dataframe information to have vocab-study-ready columns

	Parameters
	----------
	df : pd.DataFrame
		Dictionary-enriched, one row per japanese vocabulary word
	jmdict_tags_mapping : dict[str, str]
		mapping of JMDict abbreviations and their human-understandable extention (such as 'n' for noun)

	Returns
	-------
	pd.DataFrame
		Extended dataframe containing columns suitable for anki flashcards
	"""
	rdf = df.copy()
	rdf["english_definition"] = rdf["english_definition"].str.join(', ')
	rdf["grammar"] = rdf["grammar"].apply(lambda lst: [jmdict_tags_mapping[item] for item in lst])
	rdf["grammar"] = rdf["grammar"].str.join(', ')

	rdf["reduced_additional"] = df.apply(lambda x: filter_english_definitions(x["additional"], x["english_definition"]), axis=1)
	rdf["reduced_additional"] = rdf["reduced_additional"].str.join(', ')

	# Is the word usually written in kana?
	rdf["usually_kana"] = df["misc"].apply( lambda lst: True if "uk" in lst else False)

	# Make the furigana reading, but not necessary if the word is usually_kana
	rdf["reading"] = rdf.apply(
			lambda row: row["reading_kana"] if row["usually_kana"] else \
								make_furigana(row["reading_kanji"], row["reading_kana"]),
							axis=1)

	###
	# Tags part
	# Formality of the word
	formal_tags = ["hon", "pol", "hum"]
	rdf["formality"] = rdf["misc"].apply(lambda lst: [jmdict_tags_mapping[x] for x in lst if x in formal_tags])
	
	# Rarely used words
	rdf["rare"] = rdf["misc"].apply(lambda lst: ["rare_term" for x in lst if x in ["rare"]])

	rdf["tags"] = rdf.apply( lambda x: "usually_kana" if x["usually_kana"] else  "", axis = 1)
	rdf["tags"] = rdf.apply( lambda x: x["formality"] + [x["tags"]] + x["rare"], axis=1)
	
	rdf["expression"] = df.apply(lambda x: x["reading_kanji"] if x["reading_kanji"] != "" else x["reading_kana"], axis=1)

	return rdf


def finalise(df: pd.DataFrame) -> pd.DataFrame:
	"""Drop and finishing touches to the dataframe

	Parameters
	----------
	df : pd.DataFrame
		one row per japanese word, still containing extraneous columns not needed for anki decks

	Returns
	-------
	pd.DataFrame
		one row per japanese word, fully transformed
	"""
	rdf = df.copy()

	# Column name tidy
	rdf = rdf.drop(["kana", "kanji", "waller_definition", "additional", "misc", "reading_kanji", "reading_kana", "usually_kana", "formality"], axis=1)
	rdf = rdf.rename({"reduced_additional": "additional"}, axis=1)

	# Data checks have expected structure for anki import
	assert rdf["tags"].apply(lambda x: isinstance(x, list)).all(), "tags column is not a list"
	required_cols = {"expression", "english_definition", "reading", "grammar", "additional"}
	assert required_cols.issubset(rdf.columns), f"Missing columns: {required_cols - set(rdf.columns)}"

	# Shuffle the rows
	# rdf = rdf.sample(frac=1).reset_index(drop=True)
	rdf = (
	rdf.groupby('jlpt_level', group_keys=True)
				.sample(frac=1, random_state=42)
				.reset_index(drop=True)
	)
	# Rearrange columns
	rdf = rdf[["jlpt_level", "expression", "english_definition", "reading", "grammar", "additional", "tags", "wani_audio_path"]]

	return rdf

def drop_equivalent_rows(df: pd.DataFrame) -> pd.DataFrame:
	"""Remove words that might pop up twice in Anki yet look like almost the same word. These two words have distinct entries in JMDict

	For example, こと and 事(pronouced こと) (usually kana) have very similar meanings, have the same entry in the flashcard due to both being written in kana.
	One should be removed to avoid similar/repeat entries in the flashcards.
	Keeps the one that is labeled as the easier grade.

	Parameters
	----------
	df : pd.DataFrame
		You know it by now. One row per vocab word

	Returns
	-------
	pd.DataFrame
		Reduced, removing any potential multiples following the specified rule.
	"""
	df = df.copy()

	# Identify rows
	has_kanji_and_usually_kana = df["kanji"].ne("") & df["tags"].apply(lambda t: "usually_kana" in t)
	blank_kanji = df["kanji"].eq("")

	# JLPT difficulty ranking (lower number = easier)
	jlpt_rank = {"N5": 1, "N4": 2, "N3": 3, "N2": 4, "N1": 5, "common": 6}

	# To drop
	drop_indices = []

	# Group by reading
	for reading, group in df.groupby("reading"):
		idx_usually = group.index[has_kanji_and_usually_kana.loc[group.index]]
		idx_blank = group.index[blank_kanji.loc[group.index]]

		# Only act if both types are present
		if len(idx_usually) > 0 and len(idx_blank) > 0:
			for i1 in idx_usually:
				for i2 in idx_blank:
					# Compare JLPT levels
					rank1 = jlpt_rank[df.at[i1, "jlpt_level"]]
					rank2 = jlpt_rank[df.at[i2, "jlpt_level"]]

					if rank1 > rank2:
						# i1 is harder, drop it
						drop_indices.append(i1)
					elif rank2 > rank1:
						# i2 is harder, drop it
						drop_indices.append(i2)
					else:
						# Tie or unknown — drop higher index as fallback
						drop_indices.append(max(i1, i2))
	print(drop_indices)
	# Return df with the designated rows dropped
	return df.drop(index=set(drop_indices))

def transform(df: pd.DataFrame, jmdict: pd.DataFrame, jmdict_tags_mapping: dict[str, str], wani_audio: pd.DataFrame) -> pd.DataFrame:
	"""Transform the extracted data, ready for loading.

	Parameters
	----------
	df : pd.DataFrame
		jlpt-graded and jmdict entry column'ed dataframe
	jmdict : pd.DataFrame
		Dictionary
	jmdict_tags_mapping : dict[str, str]
		dictionary abbr tags to human explained
	wani_audio : pd.DataFrame
		columns with corresponding jmdict entry, and path saved at

	Returns
	-------
	pd.DataFrame
		Load-ready
	"""
	rdf = df.copy()

	rdf = clean(rdf)

	# Use the data in the .CSVs to look up words in the dictionary. Return a new dataframe with the new information
	df_lookup = rdf.apply(lambda x: lookup_dict(x["jmdict_seq"], jmdict), axis=1, result_type="expand")
	# Join the original csv with the dictionary information
	rdf = pd.concat([rdf, df_lookup], axis=1)

	rdf = prepare_word_record(rdf, jmdict_tags_mapping)

	# drop edge cases of competing reading rows that have multiple entries, where some have only kanji but usually kana and some are only kana
	rdf = drop_equivalent_rows(rdf)

	# Add audio to the df
	rdf = rdf.merge(
		wani_audio,
		on="jmdict_seq",
		how="left",
	)

	# Download and add missing audio
	rdf = download_missing_wanikani_audio(rdf, wani_audio)

	rdf = finalise(rdf)

	return rdf


####################
## Ready the words for export/Anki

def load(df: pd.DataFrame) -> None:
	"""Load the information to saved formats.

	Saves to .apkg and .csv files

	Parameters
	----------
	df : pd.DataFrame
		Containing all the important information needed for saving to anki formats
	"""
	# Save to csv file
	csv_path = Path("output", "full.csv")
	logging.info(f"Saving csv to {csv_path}")
	df.to_csv(csv_path, index=False)

	# Store the info into anki packages (made up of multiple decks)
	deck_types = ["core", "extended"]
	for dt in deck_types:
		package = AnkiPackage(dt)
		# Add a new note for each row/word
		for _, row in df.iterrows():
			package.add_note(row, row["jlpt_level"])

		package.save_to_folder(Path("output"))

		logging.debug(f"Cards per deck: {package.get_cards_in_deck()}")


####################
## The pipeline
def run() -> None:
	"""The main extract-transform-load (ETL) loop"""

	# Set logging level
	logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

	logging.info("Extracting info from files...")
	df, jmdict, jmdict_tags_mapping, wani_audio = extract()

	# Transform/clean these csvs for use
	logging.info("Transforming data	...")
	df = transform(df, jmdict, jmdict_tags_mapping, wani_audio)

	# Transform/prepare the dataframe for use as anki flashcards
	logging.info("Finalising for anki...")
	load(df)

if __name__ == "__main__":
	run()
