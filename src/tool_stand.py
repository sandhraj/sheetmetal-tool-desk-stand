"""Screwdriver & tool desk stand - parametric generator.

Units mm. 1.5 mm mild steel (low-Si CRCA), laser cut, press-brake formed, hot-dip galvanised after forming.
Bend deduction (1.5 mm, Ri 1.5, 90 deg, K~0.33) BD = 2.9  -> confirm with your press-brake shop.

Parts
  TOP_PLATE    300 x 170 flat, 45 tool slots + 4 standoff holes
  LOWER_PLATE  300 x 170, same hole centres (holes ~8 % smaller), 2 pivot ears lanced inside the outline, bent DOWN
  BASE         300 x 170 desk foot, 2 lanced ears bent UP; both arms are cut from inside it
  ARM x2       150 x 30, pivot holes 120 c-c + lightening slot (not a pivot)

x stack (right side, from centre): tray ear + base ear [140.5, 142] | arm [142, 143.5] | plate edges 150

Run:  python tool_stand.py   -> build/*.dxf + build/geometry.json (prints a check report)
Deps: pip install ezdxf shapely matplotlib
"""
import math, json, os
import ezdxf
from shapely.geometry import box, Point, LineString, Polygon
from shapely.ops import unary_union
from shapely import affinity

T, BD, HOLE, Q = 1.5, 2.9, 7.0, 24
RI = 1.5
D = 170.0
W_TOP, W_LOW = 300.0, 300.0
GAP = 45.0                        # top face to top face (standoff setting)
SO = (W_TOP/2 - 7.5, 7.5)         # standoff hole inset (x, y)
EAR_W, EAR_R = 36.0, 18.0
H2 = 25.0                         # tray pivot depth below lower plate top face
L_ARM, ARM_W = 120.0, 30.0        # pivot hole to top-end centre
SLOT = (22.0, 98.0)               # LIGHTENING slot only (not a pivot), clear of the r18 ear contact
SLOT_W = 10.0
H1 = 25.0                         # base pivot height
BASE_W, BASE_D, YB = 300.0, 170.0, 95.0
X_ARM_IN = 142.0                  # arm sits flat on both ears (fixed tray pivot, no spacers)
X_EAR_OML = None                  # set below: base ear shares the tray-ear plane [140,142]
XB = None
SPACER_T = 0.0                    # no spacers
X_TEAR_OML = X_ARM_IN - SPACER_T - T   # 140 tray-ear inboard face (bend outside)
XL = X_TEAR_OML + BD              # 143.8 flat x of h=0 on tray ear; depth h -> XL - h
X_EAR_OML = X_TEAR_OML            # 140 base-ear inboard face; ear sits at [140,142], 5 discs to arm
XB = X_EAR_OML - T + BD           # 141.8 flat x of Z=0 on base ear
REL_EXT = 3.5                     # bend-relief run past bend line (lower plate)
REL_W = 2.0                       # bend-relief slot width (= T)
BSLOT = 14.0                      # bend-line slot length (centre of each tab)
DISC_D = 24.0

def slot(x1, y1, x2, y2, w): return LineString([(x1, y1), (x2, y2)]).buffer(w/2, quad_segs=Q)
def rrect(cx, cy, w, h, r):
    if 2*r >= min(w, h) - 0.01:
        return slot(cx, cy-(h-w)/2, cx, cy+(h-w)/2, w) if h >= w else slot(cx-(w-h)/2, cy, cx+(w-h)/2, cy, h)
    return box(cx-w/2, cy-h/2, cx+w/2, cy+h/2).buffer(-r, quad_segs=Q).buffer(r, quad_segs=Q)
def rc(p, r): return p.buffer(-r, quad_segs=Q).buffer(r, quad_segs=Q)

# ---------- tool pattern, template reflowed to 300 x 170 (y from FRONT edge) ----------
# (kind, x, y, w, h, r, group)
PAT = []
def add(kind, x, y, w, h=None, r=0, g="", top_only=False): PAT.append((kind, x, y, w, h if h else w, r, g, top_only))
for x in (-126.5, 126.5):
    for y in (135.0, 35.0): add("rr", x, y, 28, 32, 3, "A  28x32 - pliers / long-nose (jaws down)")
add("rr", 126.5 - 55.0, 135.0, 28, 32, 3, "A  28x32 - pliers / long-nose (jaws down)")
for x in (-121.5, 121.5): add("rr", x, 85.0, 43, 38, 4, "K  43x38 - stripper handle (ear opening on TS-03)", True)
for x in (-66.5, 66.5): add("rr", x, 85.0, 30, 22, 11, "P  30x22 slot - 2nd stripper handle, 55 c-c to K")
for x in (-80, -48, -16, 16): add("c", x, 147.0, 9, g="L  Dia 9 - large screwdrivers (handle to 30)")
for x in (-91, -65, -39, -13, 13, 39): add("c", x, 117.0, 8, g="M  Dia 8 - medium screwdrivers (handle to 24)")
for x in (-30, -10, 10, 30): add("c", x, 85.0, 8, g="N  Dia 8 - small screwdrivers (handle to 18)")
for x in (-91, -65, -39, -13): add("rr", x, 47.0, 18, 18, 2, "Q  18x18 - flush / diagonal cutters (jaws down)")
for x, (w, h) in zip((15, 33, 51, 69, 87), ((6, 10), (7, 12), (7, 12), (6, 10), (7, 12))):
    add("rr", x, 47.0, w, h, w/2, "T  slot - tweezers, back end down")
for i in range(13): add("c", -96 + 16*i, 20.0, 6, g="R  Dia 6 - precision drivers (handle to 14)")

def shrink(v):
    """lower-plate size: ~8 % smaller, at least 1 mm, at most 3 mm, rounded to 0.5"""
    return round((v - max(1.0, min(3.0, 0.08*v)))*2)/2
def lower_size(k, w, h, r):
    lw, lh = shrink(w), shrink(h)
    if k == "c": return lw, lw, 0
    full = 2*r >= min(w, h) - 0.01
    lr = min(lw, lh)/2 if full else min(r, min(lw, lh)/2)
    return lw, lh, lr
def pat_geoms(lower=False):
    out = []
    for (k, x, y, w, h, r, g, top_only) in PAT:
        if lower and top_only: continue
        if lower: w, h, r = lower_size(k, w, h, r)
        out.append(("c", x, y, w) if k == "c" else ("p", rrect(x, y, w, h, r)))
    return out

parts = {}
# ---------- TOP PLATE ----------
holes = pat_geoms() + [("c", sx*SO[0], sy, HOLE) for sx in (1, -1) for sy in (SO[1], D-SO[1])]
parts["TOP_PLATE"] = dict(outline=rc(box(-W_TOP/2, 0, W_TOP/2, D), 6), holes=holes, bends=[], qty=1)

# ---------- LOWER PLATE ----------
yc = D/2
BEND_SLOTS = []
def lanced(xb, depth, s, ext):
    """tab whose flat runs inboard from bend line xb; returns (tab, channel)"""
    e = unary_union([box(xb - depth, yc_ - EAR_W/2, xb + ext, yc_ + EAR_W/2),
                     Point(xb - depth, yc_).buffer(EAR_R, quad_segs=Q)])
    ch = e.buffer(1.5, quad_segs=Q, join_style=2).difference(e).difference(box(xb + ext - 0.1, -1e3, 1e3, 1e3))
    ch = unary_union([g for g in getattr(ch, "geoms", [ch]) if g.area > 1])
    # bend reliefs: 2 mm wide round-ended slots at both tab corners, running past the bend line
    yr = EAR_W/2 + 0.75
    rel = unary_union([slot(xb - 3, yc_ + sg*yr, xb + ext - REL_W/2, yc_ + sg*yr, REL_W) for sg in (1, -1)])
    ch = unary_union([ch, rel])
    # bend-line slot in the middle of the tab: localises the fold, halves bending force
    bs = slot(xb, yc_ - BSLOT/2 + REL_W/2, xb, yc_ + BSLOT/2 - REL_W/2, REL_W)
    if s == -1: e, ch, bs = (affinity.scale(g, -1, 1, origin=(0, 0)) for g in (e, ch, bs))
    BEND_SLOTS.append(bs)
    return e, ch
yc_ = yc
holes = pat_geoms(lower=True) + [("c", sx*SO[0], sy, HOLE) for sx in (1, -1) for sy in (SO[1], D-SO[1])]
LOW_TABS = []
for s_ in (1, -1):
    e, ch = lanced(XL, H2, s_, REL_EXT)
    LOW_TABS.append(e)
    holes.append(("p", ch)); holes.append(("p", BEND_SLOTS[-1])); holes.append(("c", s_*(XL - H2), yc, HOLE))
parts["LOWER_PLATE"] = dict(outline=rc(box(-W_LOW/2, 0, W_LOW/2, D), 6), holes=holes, qty=1,
    bends=[(s_*XL, yc - EAR_W/2, yc + EAR_W/2, "DOWN 90") for s_ in (1, -1)])

# ---------- ARM ----------
arm_o = slot(0, 0, L_ARM, 0, ARM_W)
arm_h = [("c", 0, 0, HOLE), ("c", L_ARM, 0, HOLE), ("p", slot(SLOT[0], 0, SLOT[1], 0, SLOT_W))]
parts["ARM"] = dict(outline=arm_o, holes=arm_h, bends=[], qty=2)

# ---------- BASE ----------
holes = []
bends = []
BASE_TABS = []
for s_ in (1, -1):
    yc_ = YB
    e, ch = lanced(XB, H1, s_, 3.5)
    BASE_TABS.append(e)
    holes.append(("p", ch)); holes.append(("p", BEND_SLOTS[-1])); holes.append(("c", s_*(XB - H1), YB, HOLE))
    bends.append((s_*XB, YB - EAR_W/2, YB + EAR_W/2, "UP 90"))
yc_ = yc
ARM_POS = [(-L_ARM/2, 28.0), (-L_ARM/2, 66.0)]
for (ax, ay) in ARM_POS:
    holes.append(("arm", ax, ay))
DISC_POS = []
for (dx_, dy_) in DISC_POS:
    holes.append(("disc", dx_, dy_))
parts["BASE"] = dict(outline=rc(box(-BASE_W/2, 0, BASE_W/2, BASE_D), 12), holes=holes, bends=bends, qty=1)

def expand(p):      # list of shapely features (arms expanded to outline + holes)
    out = []
    for h in p["holes"]:
        if h[0] == "c": out.append(("c", Point(h[1], h[2]).buffer(h[3]/2, quad_segs=Q), h))
        elif h[0] == "p": out.append(("p", h[1], h))
        else:
            po, ph = (arm_o, arm_h) if h[0] == "arm" else (Point(0, 0).buffer(DISC_D/2, quad_segs=Q), [("c", 0, 0, HOLE)])
            out.append(("armo", affinity.translate(po, h[1], h[2]), h))
            for ah in ph:
                g = Point(ah[1], ah[2]).buffer(ah[3]/2, quad_segs=Q) if ah[0] == "c" else ah[1]
                out.append(("armh", affinity.translate(g, h[1], h[2]), h))
    return out

# ---------- checks ----------
rep = {"tool_holes": len(PAT)}
for n, p in parts.items():
    f = expand(p)
    shapes = [g for (k, g, _) in f if k != "armh"]
    s = p["outline"]
    for g in shapes: s = s.difference(g)
    mw = min((shapes[i].distance(shapes[j]) for i in range(len(shapes)) for j in range(i+1, len(shapes))), default=99)
    me = min((p["outline"].exterior.distance(g) for g in shapes), default=99)
    b = p["outline"].bounds
    cut = p["outline"].length + sum(g.length for (k, g, _) in f)
    pierce = 1 + len(f)
    area = s.area + sum(g.area for (k, g, _) in f if k == "armo") - sum(g.area for (k, g, _) in f if k == "armh")
    rep[n] = dict(blank=f"{b[2]-b[0]:.1f} x {b[3]-b[1]:.1f}", min_web=round(mw, 1), min_edge=round(me, 1),
                  pierces=pierce, cut_m=round(cut/1000, 2), kg_each=round(s.area*T*7.85e-6, 3))
    p["kg"] = s.area*T*7.85e-6

# ---------- kinematics ----------
M_TOOLS = 1.5
M_SO = 4*0.035
m_tray = parts["TOP_PLATE"]["kg"] + parts["LOWER_PLATE"]["kg"] + M_SO + M_TOOLS
m_arm = parts["ARM"]["kg"]
def pose(alpha, s, theta):
    a = math.radians(alpha)
    p1 = (YB, H1); p2 = (YB + s*math.sin(a), H1 + s*math.cos(a))
    t = math.radians(theta)
    def G(y, h):
        dy, dz = y - yc, -(h - H2)
        return (p2[0] + dy*math.cos(t) - dz*math.sin(t), p2[1] + dy*math.sin(t) + dz*math.cos(t))
    return p1, p2, t, G
def evaluate(alpha, s, theta, shank=130.0):
    p1, p2, t, G = pose(alpha, s, theta)
    dn = (math.sin(t), -math.cos(t))
    tips = [G(y, T)[1] + shank*dn[1] for y in (10, yc, D-10)]
    ear_low = min(G(yc + EAR_R*math.cos(k/12*math.pi), H2 + EAR_R*math.sin(k/12*math.pi))[1] for k in range(13))
    plate_low = min(G(0, T)[1], G(D, T)[1])
    # CG
    cg_tray = [(parts["TOP_PLATE"]["kg"], G(yc, -GAP + 1)), (parts["LOWER_PLATE"]["kg"], G(yc, 1)),
               (M_SO, G(yc, -GAP/2)), (M_TOOLS, G(yc, -GAP - 30))]
    mt = sum(m for m, _ in cg_tray); cgt = sum(m*q[0] for m, q in cg_tray)/mt
    arm_mid = ((p1[0] + p2[0])/2, 0)
    cg_all = (cgt*mt + 2*m_arm*arm_mid[0] + parts["BASE"]["kg"]*BASE_D/2)/(mt + 2*m_arm + parts["BASE"]["kg"])
    g = 9.81
    t_p2 = mt*g*abs(cgt - p2[0])/1000/2
    t_p1 = (mt*g*abs(cgt - p1[0]) + 2*m_arm*g*abs(arm_mid[0] - p1[0]))/1000/2
    top_front = G(0, -GAP)
    return dict(tip=min(tips), ear_low=ear_low, plate_low=plate_low, cg=cg_all,
                t_p2=t_p2, t_p1=t_p1, front_h=top_front[1], front_y=top_front[0])
grid = []
for alpha in (-15, 0, 15, 30, 45):
    for s in (120,):
        for theta in (0, 15, 30, 45, 60):
            e = evaluate(alpha, s, theta)
            ok = e["tip"] >= 5 and e["plate_low"] > 5 and 20 < e["cg"] < BASE_D - 20
            grid.append(dict(alpha=alpha, s=s, theta=theta, ok=ok, **{k: round(v, 1) for k, v in e.items()}))
rep["grid_ok"] = f"{sum(g['ok'] for g in grid)}/{len(grid)}"
rep["max_torque_needed_per_side_Nm"] = dict(P1=round(max(g["t_p1"] for g in grid if g["ok"]), 2),
                                            P2=round(max(g["t_p2"] for g in grid if g["ok"]), 2))
PRESETS = {"Gentle 20°": (0, 120, 20), "Standard 30°": (0, 120, 30), "Mid 45°": (0, 120, 45), "Steep 60°": (0, 120, 60)}
rep["presets"] = {k: {kk: round(vv, 1) for kk, vv in evaluate(*v).items()} for k, v in PRESETS.items()}
# fold-flat check (empty tray): arm horizontal pointing back, slot at 60, tray flat
pf = evaluate(90, 120, 0, shank=0)
rep["fold_flat"] = dict(ear_low=round(pf["ear_low"], 1), plate_low=round(pf["plate_low"], 1),
                        top_h=round(pose(90, 120, 0)[3](yc, -GAP - T)[1], 1))
rep["mass_tray_with_tools"] = round(m_tray, 2)
rep["mass_steel_total"] = round(sum(p["kg"]*p["qty"] for p in parts.values()) - 2*m_arm*0 , 2)

# ---------- DXF ----------
def new_doc():
    doc = ezdxf.new("R2010", setup=True); doc.units = ezdxf.units.MM
    doc.layers.add("CUT", color=7); doc.layers.add("BEND", color=1, linetype="DASHED"); doc.layers.add("LABEL", color=3)
    return doc
def poly(msp, g):
    for gg in getattr(g, "geoms", [g]):
        for ring in [gg.exterior] + list(gg.interiors):
            msp.add_lwpolyline(list(ring.coords)[:-1], close=True, dxfattribs={"layer": "CUT"})
def add_part(msp, name, p, dx=0, dy=0, label=True):
    tr = lambda g: affinity.translate(g, dx, dy)
    poly(msp, tr(p["outline"]))
    for (k, g, h) in expand(p):
        if k == "c" or (k == "armh" and g.geom_type == "Polygon" and abs(g.area - math.pi*HOLE**2/4) < 1):
            c = tr(g.centroid); msp.add_circle((c.x, c.y), HOLE/2 if k == "armh" else h[3]/2, dxfattribs={"layer": "CUT"})
        else:
            poly(msp, tr(g))
    for (x, y0, y1, txt) in p["bends"]:
        msp.add_line((x+dx, y0+dy), (x+dx, y1+dy), dxfattribs={"layer": "BEND"})
        msp.add_text(txt, height=3.5, dxfattribs={"layer": "LABEL"}).set_placement(
            (x + dx + (-6 if x > 0 else 6), (y0+y1)/2 + dy), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
    if label:
        bb = tr(p["outline"]).bounds
        msp.add_text(f"{name}  QTY {p['qty']}  1.5 mm", height=5, dxfattribs={"layer": "LABEL"}).set_placement(
            ((bb[0]+bb[2])/2, bb[1] - 7), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)

os.makedirs("build", exist_ok=True)
for n, p in parts.items():
    doc = new_doc(); add_part(doc.modelspace(), n, p); doc.saveas(f"build/{n}.dxf")
GN = 8
lb, tb, bb = (parts[k]["outline"].bounds for k in ("LOWER_PLATE", "TOP_PLATE", "BASE"))
Wn = max(lb[2]-lb[0], bb[2]-bb[0])
lay = [("BASE", Wn/2, -bb[1])]
y0 = bb[3] - bb[1] + GN
lay.append(("LOWER_PLATE", -lb[0], y0 - lb[1]))
y0 += lb[3] - lb[1] + GN
lay.append(("TOP_PLATE", -tb[0], y0 - tb[1]))

doc = new_doc(); msp = doc.modelspace(); outs = []
for (n, dx, dy) in lay:
    add_part(msp, n, parts[n], dx, dy, label=False); outs.append(affinity.translate(parts[n]["outline"], dx, dy))
ext = unary_union(outs).bounds
rep["nest_min_gap"] = round(min(outs[i].distance(outs[j]) for i in range(len(outs)) for j in range(i+1, len(outs))), 1)
rep["nest_max_x"] = round(ext[2], 1)
rep["nest_blank"] = f"{ext[2]-ext[0]+10:.0f} x {ext[3]-ext[1]+10:.0f}"
msp.add_text("1.5 mm MS (CRCA) sheet, HDG after forming | layers: CUT (white), BEND (red dashed), LABEL (green, do not cut) | 2 arms cut inside the base",
             height=5, dxfattribs={"layer": "LABEL"}).set_placement((ext[0], ext[1] - 12))
doc.saveas("build/TOOL_STAND_NESTED_ALL_PARTS.dxf")

# ---------- geometry export for the HTML drawing ----------
def rings(g):
    out = []
    for gg in getattr(g, "geoms", [g]):
        out.append([[round(x, 2), round(y, 2)] for x, y in gg.exterior.coords])
        for r in gg.interiors: out.append([[round(x, 2), round(y, 2)] for x, y in r.coords])
    return out
geo = {}
for n, p in parts.items():
    feats = []
    for (k, g, h) in expand(p):
        if k == "c": feats.append({"t": "c", "x": round(h[1], 2), "y": round(h[2], 2), "d": h[3]})
        elif k == "armh" and abs(g.area - math.pi*HOLE**2/4) < 1:
            c = g.centroid; feats.append({"t": "c", "x": round(c.x, 2), "y": round(c.y, 2), "d": HOLE})
        else: feats.append({"t": "p", "r": rings(g)})
    geo[n] = {"outline": rings(p["outline"]), "feats": feats, "bends": p["bends"], "qty": p["qty"],
              "kg": round(p["kg"], 3), **rep[n]}
geo["nest"] = [{"part": n, "dx": dx, "dy": dy} for (n, dx, dy) in lay]
geo["params"] = dict(T=T, BD=BD, D=D, W_TOP=W_TOP, W_LOW=W_LOW, GAP=GAP, SO=SO, EAR_W=EAR_W, EAR_R=EAR_R,
                     H2=H2, L_ARM=L_ARM, ARM_W=ARM_W, SLOT=SLOT, SLOT_W=SLOT_W, H1=H1, BASE_W=BASE_W,
                     BASE_D=BASE_D, YB=YB, RI=RI, REL_W=REL_W, BSLOT=BSLOT, REL_EXT_B=3.5, XL=XL, XB=XB, nest_blank=rep["nest_blank"], SPACER_T=SPACER_T, DISC_D=DISC_D, X_TEAR_OML=X_TEAR_OML, X_ARM_IN=X_ARM_IN, REL_EXT=REL_EXT)
geo["pattern"] = [dict(k=k, x=x, y=y, w=w, h=h, r=r, g=g, top=top_only, low=lower_size(k, w, h, r)) for (k, x, y, w, h, r, g, top_only) in PAT]
geo["presets"] = PRESETS
geo["grid"] = grid
geo["rep"] = rep
json.dump(geo, open("build/geometry.json", "w"))
print(json.dumps({k: v for k, v in rep.items()}, indent=1))
