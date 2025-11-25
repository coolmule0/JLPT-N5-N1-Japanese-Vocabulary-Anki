"""
Generate a list of ((word, jlpt level) pairs.

This step is needed because Jisho.org has an unreliable API that returns different results on occasion. A stable solution is to have a fixed list within this repo saved which has the words to use. Coming back to the deck to make changes, the list can be queried and added when necessary, but known to have the words desired within.
"""

# search jisho by word - whats returned?

# Archaic definitions to ignore?

# consistent words from anki

#clear install/requirements instructions

#audio

#example sentences


#additional grammar

# Add number of cards per deck in description
# Make the raw csv/.apkg files available for download


import os

import pandas as pd
import pandera.pandas as pa

# Define a function to load all JLPT CSVs from a directory into one DataFrame and save to file
def load_jlpt_csvs(folder_path, output_path):
    dfs = []
    
    for level in ["n5", "n4", "n3", "n2", "n1"]:
        csv_path = os.path.join(folder_path, f"{level}.csv")
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            df["jlpt_level"] = level.upper()
            dfs.append(df)
    
    if dfs:
        merged_df = pd.concat(dfs, ignore_index=True)
        merged_df.to_csv(output_path, index=False)
        return merged_df
    else:
        return None

# Example usage
folder = "/mnt/data/original_data"
output = "/mnt/data/jlpt_merged.csv"

# Create sample directory and example CSVs for demonstration
os.makedirs(folder, exist_ok=True)
sample_data = {
    "ent_seq": [1001, 1002],
    "kanji": ["例", "試験"],
    "kana": ["れい", "しけん"],
}

for level in ["n5", "n4"]:
    pd.DataFrame(sample_data).to_csv(os.path.join(folder, f"{level}.csv"), index=False)

# Run the function
merged_result = load_jlpt_csvs(folder, output)
merged_result
