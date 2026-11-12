"""Builds op transactions (JSON) for leg/arm layers. Pixels are written only by CyberSprite ops."""
import json, sys
B = [0,1,0,-1,0,1,0,-1, 0,1]           # body bob per frame
SHOES = {  # (origin dx, dy from ankle point, rows)  sym: c=shoe, d=sole ; far: d / 2
 'flat': (0, 1, ["ccc.", "dddd"]),
 'heel': (0, 0, ["...c", "cccd", "dd.."]),
 'toe':  (0, 1, ["cc..", ".ccc", "..dd"]),
 'swing':(0, 1, ["ccc", ".dd"]),
 'reach':(0, 0, ["...c", "cccd", "d..."]),
}
def leg_pose(phase, hx, b):
    hy = 20 + b
    P = {
     0: ([(hx,hy),(hx+2,23),(hx+4,26)], 'heel', (hx+4,26)),
     1: ([(hx,hy),(hx+3,24),(hx+2,26)], 'flat', (hx+2,26)),
     2: ([(hx,hy),(hx+1,23),(hx,26)],   'flat', (hx,26)),
     3: ([(hx,hy),(hx-1,22),(hx-2,25)], 'toe',  (hx-2,25)),
     4: ([(hx,hy),(hx-2,23),(hx-4,25)], 'toe',  (hx-4,25)),
     5: ([(hx,hy),(hx-1,24),(hx-3,24)], 'toe',  (hx-3,24)),
     6: ([(hx,hy),(hx+2,23),(hx,25)],   'swing',(hx,25)),
     7: ([(hx,hy),(hx+3,22),(hx+3,24)], 'reach',(hx+3,24)),
    }
    return P[phase]
ARM = {'back':((-2,3),(-4,5)),'backmid':((-1,3),(-2,6)),'mid':((0,3),(1,6)),
       'fwdmid':((1,3),(3,5)),'fwd':((2,3),(4,4)),'hang':((0,3),(0,6))}
NEAR_ARM = ['back','backmid','mid','fwdmid','fwd','fwdmid','mid','backmid','hang','hang']

def leg_ops(layer, f, pts, shoe, ankle, fill, near):
    b = B[f]
    ops = [{"op":"stroke","args":{"layer":layer,"frame":f,"points":[list(p) for p in pts],"color":fill,"brush":{"size":2}}}]
    dx, dy, rows = SHOES[shoe]
    if not near:
        rows = [r.replace('d','2').replace('c','d') for r in rows]
    ops.append({"op":"draw_rows","args":{"layer":layer,"frame":f,"x":ankle[0]+dx,"y":ankle[1]+dy,"rows":rows,"format":"sym","skip_transparent":True}})
    ops.append({"op":"outline","args":{"layer":layer,"frame":f,"color":1,"placement":"outside","connectivity":4,"region":{"type":"all"}}})
    # remove the outline that would cut across the hip (legs continue into the pants)
    ops.append({"op":"erase","args":{"layer":layer,"frame":f,"region":{"type":"rect","x":0,"y":0,"w":32,"h":20+b}}})
    return ops

def legs(near):
    layer = 'near_leg' if near else 'far_leg'
    hx = 15
    fill = 3 if near else 2
    ops = []
    for f in range(8):
        phase = f if near else (f+4) % 8
        pts, shoe, ankle = leg_pose(phase, hx, B[f])
        ops += leg_ops(layer, f, pts, shoe, ankle, fill, near)
    for f in (8, 9):  # idle stance
        hy = 20 + B[f]
        if near: pts, ankle = [(hx,hy),(hx,23),(hx+1,26)], (hx+1,26)
        else:    pts, ankle = [(hx,hy),(hx-1,23),(hx-2,26)], (hx-2,26)
        ops += leg_ops(layer, f, pts, 'flat', ankle, fill, near)
    return {"label": f"{layer}: walk poses (contact/down/passing/up) + idle stance", "ops": ops}

def arms(near):
    layer = 'near_arm' if near else 'far_arm'
    sx = 15 if near else 14
    fill, hand = (5, 8) if near else (16, 17)
    ops = []
    for f in range(10):
        name = NEAR_ARM[f] if (near or f >= 8) else NEAR_ARM[(f+4) % 8]
        sy = 14 + B[f]
        (ex,ey),(hx_,hy_) = ARM[name]
        pts = [[sx,sy],[sx+ex,sy+ey],[sx+hx_,sy+hy_]]
        ops.append({"op":"stroke","args":{"layer":layer,"frame":f,"points":pts,"color":fill,"brush":{"size":2}}})
        ops.append({"op":"rect","args":{"layer":layer,"frame":f,"x":sx+hx_,"y":sy+hy_,"w":2,"h":2,"color":hand,"filled":True}})
        ops.append({"op":"outline","args":{"layer":layer,"frame":f,"color":1,"placement":"outside","connectivity":4,"region":{"type":"all"}}})
    return {"label": f"{layer}: arm swing opposite to legs + idle hang", "ops": ops}

which = sys.argv[1]
out = {'near_leg':lambda:legs(True),'far_leg':lambda:legs(False),'near_arm':lambda:arms(True),'far_arm':lambda:arms(False)}[which]()
json.dump(out, open(f"work/t_{which}.json","w"))
print(len(out['ops']))
