import logging
import time
from pathlib import Path

import pandas as pd
import requests
from tqdm import tqdm

"""
Handle the downloading of audio files from wanikani
"""

def download_wanikani_vocab() -> (pd.DataFrame):
	"""
	Returns: vocab entries and the audio download info 
	"""
	# get token
	with open("wanikani_token", "r") as f:
		token = f.read()[:-1] # ignore newline
	
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
		# TODO: add cache and store last modified. Store in .cache somewhere. Can avoid full page returns if no changes since previous call

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
	"""
	Parse the json data return from a wanikani query into vocab data, and audio file download data
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
	# url = row["url"]
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
	"""
	df: with audio paths as a column, filled for entries already existing

	returns: updated main df with the newly downloaded files also included
	"""
	rdf = df.copy()
	df_entries = download_wanikani_vocab()

	# only interested in entries that don't have vocab already locally downloaded
	df_no_audio = rdf[rdf["wani_audio_path"].isna()]

	dff = df_no_audio.merge(
		df_entries,
		on=['reading_kanji', "reading_kana"],
		how="left",
		# indicator=True
	)

	df_available = dff[~dff["url"].isnull()]

	# downloaded_dicts = []
	for _, row in tqdm(df_available.iterrows(), total=df_available.shape[0]):
		filename_path = download_wanikani_audio_url(row["url"], row["jmdict_seq"])
		
		# audio_dict = {
		# 	"wani_audio_path": filename_path,
		# 	"jmdict_seq": int(filename_path.stem),
		# }
		# downloaded_dicts.append[audio_dict]

		rdf[rdf[jmdict_seq] == row["jmdict_seq"]]["wani_audio_path"] = filename_path

		# Don't hit the servers too much
		time.sleep(1)

	# return pd.DataFrame(downloaded_dicts)
	return rdf