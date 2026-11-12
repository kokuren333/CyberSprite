# inspection only: tile preview PNGs side by side for viewing
import sys
from PIL import Image
out, files = sys.argv[1], sys.argv[2:]
ims = [Image.open(f).convert('RGBA') for f in files]
w = sum(i.width for i in ims) + 4*(len(ims)-1); h = max(i.height for i in ims)
m = Image.new('RGBA', (w, h), (255,0,255,255)); x = 0
for i in ims: m.paste(i, (x, 0)); x += i.width + 4
m.save(out)
