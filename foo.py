import json
import pandas as pd
from jamdict import Jamdict
jam = Jamdict()

# use wildcard matching to find anything starts with 食べ and ends with る
result = jam.lookup('揚げる')
# result = jam.lookup('id#2859161')

# print all word entries
for entry in result.entries:
     print(entry)


with open("original_data/jmdict-eng-3.6.1.json", "r") as f:
    data = json.load(f)

jmdict = pd.DataFrame(data["words"])
jmdict["id"] = jmdict["id"].astype(int)

entry = jmdict[jmdict["id"] == 2864817]
if len(entry) < 1:
     print(f"Not found {2864817}")