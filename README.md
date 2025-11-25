# JLPT N5 to N1 Japanese Vocabulary Flashcard Deck for Anki

For learning japanese vocabulary in accordance with the official Japanese Language Proficiency Tests (JLPT), using flashcards and spaced repetition with the [Anki](https://apps.ankiweb.net/) software.

This is prefaced that there is no official JLPT vocabulary list anymore, not since the reformation of the exam structure around 2010.

This repository generates a `.csv` or `.apkg` file suitable for importing into [Anki](https://apps.ankiweb.net/) by searching [Jisho.org](https://jisho.org/) for JLPT Tags (N5, N3, e.t.c.),

This was used to create the decks [JLPT-N5-N1 Japanese Vocabulary](https://ankiweb.net/shared/info/1550984460) and [JLPT-N5-N1 Japanese Vocabulary Extended Notes](https://ankiweb.net/shared/info/336300824)

The "extended" deck contains everything of the normal deck as well as audio pronunciation for some words.

Following this readme will provide exactly the deck available on Anki (linked above). Unless you wish to make modifications to the deck and code, it is far easier to download the deck using the links above.

![An anki card](example_images/example_anki.png)

## How to Generate Files

Ensure Python Version 3.X is installed. I would suggest also having pipenv installed (`pip install pipenv`). Then run `pipenv shell` in this folder, then `python createJLPTDeck.py`. Resulting files will be created in the `output` folder.

An issue with this deck's approach is that the words returned from querying anki for #jlpt-n1 are not consistent. Different calls to the same page can return different results. Creating a more consistent 

### Suggested run arguments

`python createJLPTDeck.py -v` will download and create all JLPT decks and common word deck. The `-v` argument is useful to track process of the script, as it takes a while to complete.

`python createJLPTDeck.py -v --type extended` will create all JLPT decks and common word deck with some words containing audio. This method is a lot slower due to needing to download many more files.

`python createAnkiDeck.py -v` will create various `.apkg` files ready for import. These files can be imported directly into Anki without constructing decks or models beforehand. If running this command then the remainder of this file can be skipped as the deck will be set up correctly.

## Importing Into Anki using a .apkg
Running `createAnkiDeck.py` results in a .apkg file being generated in the `output` folder. The apkg file is an anki-specific format that contains all the deck and flashcard information already baked in. Import the file into Anki according to the instructions for your client. Usually something like an "import file" button. Done! :)

## Importing Into Anki using a csv

After running the script, as described above, there should now be a `output` folder, and optionally a `audio` folder if the `--type extended` argument was used with a csv for each deck. Each csv file can be imported into Anki to create its own deck. 

However, the decks can be combined together into a more complete master deck.

### Creating a master heirachy deck

The increasing vocabulary structure of JLPT lends itself well to a simple heirarchy:

- common
	- JLPT N1
		- JLPT N2
			- JLPT N3
				- JLPT N4
					- JLPT N5

To achieve this in Anki start by creating an empty deck of the above form. The quickest way to do this is create a new deck called `Core Japanese Vocabulary::JLPT N1::JLPT N2::JLPT N3::JLPT N4::JLPT N5`. The "::" in Anki means subdeck.

Within Anki you should have a card type suitable for this deck. See "Note Structure" below for the suggested layout. Ensure there is a note type suitable before importing the decks. This note type should be selected during the import process.

- Import into each deck the appropriate .csv file that was generated.
- Import the common.csv file into the outmost/root deck
- Import with "Update existing notes when first field matches" setting in anki.

The result should be a fully populated deck of the above structure. 

N.B. Some cards will be in the incorrect JLPT deck. This occurs because the Jisho search does not correctly find all the appropriate cards for each grade. After populating the list in Anki, manually search for cards by tag (e.g. `tag:jlpt-n1`) and move them to the appropriate deck. Advice would be to start with N1 and move down to N5, so that the N5 tag has priority in placement for the card.

### Card layout

The deck can function well with 2 card types, "recognition" and "recall". Recognition checks the Japanese, while recall tests the english and being able to provide the Japanese in response.

To set up the cards with suggested html and css view the `card_style` folder, which contains 5 files for front, back, and card style. Adjust front and back to ask and test desired fields for the appropriate cards.

## Note Structure

Current anki deck should contain the following elements:
- "Expression" - the word/expression in japanese with only kanji if relevant
- "English definition" - the main english meaning, translated
- "Reading" - similar to "expression", but with kanji expanded with ruby-ready furigana addition
- "Grammar" - the grammatical type
- "Additional definitions" - other english meanings
- ("Sound" - audio track of the deck. Optional, only used for `extended` deck type)
- "jlpt" - the anki-tags, ordered by JLPT. These should be imported as the `tag` field. Also includes formality - if the word has use in humble, formal (e.t.c.) language
