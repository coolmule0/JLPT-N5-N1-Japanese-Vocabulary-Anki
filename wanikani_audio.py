""" Handle the downloading of audio files from wanikani, and processing of local audio files."""
import logging
import time
from pathlib import Path
import json

import pandas as pd
import requests
from tqdm import tqdm


def download_wanikani_vocab() -> pd.DataFrame:
	"""Query Wanikani for available vocabulary audio

	Skips any internet queries if the cache file is present. To force an update (e.g. if Wanikani has updated their audio) delete this cache file.

	Returns
	-------
	pd.DataFrame
		A row per vocab entry with a corresponding column for the url
	"""

	wanikani_cache_path = Path(".cache", "wanikani_vocab.json")

	# Assume the cache file existing means the data is already present and up to date
	if wanikani_cache_path.is_file():
		with open(wanikani_cache_path, 'r') as file:
			response_data = json.load(file)
	else:
		# get token
		wanikani_token_path = Path("wanikani_token")
		if wanikani_token_path.is_file():
			with open("wanikani_token", "r") as f:
				token = f.read()[:-1] # ignore newline
		else:
			logging.info(f"No wanikani token found at {wanikani_token_path}, skipping audio download.")
			return pd.DataFrame(columns=["slug", "reading_kana", "reading_kanji", "url"])
		
		if len(token) < 1:
			logging.debug("No debug token found.")
			return pd.DataFrame(columns=["slug", "reading_kana", "reading_kanji", "url"])

		
		url = "https://api.wanikani.com/v2/subjects"
		headers = {
			"Authorization": f"Bearer {token}"
		}

		payload = {"types": "vocabulary"}

		logging.debug("Querying wanikani.com for available vocabulary.")

		with requests.Session() as s:
			response = s.get(url, headers=headers, params=payload)
			response_data = response.json()["data"]

			next_page_url = response.json()["pages"]["next_url"]

			while next_page_url:
				response = s.get(next_page_url, headers=headers)
				response_data += response.json()["data"]

				next_page_url = response.json()["pages"]["next_url"]

		# Store the data in local cache
		wanikani_cache_path.parent.mkdir(parents=True, exist_ok=True)
		wanikani_cache_path.write_text(json.dumps(response_data))

	d_rows = []
	pron_rows = []
	for i in range(len(response_data)):
		d, prons = parse_entry(response_data[i]["data"])
		d_rows.append(d)
		pron_rows.extend(prons)

	df_entries = pd.DataFrame(d_rows)
	df_prons = pd.DataFrame(pron_rows)

	# Join the two frames into a single. Keep just the first available audio per word
	df_prons_first = df_prons.drop_duplicates(subset="slug", keep="first")
	df_entries = df_entries.merge(df_prons_first[["slug", "url"]], on="slug", how="left")
	df_entries

	return df_entries


def parse_entry(data: dict) -> tuple[dict, list]:
	"""Parse the json data return from a wanikani query into vocab data, and audio file download data.

	Parameters
	----------
	data : dict
		An entry for a word

	Returns
	-------
	tuple[dict, list]
		The wanikani vocab information for the word, and pronunciation information
	"""

	d = {
		"slug": data["slug"],
		"reading_kana": data["characters"],
		# "meaning": data["meanings"][0]["meaning"],
		"reading_kanji": data["readings"][0]["reading"],
	}

	prons = []
	for p in data["pronunciation_audios"]:
		p["slug"] = data["slug"]
		prons.append(p)

	return d, prons


def download_wanikani_audio_url(url: str, filename: str) -> Path:
	"""Download audio from the provided url and save it

	Parameters
	----------
	url : str
		url path for audio file
	filename : str
		Name to save audio file as (without extention)

	Returns
	-------
	Path
		Location of the saved file
	"""
	response = requests.get(url)
	response.raise_for_status()

	cd = response.headers.get('content-disposition')

	if cd:
		# Try to extract filename* (RFC 5987 encoded)
		filename_star_match = re.search(r'filename\*\s*=\s*([^;]+)', cd)
		if filename_star_match:
			# Format is something like: UTF-8''encoded_filename
			filename_star = filename_star_match.group(1)
			# Remove optional UTF-8'' prefix
			encoding_prefix = "UTF-8''"
			if filename_star.lower().startswith(encoding_prefix.lower()):
				filename_star = filename_star[len(encoding_prefix):]
			filename = unquote(filename_star)
		else:
			# Fallback to regular filename
			filename_match = re.search(r'filename\s*=\s*"([^"]+)"', cd)
			if filename_match:
				filename = unquote(filename_match.group(1))
	filename_path = Path("original_data", "wanikani", filename)
	filename_path = filename_path.with_name(f"{filename}{filename_path.suffix}")

	with open(filename_path, 'wb') as f:
		for chunk in response.iter_content(chunk_size=8192):
			f.write(chunk)
	return filename_path


def download_missing_wanikani_audio(df: pd.DataFrame, wani_audio: pd.DataFrame) -> pd.DataFrame:
	"""_summary_

	Parameters
	----------
	df : pd.DataFrame
		with audio paths as a column, filled for entries already existing
	wani_audio : pd.DataFrame
		currently downloaded audio

	Returns
	-------
	pd.DataFrame
		updated main df with the newly downloaded files also included
	"""
	rdf = df.copy()
	df_entries = download_wanikani_vocab()

	# only interested in entries that don't have vocab already locally downloaded
	df_no_audio = rdf[rdf["wani_audio_path"].isna()]

	# Assume words match when sharing both kanji and kana between wanikani and the jmdict
	dff = df_no_audio.merge(
		df_entries,
		on=['reading_kanji', "reading_kana"],
		how="left",
	)

	df_available = dff[~dff["url"].isnull()]

	if df_available.shape[0] > 0:
		for _, row in tqdm(df_available.iterrows(), total=df_available.shape[0]):
			filename_path = download_wanikani_audio_url(row["url"], row["jmdict_seq"])
			
			rdf[rdf[jmdict_seq] == row["jmdict_seq"]]["wani_audio_path"] = filename_path

			# Don't hit the servers too much
			time.sleep(1)

	return rdf