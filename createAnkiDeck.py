import random
import re
import math

import genanki

from createJLPTDeck import download_and_generate, parse_args


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
            self.model.templates[1]["qfmt"] += "\n\n{{Sound}}"  # recall sound on front
        self.gen_decks()

    def get_deck_from_tag(self, tags):
        """
        Find the easiest deck from a set of tags
        """
        tags = tags.split()
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
        if note["slug"] in self.entries:
            return
        my_note = genanki.Note(
            model=self.model,
            fields=[
                note["slug"],
                note["english_definition"],
                note["reading"],
                note["grammar"],
                note["additional"],
            ],
            tags=note["jlpt"].split(),
        )
        if self.extended:
            my_note.fields.append(note["sound"] if (type(note["sound"]) == str) else "")

        self.decks[self.get_deck_from_tag(note["jlpt"])].add_note(my_note)
        self.entries.append(note["slug"])

    def create_files(self):
        """
        Creates an apkg file of the combined info
        """
        for d in self.decks:
            genanki.Package(d).write_to_file(f"generated/{d.name}.apkg")


if __name__ == "__main__":
    args = parse_args()

    a = AnkiDeck(args.type)

    for N in args.grades:
        df = download_and_generate(N, args.type)
        for index, row in df.iterrows():
            a.add_note(row)

    a.create_files()
