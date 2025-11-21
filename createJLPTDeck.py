import json
import re
import os.path
import time
import argparse
import logging
from typing import TextIO, List, Any

import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
from tqdm import tqdm 
import requests

"""
A script to download JLPT N5-N1 and common vocabulary from Jisho and output anki-ready csv decks.
 
Stores jisho call results to a .cache directory to avoid repeadly querying the site.
"""

# folder to save generated results in.
# This folder will contain a .csv and a .json
folder_name = "output"

logging.basicConfig(
	level=logging.INFO,
	format="%(asctime)s %(levelname)s %(message)s",
)


def getAudio(wordKanji: str, wordKana: str, saveDir: str, excludeFile: TextIO) -> bool:
	"""Download audio from Jisho.org for word

	Args:
					wordKanji (string): Kanji for the word
					wordKana (string): kana for the word
					saveDir (string): Where to save the audo
					excludeFile (fie): File for audio to not search for. Contains a single column of all words.mp3 that should not be downloaded. This function does not check this, only appends to it if it fails

	Returns:
					bool: whether word mp3 is saved in directory (not necessarily donwloading if it already exists)
	"""

	logging.debug(f"Attempting to download {wordKanji}")

	baseUrl = "https://jisho.org/search/"
	# search using both kanji and kana to ensure first result is desired
	search = (
		baseUrl + urllib.parse.quote(wordKanji) + "%20" + urllib.parse.quote(wordKana)
	)

	# get url page into a useable format
	try:
		page = urllib.request.urlopen(search).read()
	except:
		return False
	soup = BeautifulSoup(page, features="lxml")
	audiotag = soup.find("audio")
	# ensure it is of the first result
	if (audiotag) and (audiotag.find_parent("div", {"class": "exact_block"})):
		audioUrl = audiotag.find("source").get(
			"src"
		)  # assume audio would be first, if present
		urllib.request.urlretrieve(
			"http:" + audioUrl, saveDir + wordKanji + ".mp3"
		)  # source in webpage lacks "http:" prefix
		return True
	else:
		# Note word as failed- so can speed up next time by not checking
		with open(excludeFile, "a", encoding="utf-8") as f:
			f.write(wordKanji + ".mp3\n")
		return False


def get_all_of_level(level: str, fileName: str = ""):
	"""SLOW OPERATION. Download all the words for a `group` from Jisho and save into a json file.

	Args:
					level (string): Jisho Category to search for (e.g. N3) or tag (e.g. #common (note # for tag searches))
					fileName (string, optional): filename output to save json data. Defaults to "$(level).json"
	"""

	if fileName == "":
		fileName = level + ".json"

	# number of results returned from JSON query for a page
	num_results = 1
	# keep track of pages of results
	page = 1

	# Big JSON storage file
	all_jisho_results = []

	base_url = "https://jisho.org/api/v1/search/words"

	logging.info(f"Querying Jisho for {level} words")

	with requests.Session() as session:

		# Jisho has a limit of 20 results per page, so run for multiple pages until no more results.
		# We don't know how many pages there will be in advance before querying the site
		while True:
			params = {
				"keyword": f"#{level}",
				"page": page,
			}
			response = session.get(base_url, params=params)

			if response.status_code != 200:
				logging.error(f"Failed to fetch page {page}, status code: {response.status_code}")
				break

			text_response = response.json()
			data = text_response["data"]

			#json_results = query_jisho_term(f"#{level}&page={str(page_counter)}")
			num_results = len(data)

			# jisho.org currently has a limit of 1000 pages
			if num_results == 0 or page > 999:
				break

			all_jisho_results += data
			page += 1

			logging.info(f"Page {page}\r")

			#debug
			#page = 1000

	logging.info(f"Found {str(page - 1)} pages with {len(all_jisho_results)} words")

	# Write to a file
	with open(fileName, "w", encoding="utf-8") as jf:
		json.dump(all_jisho_results, jf, indent=3, ensure_ascii=False)

def extract_word_safe(val):
	"""
	Get the expression from the "japanese" dict structure returns from a jisho api word query.

	Returns:
					string: the word, in japanese

	"""
	if isinstance(val, list) and len(val) > 0:
		first = val[0]
		if isinstance(first, dict):
			return first.get('word', None)
	return None

def filter_english_definitions(senses) -> str:
	"""
	Grabs all the additional english definitions of the word. 
	
	E.g. 川 has a primary definition of "river", and 1 additional meaning as "the *something* river". This function returns "the *something* river".

	Coalates the all but the first english_definitions together. Ignores the definition if tagged as 'place' or 'wikipedia definition', as they seem to have worse definitions.
	Remove duplicate entries.
	Limits total entries to not have too much info.

	Returns:
					string: comma separated additional english definitions
	"""
	letter_limit = 100 # How many letters to limit the return string
	first_defs = set(defn.lower() for defn in senses[0].get('english_definitions', []))
	
	# Use the rest of the english definitions, without repeating those
	filtered_defs = []
	seen = set()  # To track duplicates (case-insensitive).

	for sense in senses[1:]:
		# Check if parts_of_speech contains neither "Place" nor "Wikipedia definition"
		if any(pos in ["Place", "Wikipedia definition"] for pos in sense.get("parts_of_speech", [])):
			continue
		
		for defn in sense.get("english_definitions", []):
			defn_lower = defn.lower()
			# Add if not in first sense and not already seen
			if defn_lower not in first_defs and defn_lower not in seen:
				filtered_defs.append(defn)
				seen.add(defn_lower)
	# Limit the total letters.
	letter_count = 0
	for i in range(len(filtered_defs)):
		single_def = filtered_defs[i]
		letter_count += len(single_def)
		if letter_count > letter_limit:
			filtered_defs = filtered_defs[:i]
			break
			
	return ", ".join(filtered_defs)

def extract_formality(senses):
	"""
	Extracts the formality tags from a string array

	Args:
					senses: senses section of the jlpt word info
	Returns:
					array: formalities this word/sense is. E.g. ["polite/teineigo"]
	"""
	tags = senses[0]["tags"]
	# a list of pairs. The first is the entry to accept. The latter is what will be provided into the final formality string
	accept = {
		"Humble (kenjougo) language": "humble/kenjougo",
		"Honorific or respectful (sonkeigo) language": "respectful/sonkeigo",
		"Polite (teineigo) language": "polite/teineigo",
	}
	formalities = []
	for t in tags:
		if t in accept:
			formalities.append(accept[t])
	return formalities

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
		assert(False, "No kana reading provided.")
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
		for m in re.finditer("[一-龯々]+", kanji):
			kanjiWordPos = m.span()[0]
			kanaWordPos = kanjiWordPos + tt

			# find the next furigana(s) in the kanji word
			searchLoc = m.span()[1]
			m2 = re.search(r"[ぁ-んァヿ]+", kanji[searchLoc:])
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


def data_to_flashcard(df_data: pd.DataFrame, flashcard_type: str) -> pd.DataFrame:
	"""
	Take the jisho json-as-dataframe data and convert each entry into a flashcard-ready structure.

	Returns:
					pd.DataFrame: tidied, study-ready definitions for each japanese word

	"""
	# Which columns in the output dataframe should be combined & dropped to form the card's tags column
	columns_as_tags = ['usually_kana', 'jlpt', 'formality']

	# The columns of the card. Defined here to have the column ordering obvious.
	cols = [
			"expression",
			"reading",
			"english_definition",
			"grammar",
			"additional",
			"tags", # the card's tags. Should be kept as the last column for Anki
		]
	df = pd.DataFrame(columns=cols)

	# Jiso API might return multiple results of the same slug. Drop them
	df["slug"] = df_data["slug"]
	dupes = df[df.duplicated(subset="slug", keep="first")]
	logging.debug("Duplicated rows dropped:")
	logging.debug(dupes["slug"])
	df = df.drop(dupes.index)
	df = df.drop(["slug"], axis=1)

	# The primary english definition of the word
	df["english_definition"] = df_data["senses"].apply(
		lambda x: ", ".join(x[0]["english_definitions"])
	)
	# The kanji/usual writing of the word
	df["expression"] = df_data["japanese"].apply(extract_word_safe)
	# The grammar structure of the word
	df["grammar"] = df_data["senses"].apply(
		# remove text from () and []
		lambda x: re.sub("[\(\[].*?[\)\]]", "", ", ".join(x[0]["parts_of_speech"]))
	)
	# Additional english definitions. Not usually how the word is primarily used, but can be used within the language
	df["additional"] = df_data["senses"].apply(filter_english_definitions)

	# Which JLPT grade(s)
	df["jlpt"] = df_data["jlpt"] # keeping as an array of jlpt tags
	# Whether the card is usually read as kana
	df["usually_kana"] = df_data["senses"].apply(
		lambda x: ["usually_kana"]
			if ("Usually written using kana alone" in x[0]["tags"]) else None # keep entries as array for easy merging in below step
	)
	# formality of the word
	df["formality"] = df_data["senses"].apply(extract_formality)

	# The kana-based reading of the word
	df["japanese_reading"] = df_data["japanese"].apply(
		lambda x: x[0]["reading"]
	)
	# The furigana kanji reading of the word
	df["reading"] = df.apply(
		lambda row: row["japanese_reading"] if row["usually_kana"]=="usually_kana" else make_furigana(row["expression"], row["japanese_reading"]),
		axis=1
	)
	df = df.drop(["japanese_reading"], axis=1) # finished with the purely kana. Now incorporated as furigana

	# Combine tag columns (specified in `columns_as_tags`) into single tags column. Expects the columns to have either array entries or Null/None
	df["tags"] = df[columns_as_tags].apply(
		lambda row: [i for sublist in row if sublist for i in sublist],
		axis=1
	)
	df = df.drop(columns_as_tags, axis=1)

	# Drop any words that are purely english. Words like ＰＥＴ
	english_pattern = re.compile(r'^[A-Za-zＡ-Ｚａ-ｚ]+$')
	df = df[~df["expression"].str.contains(english_pattern, regex=True, na=False)]

	# Ensure expression entry isn't empty. Can occur for kana only words (e.g. いいえ). Replace with the kana "reading"
	df["expression"] = df["expression"].fillna(df["reading"])

	# Tidy up the indices
	df = df.reset_index(drop=True)
	return df


def download_and_generate(jlpt_level: str, flashcard_type: str) -> pd.DataFrame:
	"""Download vocabulary from Jisho for a given jlpt grade, and generate the flashcard type's data.
	Saves resulting files in the "generated" folder as a .csv

	Args:
					jlpt_level (string): JLPT grade of #tag to search Jisho for. Either "jlpt-n5", "jlpt-n1" etc, or "common"
					flashcard_type (string [normal/extended]): [normal/extended] are the only valid arguments.
																					normal - contains standard vocabulary card columns.
																					extended - as normal, also with sound

	Returns:
					pd.DataFrame: dataframe of JLPT level
	"""

	os.makedirs(folder_name, exist_ok=True)
	cache_folder_name = ".cache"
	os.makedirs(cache_folder_name, exist_ok=True)


	# See if the Jisho vocabulary file is already cached.
	# If the file exists, assume it contains all the words.
	json_file = os.path.join(cache_folder_name, jlpt_level + ".json")
	if not os.path.isfile(json_file):
		get_all_of_level(jlpt_level, json_file)

	logging.info(f"---------- Converting {jlpt_level}")
	pddata = pd.read_json(json_file, encoding="utf8")

	# Transform the data 
	df = data_to_flashcard(pddata, flashcard_type)  

	# Write df to file
	csv_file = os.path.join(folder_name, jlpt_level + flashcard_type + ".csv")
	# df.to_csv(csv_file, encoding="utf-8", index=False, header=False)
	df.to_csv(csv_file, encoding="utf-8", index=False, header=True)

	return df


def parse_args(argv=None):
	parser = argparse.ArgumentParser(
		description="Download JLPT N5 to N1 and common vocabulary from Jisho and output anki-ready csv decks",
		formatter_class=argparse.ArgumentDefaultsHelpFormatter,
	)
	parser.add_argument(
		"-v", "--verbose", action="store_true", help="Print more verbose statements"
	)
	parser.add_argument(
		"-t",
		"--type",
		choices=["normal", "extended"],
		default="normal",
		type=str.lower,
		help="type of flashcard to generate",
	)
	parser.add_argument(
		"--grades",
		choices=["jlpt-n5", "jlpt-n4", "jlpt-n3", "jlpt-n2", "jlpt-n1", "common"],
		default=["jlpt-n5", "jlpt-n4", "jlpt-n3", "jlpt-n2", "jlpt-n1", "common"],
		nargs="+",
		type=str.lower,
		help="Comma separated list of JLPT grades to generate. E.g. `--grades jlpt-n3,jlpt-n5`. Defaults to all grades & common words.",
	)
	args = parser.parse_args(argv)

	if args.verbose:
		logging.getLogger().setLevel(logging.DEBUG)

	return args


if __name__ == "__main__":
	args = parse_args()

	for N in args.grades:
		download_and_generate(N, args.type)
