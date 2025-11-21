import random
import re
import math

import genanki

from createJLPTDeck import download_and_generate, parse_args

"""
Creates a structured dataframe table and converts it into an Anki deck data structure. Ready for import into Anki as an apkg file.

Creates an anki package (group of decks) in the nested structure common::N1::N2...::N5. I.e. N5 is a subdeck of N4, which is a subdeck of N3...
"""


class AnkiDeck:
	model = genanki.Model(
		random.randrange(1 << 30, 1 << 31),
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

	# keep a record of the notes added to avoid repeats
	entries = []

	# Is this deck the extended type with sound?
	extended = False

	def __init__(self, type):
		# entend the information if using extended (media sound) deck
		if type == "extended":
			self.extended = True
		if self.extended:
			self.model.name = "Core Japanese Vocabulary Extended"
			self.model.fields.append({"name": "Sound"})
			self.model.templates[0][
				"afmt"
			] += "\n\n{{Sound}}"  # recognition sound on back
			self.model.templates[1]["afmt"] += "\n\n{{Sound}}"  # recall sound on back
		self.gen_decks()

	def gen_decks(self):
		"""
		Create multiple nested decks -> common:N5::N4::N3 etc
		"""
		# Construct names
		deck_names = []
		deck_layer_names = [
			"Core Japanese Vocabulary Extended"
			if self.extended
			else "Core Japanese Vocabulary",
			"JLPT N1",
			"JLPT N2",
			"JLPT N3",
			"JLPT N4",
			"JLPT N5",
		]
		for i, n in enumerate(deck_layer_names):
			deck_name = deck_layer_names[0]
			for j in range(1, i + 1, 1):
				deck_name += f"::{deck_layer_names[j]}"
			deck_names.append(deck_name)

		# Create decks
		decks = []
		for d in deck_names:
			deck = genanki.Deck(random.randrange(1 << 30, 1 << 31), d)
			decks.append(deck)
		self.decks = decks

	def get_deck_from_tag(self, tags):
		"""
		Find the easiest deck from a set of tags.
		
		If a word has the N3 and N5 tag, returns 5. If it only has the `common` tag, returns 0
		"""
		# tags = tags.split()
		possibles = [0]
		for tag in tags:
			found = re.search("[1-5]$", tag)
			if found:
				i = int(found.group())
			else:
				i = 0
			possibles.append(i)
		return max(possibles)

	def add_note(self, note):
		"""
		Create and adds a note to the revelant deck by searching its containing tags
		"""
		# Ignore possible repeated entries
		if note["expression"] in self.entries:
			return
		my_note = genanki.Note(
			model=self.model,
			fields=[
				note["expression"],
				note["english_definition"],
				note["reading"],
				note["grammar"],
				note["additional"],
			],
			# tags=note["jlpt"].split(),
			tags=note["tags"],
			# due=str(note["index"]), # make sure each due card is a different index
		)
		if self.extended:
			my_note.fields.append(note["sound"] if (type(note["sound"]) == str) else "")

		deck_index = self.get_deck_from_tag(note["tags"])
		
		# make sure each due card is a different index
		card_index = len(self.decks[deck_index].notes)
		my_note.due = card_index

		self.decks[deck_index].add_note(my_note)
		self.entries.append(note["expression"])

	def create_files(self):
		"""
		Creates an apkg file of the combined info
		"""
		# package the decks together
		p_name = "Core Japanese Vocabulary Extended" if self.extended else "Core Japanese Vocabulary"
		
		genanki.Package(self.decks).write_to_file(f"{p_name}.apkg")
		# d = self.decks[5]
		# genanki.Package(d).write_to_file("foo.apkg")

# class JlptNote(genanki.Note):
#   @property
#   def guid(self):
#     return genanki.guid_for(self.fields[0], self.fields[1])

if __name__ == "__main__":
	args = parse_args()

	a = AnkiDeck(args.type)

	for N in args.grades:
		df = download_and_generate(N, args.type)
		for index, row in df.iterrows():
			a.add_note(row)

	a.create_files()
