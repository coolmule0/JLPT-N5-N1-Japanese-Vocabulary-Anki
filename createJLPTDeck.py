import json
import os
import re
import logging
from pathlib import Path
import zipfile

import pandas as pd

from jlpt_anki import AnkiPackage

"""
Uses the information stored in the csvs about words/jlpt-level, and the jmdict dictionary to create information-rich words for study.
"""

def setup() -> None:
	logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")


####################
## Extract/load data from files

def extract_jlpt_csvs_from_folder(folder_path: Path) -> pd.DataFrame:
	dfs = []
	
	for level in ["n5", "n4", "n3", "n2", "n1"]:
		csv_path = os.path.join(folder_path, f"{level}.csv")
		if os.path.exists(csv_path):
			df = pd.read_csv(csv_path)
			df["jlpt_level"] = level.upper()
			dfs.append(df)
	
	if dfs:
		merged_df = pd.concat(dfs, ignore_index=True)
		return merged_df
	else:
		return None

def load_jmdict_json_zip(jmdict_zip_file: Path) -> tuple[pd.DataFrame, dict]:
	"""
	Unzip and load up the jmdictionary in zipped json format.

	Returns: tuple: dictionary in dataframe form, and the tags mapping their occurence in the dictionary to a more verbose explanation
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
			unzip_file = path_name
			print(f"Extracted to: {unzip_file}")
	else:
		logging.info(f"Extraction skipped; jmdict json already exists: {unzip_file}")
		
			
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

####################
## Transform helpers

def extract_addition_engl(entry) -> list[str]:
	"""
	Extract all the additional definitions for the word
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

	E.g. (掃除する, そうじする) becomes 掃除[そうじ]する

	Args:
					kanji (string): Kanji of the word (can include kana as well).
					kana (string): Kana of the word
	Returns:
					string: Kanji word with furigana
	"""
	if not kana:
		assert False, "No kana reading provided."
		return
	if not kanji:
		return kana
	# what to put the furigana inside
	f_l = "["
	f_r = "]"

	# keep track of extra character spaces that are 'eaten' by kanjis
	tt = 0
	# furigana-kanji lists
	outWord = ""
	lastMatchLoc = 0
	fk = []
	# for each kanji in the word
	if kanji:
		# Search over kanji
		for m in re.finditer("[一-龯々]+", kanji):
			kanjiWordPos = m.span()[0]
			kanaWordPos = kanjiWordPos + tt

			# find the next furigana(s) in the kanji word
			searchLoc = m.span()[1]

			# Search over hiragana and katakana
			m2 = re.search(r"[ぁ-んァ-ヿ]+", kanji[searchLoc:])
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

def filter_english_definitions(additional_lst: list[list[str]], primary_eng_defns: list[str]) -> str:
	"""
	Grabs all the additional english definitions of the word. 
	
	E.g. 川 has a primary definition of "river", and 1 additional meaning as "the *something* river". This function returns "the *something* river".

	Remove duplicate entries.
	Limits total entries to not have too much info.

	Returns:
					string: comma separated additional english definitions
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

def clean(df) -> pd.DataFrame:
	rdf = df.copy()
	rdf = rdf.dropna(subset=["jmdict_seq"])  # Drop any rows with NaN values
	rdf["jmdict_seq"] = rdf["jmdict_seq"].astype(int) # convert from floats to ints
	
	# Drop duplicates in jmdict_seq, keeping the lowest/easiest level (which comes first in the df)
	dupes = rdf[rdf.duplicated(subset="jmdict_seq", keep="first")]
	logging.debug("Duplicated jmdict_seq rows dropped:")
	logging.debug(dupes["jmdict_seq"])
	rdf = rdf.drop(dupes.index)


	# fill NAN kanji with blank, since these values should be empty, it's not an error
	rdf["kanji"] = rdf["kanji"].fillna("")
	return rdf

def lookup_dict(dict_id: int, jmdict: pd.DataFrame) -> dict:
	"""
	Using the jmdict in json form (https://github.com/scriptin/jmdict-simplified/) imported as a pandas dataframe.
	"""
	entry = jmdict[jmdict["id"] == dict_id]
	if len(entry) < 1:
		logging.error(f"Not found {dict_id}")

	# Need .iloc[0][0] structure due to importing nested json into dataframe
	
	kanji = entry["kanji"].iloc[0][0]["text"] if len(entry["kanji"].iloc[0])  > 0 else ""
	kana = entry["kana"].iloc[0][0]["text"] if len(entry["kana"].iloc[0])  > 0 else ""

	additional = extract_addition_engl(entry)
			
	newdict = {
		# "expression": entry.kanji_forms[0],
		"reading_kanji": kanji,
		"reading_kana": kana,
		"english_definition": [x["text"] for x in entry["sense"].iloc[0][0]["gloss"]],
		"grammar": entry["sense"].iloc[0][0]["partOfSpeech"],
		"additional": additional,
		# "formality": entry["sense"].iloc[0][0]["misc"], #pol, hon,
		# "usually_kana": entry["sense"].iloc[0][0]["misc"], #uk
		"misc": entry["sense"].iloc[0][0]["misc"],
	}
	return newdict
	# expression,reading,english_definition,grammar,additional,tags,japanese_reading

def prepare_word_record(df: pd.DataFrame, jmdict_tags_mapping: dict) -> pd.DataFrame:
	"""
	Use the dictionary information to construct meaningful columns
	"""
	rdf = df.copy()
	rdf["english_definition"] = rdf["english_definition"].str.join(', ')
	rdf["grammar"] = df["grammar"].apply(lambda lst: [jmdict_tags_mapping[l] for l in lst])
	rdf["grammar"] = rdf["grammar"].str.join(', ')

	rdf["reduced_additional"] = df.apply(lambda x: filter_english_definitions(x["additional"], x["english_definition"]), axis=1)
	rdf["reduced_additional"] = rdf["reduced_additional"].str.join(', ')

	# Is the word usually written in kana?
	rdf["usually_kana"] = df["misc"].apply( lambda lst: True if "uk" in lst else False)

	# Make the furigana reading, but not necessary if the word is usually_kana
	rdf["reading"] = rdf.apply(
			lambda row: row["reading_kana"] if row["usually_kana"]=="usually_kana" else \
								make_furigana(row["reading_kanji"], row["reading_kana"]),
							axis=1)

	# Formality of the word
	formal_tags = ["hon", "pol", "hum"]
	rdf["formality"] = df["misc"].apply(lambda lst: [jmdict_tags_mapping[x] for x in lst if x in formal_tags])
	# rdf["formality"] = rdf["formality"].apply(lambda lst: [formal_map[l] for l in lst])

	rdf["expression"] = df.apply(lambda x: x["reading_kanji"] if x["reading_kanji"] != "" else x["reading_kana"], axis=1)

	rdf["tags"] = rdf.apply( lambda x: "usually_kana" if x["usually_kana"] else  "", axis = 1)
	rdf["tags"] = rdf.apply( lambda x: x["formality"] + [x["tags"]], axis=1)
	
	return rdf	

def finalise(df) -> pd.DataFrame:
	rdf = df.copy()

	# Column name tidy
	rdf = rdf.drop(["kana", "kanji", "waller_definition", "additional", "misc", "reading_kanji", "reading_kana", "usually_kana", "formality"], axis=1)
	rdf = rdf.rename({"reduced_additional": "additional"}, axis=1)

	# Data checks have expected structure for anki import
	assert rdf["tags"].apply(lambda x: isinstance(x, list)).all(), "tags column is not a list"
	required_cols = {"expression", "english_definition", "reading", "grammar", "additional"}
	assert required_cols.issubset(rdf.columns), f"Missing columns: {required_cols - set(rdf.columns)}"

	# Shuffle the rows
	rdf = rdf.sample(frac=1).reset_index(drop=True)

	return rdf

def transform(df: pd.DataFrame, jmdict: pd.DataFrame, jmdict_tags_mapping: dict) -> pd.DataFrame:
	rdf = df.copy()

	rdf = clean(rdf)

	# Use the data in the .CSVs to look up words in the dictionary. Return a new dataframe with the new information
	df_lookup = rdf.apply(lambda x: lookup_dict(x["jmdict_seq"], jmdict), axis=1, result_type="expand")
	# Join the original csv with the dictionary information
	rdf = pd.concat([rdf, df_lookup], axis=1)

	rdf = prepare_word_record(rdf, jmdict_tags_mapping)

	rdf = finalise(rdf)

	return rdf


####################
## Ready the words for export/Anki

def load(df: pd.DataFrame) -> None:
	"""
	Converts it to Anki data
	"""
	# Save to csv file
	csv_path = Path("output", "full.csv")
	logging.info(f"Saving csv to {csv_path}")
	df.to_csv(csv_path, index=False)

	# Store the info into an anki deck
	package = AnkiPackage()
	# Add a new note for each row/word
	df.apply(lambda x: package.add_note(x, x["jlpt_level"]), axis=1)

	package.save_to_folder("output")

####################
## The pipeline
def run():
	setup()

	# Load dictionary from json
	logging.info("Loading jmdict from zipped json...")
	jmdict, jmdict_tags_mapping = load_jmdict_json_zip(Path(f"original_data/jmdict-eng-3.6.1.zip"))

	# Load JLPT-by-level from .csv(s)
	logging.info("Loading JLPT words from csvs...")
	df = extract_jlpt_csvs_from_folder(Path("original_data"))
	
	# Transform/clean these csvs for use
	logging.info("Transforming data	...")
	df = transform(df, jmdict, jmdict_tags_mapping)

	# Transform/prepare the dataframe for use as anki flashcards
	logging.info("Finalising for anki...")
	load(df)

if __name__ == "__main__":
	run()
