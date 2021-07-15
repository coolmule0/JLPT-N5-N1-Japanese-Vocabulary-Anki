import json, urllib.request, urllib.parse, re, os.path
import time
import argparse

import pandas as pd
import numpy as np
from bs4 import BeautifulSoup

# folder to save generated results in
folder_name = "generated"
# For extra print statements
verbose = False

def getJapJs(e):
	"""Get the results of Jisho.org for the word or search 'e', in JSON form

	Args:
		e (string): Jisho search term

	Returns:
		[type]: [description]
	"""

	#add some safe inputs
	url = "https://jisho.org/api/v1/search/words?keyword=" + urllib.parse.quote(e, safe='/&=')

	if verbose:
		print(url)

	response = urllib.request.urlopen(url)

	#returns multiple
	result = json.loads(response.read())

	numResults = len(result['data'])
	if verbose:
		print("Found " + str(numResults) )

	return result

def getAudio(wordKanji, wordKana, saveDir, excludeFile):
	"""Download audio from Jisho.org for word

	Args:
		wordKanji (string): Kanji for the word
		wordKana (string): kana for the word
		saveDir (string): Where to save the audo 
		excludeFile (fie): File for audio to not search for. Contains a single column of all words.mp3 that should not be downloaded. This function does not check this, only appends to it if it fails

	Returns:
		bool: whether word mp3 is saved in directory (not necessarily donwloading if it already exists)
	"""

	if verbose:
		print("Attempting to download "+wordKanji)

	baseUrl = "https://jisho.org/search/"
	#search using both kanji and kana to ensure first result is desired
	search = baseUrl + urllib.parse.quote(wordKanji) + "%20" + urllib.parse.quote(wordKana)

	#get url page into a useable format
	page = urllib.request.urlopen(search).read()
	soup = BeautifulSoup(page, features="lxml")
	audiotag = soup.find("audio")
	#ensure it is of the first result
	if(audiotag) and (audiotag.find_parent("div", {"class": "exact_block"})):
		audioUrl = audiotag.find("source").get("src") #assume audio would be first, if present
		urllib.request.urlretrieve("http:"+audioUrl, saveDir+wordKanji+".mp3") #source in webopage lacks "http:" prefix
		return True
	else:
		# Note word as failed- so can speed up next time by not checking
		with open(excludeFile, 'a', encoding='utf-8') as f:
			f.write(wordKanji+".mp3\n")
		return False
# vectorize the function
vgetAudio = np.vectorize(getAudio)

def makeFurigana(kanjiIn, kanaIn):
	"""Generate a furigana word from associated kanji and kana. Is able to handle words with kana between the kanji.
	
	E.g. (掃除する, そうじする) becomes　掃除[そうじ]する

	Args:
		kanjiIn (string): Kanji of the word (can include kana as well).
		kanaIn (string): Kana of the word

	Returns:
		string: Kanji word with furigana
	"""

	#No value provided
	if not kanaIn:
		return
	#what to put the furigana inside
	f_l = '['
	f_r = ']'


	#keep track of extra character spaces that are 'eaten' by kanjis
	tt = 0
	#furigana-kanji lists
	outWord = ""
	lastMatchLoc = 0
	fk = []
	#for each kanji in the word
	for m in re.finditer("[一-龯々]+", kanjiIn):
		kanjiWordPos = m.span()[0]
		kanaWordPos = kanjiWordPos + tt

		#find the next furigana(s) in the kanji word
		searchLoc = m.span()[1]
		m2 = re.search(r"[ぁ-ん]+", kanjiIn[searchLoc:])
		if(m2):
			#find this kana match in the kana word
			searchLoc = searchLoc + tt
			m3 = re.search(m2.group(), kanaIn[searchLoc:])
			#if no matching found, assume something wrong with the input
			if not m3:
				return ""

			#get the kana between these
			s = kanaIn[kanaWordPos:searchLoc+m3.span()[0]]

			#update number of kanas 'eaten' by kanjis
			tt = tt + m3.span()[0]

		else:
			s = kanaIn[kanaWordPos:]

		#the furigana'd kanji string, separated by space
		out = " " + m.group() + f_l + s + f_r
		outWord = outWord + kanjiIn[lastMatchLoc:kanjiWordPos] + out
		fk.append(out)

		#update position of last kanji searched
		lastMatchLoc = m.span()[1]

	#update the out word for tailing kanas
	outWord = outWord + kanjiIn[lastMatchLoc:]
	return outWord
# vectorize the function
vmakeFurigana = np.vectorize(makeFurigana)


def getAllOfGroup(group, fileName=""):
	"""SLOW OPERATION. Download all the words for a `group` from Jisho and save into a json file.

	Args:
		group (string): Jisho Category to search for (e.g. N3) or tag (e.g. #common (note # for tag searches))
		fileName (string, optional): filename output to save json data. Defaults to "$(group).json"
	"""

	if fileName == "":
		fileName = group + ".json"

	#number of results returned from JSON query for a page
	numResults = 1
	#keep track of pages of results
	pageCounter = 1

	#Big JSON storage file
	allJSResults = {}

	#Jisho has a limit of 20 results per page/return, so run for multiple pages until no more results
	while (True):
		JSONResults = getJapJs(group+"&page="+str(pageCounter))
		numResults = len(JSONResults['data'])

		#jisho.org currently has a limit of 1000 pages
		if(numResults == 0 or pageCounter > 999):
			break


		#extract the inner, useful JSON word data
		if(allJSResults == {}):
			allJSResults = {"data": JSONResults['data']}
		else:
			allJSResults = {"data": allJSResults['data'] + JSONResults['data']}

		#increment page counter
		pageCounter = pageCounter + 1

	if verbose:
		print("Found " + str(pageCounter - 1) + " pages ")

	#Write to a file
	with open(fileName, 'w', encoding='utf-8') as jf:
		json.dump(allJSResults, jf, indent=3, ensure_ascii=False)

def convertJSONtoTable(inFileName, outCsv, cardType):
	"""Convert downloaded Jisho json file of vocabulary into a csv file suitable for import into Anki

	Args:
		inFileName (string): json file name for input
		outCsv (string): csv file name for output
		cardType (string [normal/extended]): [normal/extended] are the only valid arguments. 
						normal - contains standard vocabulary card columns. 
						extended - as normal, with sound
	"""

	if not( cardType == "normal") and not( cardType == "extended"):
		print("Unknown card type as input")
		return

	pddata = pd.read_json(inFileName, orient='split', encoding='utf-8')
	#tidy up usless columns
	pddata = pddata.drop(columns=['is_common', 'tags', 'attribution'])

	#initialize depending on card type
	cols = ['slug', 'english_definition', 'reading', 'grammar', 'additional', 'jlpt']
	if(cardType == "extended"):
		pddata['sound'] = ''
		cols.insert(5, 'sound')

		audioSaveDir = "audio/"
		
		# set up directory if not present yet
		os.makedirs(audioSaveDir, exist_ok=True)

		excludeFileLoc = audioSaveDir + 'notAvailable.txt'
		#make a list of all audio files that exists
		audios = os.listdir(audioSaveDir)
		#list of audio files that do not exist to be downloaded - so dont attempt to download these
		audiosDontDown = [line.rstrip('\n') for line in open(excludeFileLoc, 'w+', encoding='utf-8')]
		if verbose:
			print("Downloading any missing audio")

	#add new columns
	pddata['english_definition'] = ''
	pddata['grammar'] = ''
	pddata['reading'] = ''
	pddata['additional'] = ''


	startI = time.time()
	# create data of same number of rows, and desired output of columns
	outData = pd.DataFrame(index=np.arange(len(pddata.index)),columns=cols)
	#get main word data
	outData['english_definition'] = pddata['senses'].apply(lambda x : ", ".join(x[0]['english_definitions']))
	outData['grammar'] = pddata['senses'].apply(lambda x : ", ".join(x[0]['parts_of_speech']))
	#Get rid of x-1 issues - sometimes words have -1 appended at the end
	outData['slug'] = pddata['slug'].apply(lambda x : x[:re.search("-\d$", x).span()[0]] if re.search("-\d$", x) else x )
	#be sure to use the tidied-up slug data
	outData['reading'] =vmakeFurigana(outData['slug'], pddata['japanese'].str[0].str['reading'])
	#jlpt level - joined sorted list
	outData['jlpt'] = pddata['jlpt'].apply( lambda x : ' '.join(sorted(x) ))
	#usually kana tag
	outData['jlpt'] += pddata['senses'].apply( lambda x : " usually_kana" if ( "Usually written using kana alone" in x[0]["tags"]) else "")

	for i in range(0, len(pddata.index)):
		if ('reading' in pddata['japanese'][i][0]):
			if (cardType == "extended"):
				audiostr = outData['slug'][i] + ".mp3"
				bSuccess = False # whether sound file now exists
				if audiostr in audios:
					bSuccess = True
				elif (audiostr in audiosDontDown):
					bSuccess = False
				elif getAudio(outData['slug'][i], pddata['japanese'][i][0]['reading'], audioSaveDir, excludeFileLoc):
					bSuccess = True
				else:
					bSuccess = False
				if(bSuccess):
					outData['sound'][i] = "[sound:"+ audiostr + "]" #naming convention for sound in card
		else:
			outData.drop(i)

		#get all the additional english senses
		l = []
		for j in pddata['senses'][i][1:]:
			#skip places and wikipedia entries - they dont seem as good as the others
			if ('Place' in j['parts_of_speech']):
				continue
			elif ('Wikipedia definition' in j['parts_of_speech']):
				continue
			#skip if tag contains 'obsolete term'
			elif ('Obsolete term' in j['tags']):
				continue
			l.append(", ".join(j['english_definitions']))
		#separate different groups by a different separator
		l = "; ".join(l)
		outData['additional'][i] = l
	endI = time.time()
	if verbose:
		print("Opt version time " + str(endI - startI))
	outData.to_csv(outCsv, encoding='utf-8', index=False, header=False)

def	download_and_generate(N, normal):
	"""Download vocabulary from Jisho for category "N", and generate the "normal" card type. 
	Saves resulting files in the "generated" folder

	Args:
		N (string): JLPT grade of #tag to search Jisho for
		normal (string [normal/extended]): [normal/extended] are the only valid arguments.
						normal - contains standard vocabulary card columns. 
						extended - as normal, with sound
	"""

	# Create the generated folder if not present
	os.makedirs(folder_name, exist_ok=True)

	# See if the Jisho vocabulary file is already downloaded
	json_file = os.path.join(folder_name, N + normal + ".json")
	if not os.path.isfile(json_file):
		getAllOfGroup(N, json_file)

	# Convert jisho json to anki-ready csv
	if verbose:
		print("----------\nConverting " + N)
	csv_file = os.path.join(folder_name, N + normal + ".csv")
	convertJSONtoTable(json_file, csv_file, normal)

def parse_args(argv=None):
	parser = argparse.ArgumentParser(description="Download JLPT N5-N1 and common vocabulary from Jisho and output anki-ready csv decks")
	parser.add_argument('-v', '--verbose', action='store_true', help='Print more verbose statements')
	parser.add_argument('-t', '--type', choices=["normal", "extended"], default='normal', help='type of card to generate')
	args = parser.parse_args(argv)
	global verbose 
	verbose = args.verbose
	return args

if __name__ == "__main__":
	args = parse_args()

	# Which JLPT grades to get (any combination of N5, N4, N3, N2, N1 and #common)
	JLPT_Grades = ["N5", "N4", "N3", "N2", "N1", "#common"]

	for N in JLPT_Grades:
		download_and_generate(N, args.type)
