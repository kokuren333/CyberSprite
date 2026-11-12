# read-only inspection of exported files
import json
from PIL import Image, ImageSequence
def rgba(im): return im.convert('RGBA')
ref = [rgba(Image.open(f'export/frames/runner_{i:02}.png')) for i in range(10)]
def down4(im):  # nearest downscale of x4 image, also check blocks are uniform
    im = rgba(im); w,h = im.size; px = im.load(); ok = True
    out = Image.new('RGBA',(w//4,h//4)); o = out.load()
    for y in range(h//4):
        for x in range(w//4):
            c = px[x*4,y*4]; o[x,y] = c
            for dy in range(4):
                for dx in range(4):
                    if px[x*4+dx,y*4+dy] != c: ok = False
    return out, ok
def same(a,b):
    a,b = a.load(), b.load()
    for y in range(32):
        for x in range(32):
            pa,pb=a[x,y],b[x,y]
            if pa[3]==0 and pb[3]==0: continue
            if pa!=pb: return False
    return True
for name, tagframes in (('walk_x4.gif', list(range(8))), ('idle_x4.gif', [8,9]), ('walk_x4.png', list(range(8)))):
    im = Image.open('export/'+name)
    print(f'== {name}: format={im.format} size={im.size} n_frames={getattr(im,"n_frames",1)} loop={im.info.get("loop")} mode={im.mode}')
    for k, fr in enumerate(ImageSequence.Iterator(im)):
        d = fr.info.get('duration')
        small, uniform = down4(fr)
        match = [i for i in range(10) if same(small, ref[i])]
        print(f'  frame {k}: duration={d} uniform4x4={uniform} matches_project_frames={match}')
# sheet vs json
sheet = rgba(Image.open('export/runner_sheet.png')); data = json.load(open('export/runner_sheet.json'))
print('== sheet', Image.open('export/runner_sheet.png').mode, sheet.size, 'meta.size', data['meta']['size'])
for i,(k,v) in enumerate(data['frames'].items()):
    r = v['frame']; crop = sheet.crop((r['x'],r['y'],r['x']+r['w'],r['y']+r['h']))
    match = [j for j in range(10) if same(crop, ref[j])]
    print(f'  {k!r}: rect={r} dur={v["duration"]} matches={match}')
print('  tags', [(t['name'],t['from'],t['to'],t['direction']) for t in data['meta']['frameTags']])
# x1 frames palette check
p = Image.open('export/frames/runner_00.png'); print('== frame png mode', p.mode, 'palette entries', len(p.getpalette() or [])//3, 'transparency', p.info.get('transparency') if not isinstance(p.info.get('transparency'), bytes) else p.info['transparency'][:4])
