# idle animation (8 frames). Offsets are relative to frame 0; the fern lags the head by one frame (follow-through),
# the frond sways, frame 4 squashes the head (lower top, cheeks 1 px wider each side), frames 6-7 blink.
import json, sys
sys.path.insert(0, "tx")
from build_a_v3 import rows

HEAD = [0, -1, -1, 0, 1, 0, 0, 0]
FERN = [0, 0, -1, -1, 0, 1, 0, 0]
ARMS = [0, 0, -1, -1, 0, 0, 0, 0]
FROND_DX = [0, 0, 1, 1, 0, 0, 0, 0]
DUR = [240, 120, 120, 120, 120, 200, 60, 80]

T = {}
T["25_anim_frames"] = ("idle: 7 copies of frame 0", [{"op": "add_frame", "args": {"count": 7, "cels": "copy", "copy_from": 0}}])
mv = []
for f in range(1, 8):
    for layer in ("head", "face", "collar"):
        if HEAD[f]:
            mv.append({"op": "move_cel", "args": {"layer": layer, "frame": f, "dy": HEAD[f], "scope": "frame"}})
    if FERN[f]:
        mv.append({"op": "move_cel", "args": {"layer": "fern", "frame": f, "dy": FERN[f], "scope": "frame"}})
    if ARMS[f]:
        mv.append({"op": "move_cel", "args": {"layer": "arms", "frame": f, "dy": ARMS[f], "scope": "frame"}})
    if FROND_DX[f]:
        mv.append({"op": "move_cel", "args": {"layer": "frond", "frame": f, "dx": FROND_DX[f], "scope": "frame"}})
T["26_anim_offsets"] = ("idle: breathing offsets, fern lags the head by one frame, frond sway", mv)
# frame 4 squash: head top is already 1 px lower (move); widen the cheeks by 1 px each side (y 29-36 after the move)
T["27_anim_squash"] = ("idle f4: head squash, cheeks 1 px wider each side", [
    rows("head", 14, 29, ["kd"] * 8, {"k": "@line", "d": "@plum2"}, frame=4),
    rows("head", 60, 29, ["dk"] * 8, {"k": "@line", "d": "@plum1"}, frame=4),
])
# blink: eye boxes at x20/44, y20 (face layer, frames 6-7 are not moved)
half = ["....kkkk....", "..kkddddkk..", ".kddddddddk.", ".kddddddddk.", "kddddddddddk", "kkkkkkkkkkkk",
        "kaakkkkkkaak", "kaakkkkkkaak", ".kaakkkkaak.", ".kaaaaaaaak.", "..kkaaaakk..", "....kkkk...."]
closed = ["............", "............", "............", "............", "............", "............",
          ".kk......kk.", "...kkkkkk...", "............", "............", "............", "............"]
lg = {"k": "@line", "a": "@amber1", "d": "@plum2"}
blink = []
for x in (20, 44):
    blink.append(rows("face", x, 20, half, lg, skip=False, frame=6))
    blink.append(rows("face", x, 20, closed, lg, skip=False, frame=7))
T["28_anim_blink"] = ("idle f6-f7: half-closed and closed eyes", blink)
T["29_anim_timing"] = ("idle: durations and tag", [
    *[{"op": "set_frame_duration", "args": {"frames": [f], "duration_ms": d}} for f, d in enumerate(DUR)],
    {"op": "add_tag", "args": {"name": "idle", "from": 0, "to": 7}}])
for k, (label, ops) in T.items():
    json.dump({"label": label, "ops": ops}, open(f"tx/{k}.json", "w"))
print(" ".join(T))
