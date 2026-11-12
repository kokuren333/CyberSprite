"""Structural comparison: map each result colour to the original colour it most often covers,
then count pixels whose mapped colour equals the original. Inspection only."""
import sys
from collections import Counter, defaultdict
from PIL import Image
a = Image.open("source_input/slime_clean_32.png").convert("RGBA"); pa = a.load()
names = {(30,43,56):'K',(47,122,60):'D',(79,179,74):'G',(143,224,104):'L',(232,255,208):'H',(255,255,255):'W',(240,138,154):'P',(90,97,112):'S'}
def nm(p): return '.' if p[3] == 0 else names.get(p[:3], '?')
for f in sys.argv[1:]:
    b = Image.open(f).convert("RGBA"); pb = b.load()
    cov = defaultdict(Counter)
    for y in range(32):
        for x in range(32):
            cov[pb[x, y]][nm(pa[x, y])] += 1
    mp = {c: cnt.most_common(1)[0][0] for c, cnt in cov.items()}
    ok = sum(1 for y in range(32) for x in range(32) if mp[pb[x, y]] == nm(pa[x, y]))
    wrong = Counter((nm(pa[x, y]), mp[pb[x, y]]) for y in range(32) for x in range(32) if mp[pb[x, y]] != nm(pa[x, y]))
    print(f"{f}: structural match {ok}/1024; colours {len(cov)}; mapping {sorted(set(mp.values()))}; errors(orig->got) {dict(wrong)}")
