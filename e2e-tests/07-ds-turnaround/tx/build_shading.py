# Generates the stage-3b shading transactions (authored by hand: every polygon below is a design decision).
import json
def P(*pts): return {"type": "polygon", "points": [list(p) for p in pts]}
def OR(*r): return {"type": "or", "of": list(r)}
def shift(layer, d, region, ramp=None):
    a = {"layer": layer, "frame": 0, "direction": d, "region": region}
    if ramp: a["ramp"] = ramp
    return {"op": "shift_ramp", "args": a}
def rows(layer, x, y, r, legend, only_on=None):
    a = {"layer": layer, "frame": 0, "x": x, "y": y, "format": "sym", "skip_transparent": True, "legend": legend, "rows": r}
    if only_on: a["mask"] = {"only_on": only_on}
    return {"op": "draw_rows", "args": a}
def line(layer, pts, color, only_on=None):
    a = {"layer": layer, "frame": 0, "points": [list(p) for p in pts], "color": color, "brush": {"size": 1, "shape": "square"}}
    if only_on: a["mask"] = {"only_on": only_on}
    return {"op": "stroke", "args": a}
tx = {}
# HEAD: lit flat top plane, front plane base, cheek underside and right side turn away, occlusion where the head sits on the collar.
tx["04_head_shading"] = [
    shift("head", "lighter", P((15, 14), (55, 14), (53, 16), (45, 17), (31, 17), (23, 18), (18, 20), (15, 22))),
    shift("head", "darker", OR(P((14, 35), (21, 37), (29, 38), (46, 38), (54, 36), (61, 31), (61, 44), (14, 44)),
                               P((56, 19), (61, 19), (61, 31), (56, 33)))),
    shift("head", "darker", P((21, 40), (55, 40), (52, 42), (24, 42))),
    # lower lids: a soft plum1 arc under each eye gives the eyes a socket
    rows("head", 21, 32, ["..dddddddd..", "....dddd...."], {"d": "@plum1"}, ["@plum2"]),
    rows("head", 45, 32, ["..dddddddd..", "....dddd...."], {"d": "@plum1"}, ["@plum2"]),
]
# COLLAR: the head casts a band of shadow on the leaves (offset to the right: light from upper left);
# the centre leaf folds along its midrib (right half in shade); veins.
tx["05_collar_shading"] = [
    shift("collar", "darker", OR(P((11, 40), (62, 40), (63, 46), (52, 45), (46, 44), (30, 43), (20, 44), (11, 45)),
                                 P((38, 43), (49, 41), (49, 47), (38, 57)),
                                 P((47, 47), (63, 46), (63, 50), (49, 50)))),
    line("collar", [(37, 44), (37, 53)], "@leaf1", ["@leaf2"]),
    line("collar", [(29, 44), (17, 48)], "@leaf1", ["@leaf2"]),
    line("collar", [(46, 44), (58, 48)], "@leaf0", ["@leaf1", "@leaf2"]),
    rows("collar", 13, 46, ["hhhh....", ".hhhhh.."], {"h": "@leaf3"}, ["@leaf2"]),
    rows("collar", 29, 45, ["hhhh", ".hhh", "..hh"], {"h": "@leaf3"}, ["@leaf2"]),
]
# TORSO + BELLY: collar casts a zigzag shadow on the belly top; belly turns away on the right; three soft segments;
# torso right side in shade; underside between the legs dark.
tx["06_torso_shading"] = [
    shift("torso", "darker", OR(P((25, 44), (50, 44), (50, 47), (44, 48), (40, 51), (37, 56), (34, 51), (30, 48), (25, 48)),
                                P((45, 48), (50, 48), (50, 66), (44, 66)),
                                P((26, 63), (49, 63), (49, 67), (26, 67))), "belly"),
    shift("torso", "darker", OR(P((47, 42), (55, 42), (55, 67), (49, 67)), P((21, 62), (55, 62), (55, 67), (21, 67))), "plum"),
    line("torso", [(28, 53), (30, 54), (45, 54), (47, 53)], "@belly0", ["@belly1"]),
    line("torso", [(28, 59), (30, 60), (45, 60), (47, 59)], "@belly0", ["@belly1"]),
    line("torso", [(31, 55), (36, 55)], "@belly1", ["@belly1"]),
]
# ARMS: collar shades the shoulders, inner side of each arm in shade, lit outer edge on the left arm, three fingers.
tx["07_arms_shading"] = [
    shift("arms", "darker", OR(P((14, 44), (27, 44), (27, 50), (14, 50)), P((48, 44), (61, 44), (61, 50), (48, 50)),
                               P((21, 50), (26, 50), (26, 64), (21, 64)), P((54, 50), (61, 50), (61, 65), (55, 65)))),
    shift("arms", "lighter", P((15, 52), (18, 50), (19, 51), (17, 58), (15, 60))),
    rows("arms", 15, 61, ["..o.o..", "..o.o..", "..o.o.."], {"o": "@plum0"}, ["@plum2", "@plum1", "@plum3"]),
    rows("arms", 53, 61, ["..o.o..", "..o.o..", "..o.o.."], {"o": "@plum0"}, ["@plum2", "@plum1", "@plum3"]),
]
# LEGS: occlusion under the torso, inner thighs in shade, toes, a small lit patch on the left thigh.
tx["08_legs_shading"] = [
    shift("legs", "darker", OR(P((16, 66), (60, 66), (60, 69), (16, 69)), P((31, 60), (37, 60), (37, 77), (31, 77)),
                               P((38, 60), (44, 60), (44, 77), (38, 77)), P((53, 60), (60, 60), (60, 77), (53, 77)))),
    shift("legs", "darker", P((33, 66), (42, 66), (42, 69), (33, 69))),
    shift("legs", "lighter", P((17, 70), (21, 69), (22, 71), (18, 73))),
    rows("legs", 17, 73, ["...o..o..o.....", "...o..o..o....."], {"o": "@plum0"}, ["@plum2", "@plum1", "@plum3"]),
    rows("legs", 43, 73, [".....o..o..o...", ".....o..o..o..."], {"o": "@plum0"}, ["@plum2", "@plum1", "@plum3"]),
]
# TAIL: underside in shade, darkest where it passes behind the right leg; frond midrib and shaded right lobes.
tx["09_tail_shading"] = [
    shift("tail", "darker", OR(P((48, 69), (60, 68), (66, 64), (69, 64), (69, 75), (48, 75)), P((48, 63), (55, 63), (55, 75), (48, 75)), P((66, 51), (73, 51), (73, 64), (66, 64))), None),
    shift("tail", "darker", P((48, 63), (54, 63), (54, 75), (48, 75)), "plum"),
    line("tail", [(65, 52), (65, 62), (65, 64)], "@leaf1", ["@leaf2", "@leaf1"]),
    rows("tail", 60, 53, ["..h...", "hh....", ".h....", "hh...."], {"h": "@leaf3"}, ["@leaf2"]),
]
# FERN: lit top-left of each coil, shaded inner/right of the stems.
tx["10_fern_shading"] = [
    shift("fern", "lighter", OR(P((17, 0), (29, 0), (27, 3), (22, 4), (19, 8), (17, 9)), P((43, 0), (55, 0), (53, 3), (48, 4), (46, 8), (44, 10)))),
    shift("fern", "darker", OR(P((31, 6), (33, 6), (33, 17), (31, 17)), P((46, 6), (48, 6), (48, 17), (46, 17)),
                               P((53, 5), (58, 5), (58, 14), (50, 14)))),
]
labels = {"04_head_shading": "head: lit top plane, cheek underside, occlusion on collar, lower lids",
          "05_collar_shading": "collar: cast shadow of the head, midrib fold, veins, lit edges",
          "06_torso_shading": "torso: collar cast shadow on belly, belly segments, shaded right side",
          "07_arms_shading": "arms: shoulders under collar, inner sides, fingers",
          "08_legs_shading": "legs: occlusion under torso, inner thighs, toes",
          "09_tail_shading": "tail: underside, behind-leg occlusion, frond midrib",
          "10_fern_shading": "fern: lit top-left of coils, shaded stems"}
for k, ops in tx.items():
    json.dump({"label": labels[k], "ops": ops}, open(f"tx/{k}.json", "w"), indent=0)
