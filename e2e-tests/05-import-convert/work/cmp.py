"""Compare a 32x32 result (indexed or RGBA PNG) with the clean original. Inspection only."""
import sys
from PIL import Image
a = Image.open("source_input/slime_clean_32.png").convert("RGBA")
b = Image.open(sys.argv[1]).convert("RGBA")
assert a.size == b.size, (a.size, b.size)
pa, pb = a.load(), b.load()
exact = alpha_mis = 0; dsum = 0; near = 0; diffs = []
for y in range(32):
    for x in range(32):
        p, q = pa[x, y], pb[x, y]
        if (p[3] > 0) != (q[3] > 0):
            alpha_mis += 1; diffs.append((x, y, p, q)); continue
        if p[3] == 0:
            exact += 1; continue
        d = max(abs(p[c] - q[c]) for c in range(3))
        if d == 0: exact += 1
        else: diffs.append((x, y, p, q))
        if d <= 16: near += 1
        dsum += d
print(f"exact {exact}/1024  alpha_mismatch {alpha_mis}  opaque_within16 {near}  colors_b {len(set(b.getdata()))}")
if len(sys.argv) > 2:
    for d in diffs: print(d)
