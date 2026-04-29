# Regarding the Data

## Data sources

JLPT resources are primarily found from [Jonathan Waller‘s JLPT list](https://www.tanos.co.uk/jlpt/). This resource is used for the online dictionary [Jisho](https://jisho.org) as well as derivatives such as [JLPT Sensei](https://jlptsensei.com/).

Japanese vocabulary information is gathered from the [JMDict, Japanese dictionary database](https://www.edrdg.org/jmwsgi/srchformq.py?svc=jmdict), a really good machine-friendly resoruce with a community helping to keep it up to date and evolving. The database is available for download. In particular, I use the unofficial json-formatted version https://github.com/scriptin/jmdict-simplified as I find json easier to parse myself. If you want to use a more up-to-date version of the dictionary. Download the json version you want from their releases, and point the `jmdict extract` function to the zip for it to use instead of the provided one.

Audio is obtained courtesy of [Kanji Alive](https://kanjialive.com/) under a [Creative Commons Attribution 4.0 International License](http://creativecommons.org/licenses/by/4.0/). It uses their human audio samples.

## Information about the generated package

### The `.apkg` deck structure

The increasing vocabulary structure of JLPT lends itself well to a simple heirarchy:

- JLPT N1 (3053 cards)
	- JLPT N2 (1737 cards)
		- JLPT N3 (1647 cards)
			- JLPT N4 (630 cards)
				- JLPT N5 (667 cards)

With N5 as the easiest, and N1 being the hardest. This structure means every grade below it is also included in the review list. So studying N3 also includes the vocabulary studied for N4 and N5.

To achieve this in Anki start by creating an empty deck of the above form. The quickest way to do this is create a new deck called `Core Japanese Vocabulary::JLPT N2::JLPT N3::JLPT N4::JLPT N5`. The "::" in Anki means subdeck.

### Card layout

By default each vocabular word has two cards in the deck, "recognition" and "recall". Recognition provides the Japanese and asks for the English, while recall shows the English and asks for the equivalent Japanese word. I personally find recall useful for the initial stages of study, but becomes less relevant for the higher grades. Check out online resources for information if you don't want to study one of the two types of card.

The appearance of the flashcards is controled by the `card_style` folder, which contains `html` and `css` styling. These control what fields are displayed where, and how they should appear.

I've created a custom furigana-toggle style which hides and shows the furigana of the word when click/tapped. Furigana is the helpful hiragana shown in small above kanji to explain how to pronounce the word. Feel free to take this .css file for your own uses.

### Note Structure

Each flashcard in the deck contains the following elements:

| Field | Explanation |
| --- | --- |
|"Expression" | The word/expression in japanese with only kanji if relevant
| "English definition" | The main english meaning, translated
| "Reading" | Similar to "expression", but with kanji expanded with ruby-ready furigana addition
| "Grammar" | The grammatical usage of the word |
| "Additional definitions" | Other english meanings
| ("Sound") | (Optional: audio pronunciation of the word. Only used for `extended` deck type) |
| "tags" | See the table below. Includes JLPT grade, formality, and other relevant grouping to easily manipulate multiple cards. |


### The card tags

Each card/vocabulary-word has various possible tags.

| Tag category | Tag on card | Explanation |
|---|---|---|
|JLPT level | N5, N3, etc | The difficulty grade. Only one. Always included. |
|Formality | Polite, Humble, Honourific | If the word is used in a particular form of japanese speech. |
| Usually kana | usually_kana | Word is usually seen in kana form, though a kanji form does exist. |

