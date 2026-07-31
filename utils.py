"""Shared utility functions.

Funcions useful for multiple scripts. Don't do much by themselves"""

import logging
import re


def make_furigana_surface(surface: str, headword: str, reading: str) -> str:
	"""Apply headword furigana mapping to a conjugated surface form.

	Uses make_furigana on the headword to determine which kanji groups map
	to which readings, then re-applies those same readings to the matching
	kanji groups in the surface form.

	e.g. surface='向かって', headword='向かう', reading='むかう'
	     => '向[む]かって'

	Falls back to returning the surface unchanged if the kanji groups
	don't align (different kanji used, or no kanji in headword).
	"""
	if not reading or not headword:
		return surface
	head_furigana = make_furigana(headword, reading)
	if not head_furigana:
		return surface
	groups = re.findall(r'([^\[ ]+?)\[([^\]]+)\]', head_furigana)
	if not groups:
		return surface
	result = ''
	surface_pos = 0
	for kanji_grp, grp_reading in groups:
		found_at = surface.find(kanji_grp, surface_pos)
		if found_at == -1:
			return surface
		result += surface[surface_pos:found_at]
		result += kanji_grp + '[' + grp_reading + ']'
		surface_pos = found_at + len(kanji_grp)
	result += surface[surface_pos:]
	return result


def make_furigana(kanji: str, kana: str) -> str:
	"""Generate a furigana word from associated kanji and kana. Is able to handle words with kana between the kanji.

	E.g.kanji: 男の子. kana: おとこのこ. returns 男[おとこ]の 子[こ] (notice the space so the furigana is aware of which characters it is pronouncing for)

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
