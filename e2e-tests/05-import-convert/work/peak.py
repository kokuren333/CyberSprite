import sys
from PIL import Image
im = Image.open(sys.argv[1]).convert("RGBA"); W, H = im.size; p = im.load()
ex = [0]*W
for x in range(1, W):
    s = 0
    for y in range(H):
        a, b = p[x, y], p[x-1, y]
        s += sum(abs(a[c]-b[c]) for c in range(4))
    ex[x] = s
tot = sum(ex)
def peakA(N):
    B = [(k*W + N//2)//N for k in range(1, N)]
    return sum(ex[b] for b in B)*(W-1)*1000//(tot*len(B))
def peakB(s, o):
    B = [o+k*s for k in range(0, W) if 1 <= o+k*s <= W-1]
    return sum(ex[b] for b in B)*(W-1)*1000//(tot*len(B))
print("A N=32", peakA(32), "A N=31", peakA(31), "A N=33", peakA(33))
print("best A", sorted(((peakA(N), N) for N in range(6, 173)), reverse=True)[:5])
print("best B", sorted(((peakB(s, o), s, o) for s in range(2, 65) for o in range(s)), reverse=True)[:5])
