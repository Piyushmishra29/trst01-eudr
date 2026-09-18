#!/usr/bin/python3 -s
"""Snap hand-traced plots (traced_px.py) to the snapped roads (roads_snapped.json).

Each straight edge that runs along a road within GROW px is moved, as a whole, onto the road
edge (outward if it stops short, inward if it sits on the road). Corners are re-intersected so
lines stay straight; finally the exact road corridor is cut out. Writes polished_px.json."""
import json, os
import numpy as np
from osgeo import ogr
from traced_px import PLOTS, WHOLE, FIXED
from roads_px import HIGHWAY, HIGHWAY_W
ogr.UseExceptions()
GROW = 14          # px (7 m): furthest an edge is moved to reach a road
HIT = 0.5          # share of an edge's samples that must see a road before it moves


def line(pts):
    g = ogr.Geometry(ogr.wkbLineString)
    for x, y in pts:
        g.AddPoint_2D(float(x), float(y))
    return g


road = None
for name, (w, pts, _) in json.load(open("roads_snapped.json")).items():
    g = line(pts).Simplify(1.0).Buffer(w / 2, 8)
    road = g if road is None else road.Union(g)
road = road.Union(line(HIGHWAY).Buffer(HIGHWAY_W / 2, 4))


def poly(pts):
    r = ogr.Geometry(ogr.wkbLinearRing)
    for x, y in list(pts) + [pts[0]]:
        r.AddPoint_2D(float(x), float(y))
    p = ogr.Geometry(ogr.wkbPolygon); p.AddGeometry(r)
    return p


def edge_shift(a, b, n, inside):
    """Median offset along outward normal n that puts edge a-b on the road's near edge."""
    L = np.hypot(*(b - a)); k = max(5, int(L / 4))
    hits = []
    for t in np.linspace(0.1, 0.9, k):
        p = a + (b - a) * t
        pt = ogr.Geometry(ogr.wkbPoint); pt.AddPoint_2D(*p)
        if road.Contains(pt):                       # edge sits on the road: pull it back inward
            seg = road.Intersection(line([p, p - n * GROW]))
            far = [np.hypot(*(np.array(seg.GetPoint_2D(i)) - p)) for i in range(seg.GetPointCount())] if seg.GetGeometryType() == ogr.wkbLineString else []
            if far:
                hits.append(-max(far))
            continue
        seg = line([p, p + n * GROW]).Intersection(road)   # stops short: push out to the road
        if not seg.IsEmpty():
            env = seg.GetEnvelope()
            cand = [np.array((x, y)) for x in env[:2] for y in env[2:]]
            hits.append(min(np.dot(c - p, n) for c in cand))
    if len(hits) < HIT * k:
        return 0.0
    return float(np.median(hits))


def isect(p1, d1, p2, d2):
    m = np.array([d1, -d2]).T
    if abs(np.linalg.det(m)) < 1e-6:
        return (p1 + p2) / 2
    s, _ = np.linalg.solve(m, p2 - p1)
    return p1 + d1 * s


def polish(pts, move=True):
    P = np.array(pts, float)
    if move:
        base = poly(pts)
        n_ = len(P)
        shifted = []
        for i in range(n_):
            a, b = P[i], P[(i + 1) % n_]
            d = (b - a) / np.hypot(*(b - a)); n = np.array([d[1], -d[0]])
            mid = ogr.Geometry(ogr.wkbPoint); mid.AddPoint_2D(*((a + b) / 2 + n * 0.5))
            if base.Contains(mid):
                n = -n
            s = edge_shift(a, b, n, base) if np.hypot(*(b - a)) >= 10 else 0.0
            shifted.append((a + n * s, d))
        Q = []
        for i in range(n_):
            q = isect(*shifted[i - 1], *shifted[i])
            if np.hypot(*(q - P[i])) > GROW * 1.5:      # near-parallel edges: don't let the corner fly off
                q = P[i] + (shifted[i - 1][0] - P[i - 1]) / 2 + (shifted[i][0] - P[i]) / 2
            Q.append(q)
        P = np.array(Q)
    g = poly(P.tolist())
    if not g.IsValid():
        g = g.MakeValid().Buffer(0)
    g = g.Difference(road)
    if g.GetGeometryType() == ogr.wkbMultiPolygon:
        g = max((g.GetGeometryRef(i) for i in range(g.GetGeometryCount())), key=lambda x: x.GetArea()).Clone()
    g = g.SimplifyPreserveTopology(1.5)
    r = g.GetGeometryRef(0)
    return [r.GetPoint_2D(i) for i in range(r.GetPointCount() - 1)]


whole = {n: polish(p, move=n not in FIXED) for n, p in WHOLE.items()}
fields = {}
wg = [poly(p) for p in whole.values()]
for n, p in PLOTS.items():
    g = poly(polish(p, move=False))
    host = max(wg, key=lambda w: w.Intersection(g).GetArea())
    if host.Intersection(g).GetArea() > 0.5 * g.GetArea():   # keep each field inside its whole plot
        g = g.Intersection(host)
        if g.GetGeometryType() != ogr.wkbPolygon:
            g = max((g.GetGeometryRef(i) for i in range(g.GetGeometryCount())), key=lambda x: x.GetArea()).Clone()
    r = g.GetGeometryRef(0)
    fields[n] = [r.GetPoint_2D(i) for i in range(r.GetPointCount() - 1)]
out = {"whole": whole, "fields": fields}
json.dump(out, open("polished_px.json", "w"))
print(len(out["whole"]), "whole plots,", len(out["fields"]), "fields polished")
import sys; sys.stdout.flush(); os._exit(0)
