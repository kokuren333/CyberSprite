import json
rows = [
".....1111......",
"....1abbb11....",
"...1aabbbba1...",
"..1aaaaaaaaa1..",
"..1aaaaaaaaaaa1",
"..1eee7777771..",
"..1ee88888181..",
"..1ee87888888 1".replace(" ",""),
"...1e78888881..",
"....1778881....",
"...14557751....",
"...14555561....",
"...14555561....",
"...14555561....",
"...14455561....",
"...14455551....",
"...12222221....",
"...13333331....",
]
rows=[r.ljust(15,'.') for r in rows]
for r in rows: print(r, len(r))
t={"label":"body f0: head and torso at base height","ops":[{"op":"draw_rows","args":{"layer":"body","frame":0,"x":9,"y":3,"rows":rows,"format":"sym"}}]}
json.dump(t,open("work/t02_body.json","w"))
