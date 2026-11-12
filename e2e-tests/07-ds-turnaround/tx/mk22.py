import json, sys
sys.path.insert(0, "tx")
from build_a_v3 import poly, line, shift, P, EX
leaf = [(64,63),(62,61),(60,60),(61,58),(59,56),(60,54),(61,52),(63,50),(65,48),(66,47),(68,49),(70,52),(69,54),(71,56),(70,58),(68,60),(66,62),(65,63)]
ops = [{"op":"clear_cel","args":{"layer":"frond","frame":0}},
       poly("frond","@leaf2",leaf),
       shift("frond","darker",P((66,46),(73,46),(73,64),(66,64))),
       shift("frond","lighter",P((58,52),(62,49),(64,48),(64,56),(60,58))),
       line("frond",[(65,62),(65,55),(66,49)],"@leaf1",["@leaf2","@leaf3"]),
       line("frond",[(65,58),(62,56)],"@leaf1",["@leaf3","@leaf2"]),
       line("frond",[(66,57),(69,55)],"@leaf0",["@leaf1"]),
       {"op":"outline","args":{"layer":"frond","frame":0,"color":"@leaf0","placement":"outside","selective":True,"connectivity":4,"exclude_colors":EX}}]
json.dump({"label":"frond: serrated leaf with midrib, lit left half, shaded right half","ops":ops},open("tx/22_frond.json","w"))
