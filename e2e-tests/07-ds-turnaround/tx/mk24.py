import json, sys
sys.path.insert(0, "tx")
from build_a_v3 import rows
ops = [
  {"op":"set_pixels","args":{"layer":"face","frame":0,"pixels":[[28,27,"@lilac"],[52,27,"@lilac"]]}},
  rows("arms",15,60,["..h.h.h"],{"h":"@plum3"},["@plum2","@plum1"]),
  rows("arms",53,60,["h.h.h.."],{"h":"@plum3"},["@plum2","@plum1"]),
  rows("legs",14,72,["..h..h..h.........."],{"h":"@plum3"},["@plum2","@plum1"]),
  rows("legs",43,72,["........h..h..h...."],{"h":"@plum3"},["@plum2","@plum1"]),
  rows("collar",12,47,["hh.","..h"],{"h":"@leaf3"},["@leaf2"]),
]
json.dump({"label":"finish: eye sparkle, knuckle and toe highlights, lit leaf tip","ops":ops},open("tx/24_finish.json","w"))
