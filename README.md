# JLPT-N5-N1-Japanese-Vocabulary-Anki

Generate a csv file suitable for importing into [Anki](https://apps.ankiweb.net/) by searching [Jisho.org](https://jisho.org/) for JLPT Tags (N5, N3, e.t.c.).

This was used to create the decks [JLPT-N5-N1 Japanese Vocabulary](https://ankiweb.net/shared/info/1550984460) and [JLPT-N5-N1 Japanese Vocabulary Extended Notes](https://ankiweb.net/shared/info/336300824)

The "extended" deck contains everything of the normal deck as well as audio pronunciation for some words.

Following this readme will provide exactly the deck available on Anki (linked above). Unless you wish to make modifications to the deck and code, it is far easier to download the deck using the links above.

## How to Generate Files

Ensure Python Version 3.X is installed. I would suggest also having pipenv installed (`pip install pipenv`). Then run `pipenv shell` in this folder, then `python createJLPTDeck.py`. Resulting files will be created in the "generated" folder.

### Suggested run arguments

`python createJLPTDeck.py -v` will download and create all JLPT decks and common word deck. The `-v` argument is useful to track process of the script, as it takes a while to complete.

`python createJLPTDeck.py -v --type extended` will create all JLPT decks and common word deck with some words containing audio. This method is a lot slower due to needing to download many more files.

## Importing Into Anki

After running the script, as described above, there should now be a `generated` folder, and optionally a `audio` folder if the `--type extended` argument was used. Each csv file can be imported into Anki to create its own deck. 

However, the decks can be combined together into a more complete master deck.

### Creating a master heirachy deck

The increasing vocabulary structure of JLPT lends itself well to a simple heirarchy:

- common
	- JLPT N1
		- JLPT N2
			- JLPT N3
				- JLPT N4
					- JLPT N5

To achieve this in Anki start by creating an empty deck of the above form. The quickest way to do this is create a new deck called "Japanes Vocabulary::N1::N2...::N5". The "::" in Anki means subdeck.

Within Anki you should have a card type suitable for this deck. See "Note Structure" below for the suggested layout. Ensure there is a note type suitable before importing the decks. This note type should be selected during the import process.

- Import into each deck the appropriate .csv file that was generated.
- Import the common.csv file into the outmost/root deck
- Import with "import even if existing note has same first field" setting in anki.

The result should be a fully populated deck of the above structure.

## Note Structure

Current anki deck should contain the following elements:
- "Expression" - the word/expression in japanese with only kanji if relevant
- "English definition" - the main english meaning, translated
- "Reading" - similar to "expression", but with kanji expanded with ruby-ready furigana addition
- "Grammar" - the grammatical type
- "Additional definitions" - other english meanings
- ("Sound" - audio track of the deck. Optional, only used for `extended` deck type)
- "jlpt" - the anki-tags, ordered by JLPT. These should be imported as the `tag` field.

