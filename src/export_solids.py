import json, math
import tool_stand as S
from shapely.geometry import box, Point
from shapely.ops import unary_union

def rings(g):
    g = g.buffer(0)
    if g.geom_type == "MultiPolygon":
        g = max(g.geoms, key=lambda x: x.area)
    return {"ext": [[round(x, 2), round(y, 2)] for x, y in g.exterior.coords],
            "holes": [[[round(x, 2), round(y, 2)] for x, y in r.coords] for r in g.interiors]}

def solid(p, clip=None, extra_cut=None):
    s = p["outline"] if clip is None else p["outline"].intersection(clip)
    for (k, g, _) in S.expand(p):
        if k != "armh": s = s.difference(g)
    if extra_cut is not None: s = s.difference(extra_cut)
    return s

P = S.parts
out = {}
out["top"] = rings(solid(P["TOP_PLATE"]))
out["lower"] = rings(solid(P["LOWER_PLATE"], extra_cut=unary_union([t.buffer(1.6) for t in S.LOW_TABS])))
ear = unary_union([box(S.D/2 - S.EAR_W/2, 0, S.D/2 + S.EAR_W/2, S.H2), Point(S.D/2, S.H2).buffer(S.EAR_R, quad_segs=24)])
out["lower_ear"] = rings(ear.difference(Point(S.D/2, S.H2).buffer(S.HOLE/2, quad_segs=24)))   # (y, h)
out["base"] = rings(solid(P["BASE"], extra_cut=unary_union([t.buffer(1.6) for t in S.BASE_TABS])))
bear = unary_union([box(S.YB - S.EAR_W/2, 0, S.YB + S.EAR_W/2, S.H1), Point(S.YB, S.H1).buffer(S.EAR_R, quad_segs=24)])
out["base_ear"] = rings(bear.difference(Point(S.YB, S.H1).buffer(S.HOLE/2, quad_segs=24)))   # (Y, Z)
out["arm"] = rings(solid(P["ARM"]))

json.dump(out, open("build/solids.json", "w"))
print({k: (len(v["ext"]), len(v["holes"])) for k, v in out.items()})
