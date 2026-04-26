""" For creating Anki packages, formatted in a way useful for JLPT studies. Includes methods for manipulating and enhancing the anki packages and decks.

Creates an anki package (group of decks) in the nested structure common::N1::N2...::N5. I.e. N5 is a subdeck of N4, which is a subdeck of N3...
"""

import random
import re
import math
from pathlib import Path
from typing import Literal
import logging

import pandas as pd
import genanki

#############
## Anki Models

"""The core anki model (card layout, expected entries, and flashcard appearance). """
model_core = genanki.Model(
	## ID of the deck. Generated from random.randrange(1 << 30, 1 << 31), a fixed number for each model.
	## Keep it this value so that importing the deck has the same ID as the previous, and anki correctly knows this is the deck to update regarding
	2125329068, 
	"Core Japanese Vocabulary",
	fields=[
		{"name": "Expression"},
		{"name": "English definition"},
		{"name": "Reading"},
		{"name": "Grammar"},
		{"name": "Additional definitions"},
	],
	templates=[
		{
			"name": "Recognition",
			"qfmt": open("card_style/recognition_front.html", "r").read(),
			"afmt": open("card_style/recognition_back.html", "r").read(),
		},
		{
			"name": "Recall",
			"qfmt": open("card_style/recall_front.html", "r").read(),
			"afmt": open("card_style/recall_back.html", "r").read(),
		},
	],
	css=open("card_style/style.css", "r").read(),
)

""" Alternative version for including audio. Includes extra field and different templates. """
model_audio = genanki.Model(
	1291263575, ## Deck ID, see above
	"Core Japanese Vocabulary Extended",
	fields=[
		{"name": "Expression"},
		{"name": "English definition"},
		{"name": "Reading"},
		{"name": "Grammar"},
		{"name": "Additional definitions"},
		{"name": "Sound"},
	],
	templates=[
		{
			"name": "Recognition",
			"qfmt": open("card_style/recognition_front.html", "r").read(),
			"afmt": open("card_style/recognition_back_sound.html", "r").read(),
		},
		{
			"name": "Recall",
			"qfmt": open("card_style/recall_front.html", "r").read(),
			"afmt": open("card_style/recall_back_sound.html", "r").read(),
		},
	],
	css=open("card_style/style.css", "r").read(),
)

class AnkiPackage:
	"""JLPT Anki Package, made up of ordered decks."""
	def __init__(self, type: Literal["core", "extended"] = "core") -> None:		# entend the information if using extended (media sound) deck
		"""Initialize according to which type of anki package to create.

		Parameters
		----------
		type : Literal, optional
			The type of package to generate, by default "core"
		"""
		self.deck_ids = DECKIDS[type]
		if type == "core":
			self.audio = False
			self.model = model_core
		else:
			self.audio = True
			self.model = model_audio
			self.audio_paths: list[Path] = []
		
		# keep a record of the notes added to avoid repeats
		self.entries: list[str] = []

		self.init_decks()

	def init_decks(self) -> None:
		""" Create multiple nested decks -> common:N5::N4::N3 etc. """
		self.decks = {}

		# Construct names
		deck_names = []
		deck_layers = [
			{"key": "N1", "label": "Core Japanese Vocabulary Extended" if self.audio else "Core Japanese Vocabulary"},
			{"key": "N2", "label": "JLPT N2"},
			{"key": "N3", "label": "JLPT N3"},
			{"key": "N4", "label": "JLPT N4"},
			{"key": "N5", "label": "JLPT N5"},
		]
	
		# decks = []
		current_name_parts = []
		for layer in deck_layers:
			# For each of these decks, make them nested. E.g. the full deck name for N2 is common::n1::n2
			current_name_parts.append(layer["label"])
			deck_name = "::".join(current_name_parts)

			deck_id = self.deck_ids[layer["key"]]

			deck = genanki.Deck(deck_id, deck_name)
			# decks.append(deck)
			self.decks[layer["key"]] = deck
	
	def get_deck(self, deck_name: str) -> genanki.Deck:
		""" Get the anki deck associated with the deck_name

		Parameters
		----------
		deck_name : str
			name of the deck, using the jlpt grade

		Returns
		-------
		genanki.Deck
			The deck associated with that name
		"""
		try:
			return self.decks[deck_name]
		except KeyError:
			raise ValueError(f"Unknown deck key: {deck_name}")
	
	def add_note(self, note: pd.Series, deck_name: str) -> None:
		""" Create and adds a note to the revelant deck by searching its containing tags.

		Parameters
		----------
		note : pd.Series
			A vocabulary word. Should contain all the expected fields
		deck_name : str
			The name of the deck to insert this card into
		"""
		# Ignore possible repeated entries
		if note["expression"] in self.entries:
			logging.debug(f"Not adding duplicate note {note}")
			return

		deck = self.get_deck(deck_name)
		notes_in_deck = len(deck.notes)

		my_note = genanki.Note(
			model=self.model,
			fields=[
				note["expression"],
				note["english_definition"],
				note["reading"],
				note["grammar"],
				note["additional"],
			],
			tags=note["tags"],
			due=notes_in_deck, # make sure each due card is a different index
		)
		if self.audio:
			# audio path exists, i.e. has a corresponding audio file
			if pd.notna(note["wani_audio_path"]):
				filename = note["wani_audio_path"].name
				note_entry = f"[sound:{filename}]"
				my_note.fields.append(note_entry)

				self.audio_paths.append(note["wani_audio_path"])
			else:
				my_note.fields.append("")

		deck.add_note(my_note)
		self.entries.append(note["expression"])

	def save_to_folder(self, folder_path: Path) -> None:
		""" Create an apkg file of the combined info.

		The filename itself is specified according to its type.

		Parameters
		----------
		folder_path : Path
			Folder to save .apkg file
		"""
		# package the decks together
		p_name = "Core Japanese Vocabulary Extended" if self.audio else "Core Japanese Vocabulary"
		
		filename = Path(folder_path, f"{p_name}.apkg")
		logging.info(f"Saving anki package to {filename}")
		package = genanki.Package(list(self.decks.values()))
		if self.audio:
			package.media_files = self.audio_paths
		package.write_to_file(filename)
	
	def get_cards_in_deck(self) -> dict[str, int]:
		""" Get the number of notes/vocab-words within the decks

		Returns
		-------
		dict[str, int]
			How many notes for each deck name
		"""
		return {d.name: len(d.notes) for d in self.decks.values()}



# Deck IDs
## ID of the deck. Generated from random.randrange(1 << 30, 1 << 31), a fixed number for each model.
## Keep it this value so that importing the deck has the same ID as the previous, and anki correctly knows this is the deck to update during import/upgrading
DECKIDS = {
	"extended": {
		"N5": 1573200341,
		"N4": 2011510961,
		"N3": 1098277003,
		"N2": 2037072551,
		"N1": 1451620590,
		"common": 1975199481,
	},
	"core": {
		"N5": 2024894500,
		"N4": 1952964240,
		"N3": 2091691710,
		"N2": 1335245950,
		"N1": 1088576386,
		"common": 1882435851,
	}
 }