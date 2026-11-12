# Branch A, frame 0, rebuild v3. Every coordinate here is a hand design decision (no image was sampled).
import json


def mir(pts):
    return [[75 - x, y] for x, y in pts]


def P(*pts):
    return {"type": "polygon", "points": [list(p) for p in pts]}


def OR(*r):
    return {"type": "or", "of": list(r)}


def poly(layer, color, pts, frame=0):
    return {"op": "polygon", "args": {"layer": layer, "frame": frame, "color": color, "filled": True, "points": [list(p) for p in pts]}}


def shift(layer, d, region, ramp=None, frame=0):
    a = {"layer": layer, "frame": frame, "direction": d, "region": region}
    if ramp:
        a["ramp"] = ramp
    return {"op": "shift_ramp", "args": a}


def rows(layer, x, y, r, legend, only_on=None, skip=True, frame=0):
    a = {"layer": layer, "frame": frame, "x": x, "y": y, "format": "sym", "skip_transparent": skip, "legend": legend, "rows": r}
    if only_on:
        a["mask"] = {"only_on": only_on}
    return {"op": "draw_rows", "args": a}


def line(layer, pts, color, only_on=None, frame=0):
    a = {"layer": layer, "frame": frame, "points": [list(p) for p in pts], "color": color, "brush": {"size": 1, "shape": "square"}}
    if only_on:
        a["mask"] = {"only_on": only_on}
    return {"op": "stroke", "args": a}


PARTS = ["tail", "frond", "legs", "torso", "arms", "collar", "fern", "head"]
EX = ["@plum0", "@leaf0", "@belly0", "@amber0", "@line"]

head = [(26, 15), (49, 15), (53, 16), (55, 17), (56, 18), (57, 20), (58, 23), (58, 26), (59, 27), (59, 35), (58, 37), (56, 39), (54, 40), (50, 41),
        (25, 41), (21, 40), (19, 39), (17, 37), (16, 35), (16, 27), (17, 26), (17, 23), (18, 20), (19, 18), (20, 17), (22, 16)]
torso = [(27, 42), (48, 42), (51, 46), (52, 52), (53, 58), (52, 63), (49, 67), (26, 67), (23, 63), (22, 58), (23, 52), (24, 46)]
belly = [(29, 45), (46, 45), (48, 50), (49, 56), (48, 62), (45, 66), (30, 66), (27, 62), (26, 56), (27, 50)]
legL = [(19, 61), (33, 61), (35, 64), (34, 69), (33, 72), (33, 76), (14, 76), (14, 73), (17, 70), (18, 65)]
armL = [(25, 46), (21, 47), (18, 50), (16, 54), (15, 58), (15, 62), (17, 64), (21, 64), (23, 62), (24, 58), (25, 53)]
leafL = [(32, 40), (26, 40), (20, 42), (15, 45), (12, 49), (18, 49), (24, 50), (29, 48), (33, 45)]
leafC = [(27, 41), (48, 41), (47, 46), (43, 50), (38, 55), (37, 55), (32, 50), (28, 46)]
tail = [(50, 64), (55, 66), (60, 66), (63, 64), (64, 61), (67, 61), (67, 66), (64, 70), (58, 73), (52, 72), (49, 70)]
fernL = [(30, 16), (30, 10), (30, 6), (28, 3), (25, 2), (22, 3), (20, 5), (19, 8), (20, 11), (22, 12), (25, 12), (27, 10), (27, 7), (25, 6), (23, 7), (23, 9)]
frond = ["......m......",
         ".....mmm.....",
         "..ee..m..ee..",
         ".hhee.m.heee.",
         "..eeee.eeee..",
         "......m......",
         ".hh...m...ee.",
         "hhee..m..eeee",
         ".eeee.m.eeee.",
         "...eee.eee...",
         "......m......",
         "......m......"]


def build():
    T = {}
    T["12_rebuild_clear"] = ("rebuild v3: clear part layers (face kept)",
        [{"op": "update_layer", "args": {"layer": "frond", "position": {"above": "tail"}}}] +
        [{"op": "clear_cel", "args": {"layer": l, "frame": 0}} for l in PARTS if l != "frond"])
    T["13_block_v3"] = ("blocking v3: rounder head top, legs with a clear gap and outward feet, frond on its own layer",
        [poly("head", "@plum2", head), poly("torso", "@plum2", torso), poly("torso", "@belly1", belly),
         poly("legs", "@plum2", legL), poly("legs", "@plum2", mir(legL)), poly("arms", "@plum2", armL), poly("arms", "@plum2", mir(armL)),
         poly("collar", "@leaf2", leafL), poly("collar", "@leaf2", mir(leafL)), poly("collar", "@leaf2", leafC),
         poly("tail", "@plum2", tail),
         rows("frond", 59, 50, frond, {"m": "@leaf1", "e": "@leaf2", "h": "@leaf3"}),
         {"op": "stroke", "args": {"layer": "fern", "frame": 0, "color": "@leaf2", "brush": {"size": 2, "shape": "square"}, "points": fernL}},
         {"op": "stroke", "args": {"layer": "fern", "frame": 0, "color": "@leaf2", "brush": {"size": 2, "shape": "square"}, "points": mir(fernL)}}])
    T["14_head_shading"] = ("head: lit top plane, cheek underside and right side turn away, occlusion on the collar, lower lids",
        [shift("head", "lighter", P((15, 14), (56, 14), (54, 16), (45, 17), (31, 17), (23, 18), (18, 20), (15, 22))),
         shift("head", "darker", OR(P((14, 35), (21, 37), (29, 38), (46, 38), (54, 36), (61, 31), (61, 44), (14, 44)),
                                    P((56, 19), (61, 19), (61, 31), (56, 33)))),
         shift("head", "darker", P((21, 40), (55, 40), (52, 42), (24, 42))),
         rows("head", 21, 32, ["..dddddddd..", "....dddd...."], {"d": "@plum1"}, ["@plum2"]),
         rows("head", 45, 32, ["..dddddddd..", "....dddd...."], {"d": "@plum1"}, ["@plum2"])])
    T["15_collar_shading"] = ("collar: 2-3 px cast shadow of the head, midrib fold, right leaf turned away, lit left edge, veins",
        [shift("collar", "darker", OR(P((10, 40), (64, 40), (64, 44), (46, 43), (30, 43), (10, 43)),
                                      P((38, 43), (49, 42), (49, 47), (38, 57)),
                                      P((47, 46), (64, 45), (64, 51), (48, 51)))),
         line("collar", [(13, 48), (17, 46), (21, 44)], "@leaf3", ["@leaf2"]),
         line("collar", [(28, 45), (31, 46)], "@leaf3", ["@leaf2"]),
         line("collar", [(37, 44), (37, 53)], "@leaf1", ["@leaf2"]),
         line("collar", [(29, 45), (17, 48)], "@leaf1", ["@leaf2"]),
         line("collar", [(46, 45), (58, 48)], "@leaf0", ["@leaf1", "@leaf2"])])
    T["16_torso_shading"] = ("torso: collar cast shadow on the belly top, belly turns away on the right, three soft segments, right side in shade",
        [shift("torso", "darker", OR(P((25, 44), (50, 44), (50, 47), (44, 48), (40, 51), (37, 56), (34, 51), (30, 48), (25, 48)),
                                     P((45, 48), (50, 48), (50, 67), (44, 67)), P((26, 64), (49, 64), (49, 68), (26, 68))), "belly"),
         shift("torso", "darker", OR(P((47, 42), (55, 42), (55, 68), (49, 68)), P((21, 63), (55, 63), (55, 68), (21, 68))), "plum"),
         line("torso", [(28, 53), (30, 54), (45, 54), (47, 53)], "@belly0", ["@belly1"]),
         line("torso", [(28, 59), (30, 60), (45, 60), (47, 59)], "@belly0", ["@belly1"])])
    T["17_arms_shading"] = ("arms: shoulders under the collar, inner side in shade, lit outer edge on the left arm, three fingers",
        [shift("arms", "darker", OR(P((14, 44), (27, 44), (27, 50), (14, 50)), P((48, 44), (61, 44), (61, 50), (48, 50)),
                                    P((21, 50), (26, 50), (26, 65), (21, 65)), P((54, 50), (61, 50), (61, 65), (55, 65)))),
         shift("arms", "lighter", P((15, 52), (18, 50), (19, 51), (17, 58), (15, 60))),
         rows("arms", 15, 61, ["..o.o..", "..o.o..", "..o.o.."], {"o": "@plum0"}, ["@plum2", "@plum1", "@plum3"]),
         rows("arms", 53, 61, ["..o.o..", "..o.o..", "..o.o.."], {"o": "@plum0"}, ["@plum2", "@plum1", "@plum3"])])
    T["18_legs_shading"] = ("legs: occlusion under the torso, inner thighs in shade, toes, lit left thigh",
        [shift("legs", "darker", OR(P((12, 66), (63, 66), (63, 69), (12, 69)), P((30, 60), (36, 60), (36, 77), (30, 77)),
                                    P((53, 60), (63, 60), (63, 77), (53, 77)))),
         shift("legs", "darker", P((30, 66), (45, 66), (45, 69), (30, 69))),
         shift("legs", "lighter", P((16, 70), (20, 69), (21, 71), (17, 73))),
         rows("legs", 14, 73, ["....o..o..o.......", "....o..o..o......."], {"o": "@plum0"}, ["@plum2", "@plum1", "@plum3"]),
         rows("legs", 43, 73, [".......o..o..o....", ".......o..o..o...."], {"o": "@plum0"}, ["@plum2", "@plum1", "@plum3"])])
    T["19_tail_shading"] = ("tail: underside in shade, darkest where it passes behind the right leg",
        [shift("tail", "darker", OR(P((48, 69), (60, 68), (66, 64), (69, 64), (69, 75), (48, 75)), P((48, 62), (56, 62), (56, 75), (48, 75))), "plum"),
         shift("tail", "darker", P((48, 62), (55, 62), (55, 75), (48, 75)), "plum")])
    T["20_fern_shading"] = ("fern: lit top-left of each coil, shaded stems",
        [shift("fern", "lighter", OR(P((17, 0), (29, 0), (27, 3), (22, 4), (19, 8), (17, 9)), P((43, 0), (55, 0), (53, 3), (48, 4), (46, 8), (44, 10)))),
         shift("fern", "darker", OR(P((31, 6), (33, 6), (33, 17), (31, 17)), P((46, 6), (48, 6), (48, 17), (46, 17)), P((53, 5), (58, 5), (58, 14), (50, 14))))])
    T["21_outline"] = ("outline: selective (material darkest) outside each part; exclude_colors makes reruns no-ops",
        [{"op": "outline", "args": {"layer": l, "frame": 0, "color": "@plum0", "placement": "outside", "selective": True, "connectivity": 4, "exclude_colors": EX}} for l in PARTS])
    return T


if __name__ == "__main__":
    T = build()
    for k, (label, ops) in T.items():
        json.dump({"label": label, "ops": ops}, open(f"tx/{k}.json", "w"))
    print(" ".join(T))
