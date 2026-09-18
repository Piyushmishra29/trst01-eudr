"""One glTF model of the farm's 3D objects for Cesium: lobed tree crowns and gable/flat roofs textured by the drone photo,
trunks, palm fronds, plain walls. Local frame: x east, y up, z south, metres from the photo centre, ground at y = 0."""
import json, numpy as np, cv2, trimesh, pygltflib as G
from pyproj import Transformer
from geo import lonlat, A, ground
M = float(np.hypot(A[0, 0], A[1, 0]) * 0.5); DW, DH = 4032, 3024
_ecef = Transformer.from_crs(4326, 4978, always_xy=True)
lon0, lat0 = [float(v) for v in lonlat(DW / 2, DH / 2)]; o = np.array(_ecef.transform(lon0, lat0, 0.0))
la, lo = np.radians(lat0), np.radians(lon0)
R = np.array([[-np.sin(lo), np.cos(lo), 0], [-np.sin(la) * np.cos(lo), -np.sin(la) * np.sin(lo), np.cos(la)]])      # ECEF -> east, north
def en(u, v):
    lon, lat = lonlat(u, v); p = np.stack(_ecef.transform(lon, lat, np.zeros_like(np.asarray(lon, float))), -1) - o
    return p @ R.T
rnd = lambda a, b, c: (np.sin(a * 127.1 + b * 311.7 + c * 74.7) * 43758.5453) % 1.0
T = json.load(open("../ai3d/web/trees.json"))["trees"]; B = json.load(open("../ai3d/web/buildings.json"))["buildings"]
def main():
    ICO = {k: trimesh.creation.icosphere(subdivisions=k) for k in (1, 2)}                          # 42 or 162 verts a lobe, smooth shaded

    P, UV, COL, F = [], [], [], []                     # textured: crowns + roofs
    P2, COL2, F2 = [], [], []                          # plain coloured: trunks, walls, fronds
    def outward(p, f, c):
        """Flip triangles whose normal points toward c (the inside), so lighting is right whatever the mapping did to the winding."""
        p = np.asarray(p, float); f = np.array(f); n = np.cross(p[f[:, 1]] - p[f[:, 0]], p[f[:, 2]] - p[f[:, 0]]); m = p[f].mean(1) - c
        bad = (n * m).sum(1) < 0; f[bad] = f[bad][:, ::-1]; return f
    def add_tex(p, uv, col, f): F.append(f + sum(len(x) for x in P)); P.append(p); UV.append(uv); COL.append(col)
    def add_col(p, col, f): F2.append(f + sum(len(x) for x in P2)); P2.append(p); COL2.append(np.broadcast_to(col, (len(p), 3)).copy() if np.ndim(col) == 1 else col)
    def prism(cx, cz, r0, r1, y0, y1, n=6):
        a = np.arange(n) * 2 * np.pi / n; ring = np.c_[np.cos(a), np.sin(a)]
        p = np.r_[np.c_[cx + ring[:, 0] * r0, np.full(n, y0), cz + ring[:, 1] * r0], np.c_[cx + ring[:, 0] * r1, np.full(n, y1), cz + ring[:, 1] * r1]]
        f = np.array([[i, n + i, (i + 1) % n] for i in range(n)] + [[(i + 1) % n, n + i, n + (i + 1) % n] for i in range(n)]); return p, f

    for t, (cx, cy, rx, ry, ht, palm) in enumerate([]):          # trees now come from build_trees.py (instanced, realistic)
        rw = (rx + ry) / 2 * M; e0 = en(cx, cy); x0, z0 = e0[0], -e0[1]
        if palm:
            H = max(ht * 16, 2.2 * rw); L = rw * 1.05
            p, f = prism(x0, z0, 0.24, 0.17, -0.3, H); add_col(p, np.array([0.36, 0.28, 0.2]), f)
            for k in range(13):
                a = k / 13 * 6.2832 + rnd(t, k, 5) * 0.4; dx, dz = np.cos(a), np.sin(a); lift = 0.25 + 0.3 * rnd(t, k, 6); sh = 0.75 + 0.35 * rnd(t, k, 7)
                q = np.linspace(0, 1, 6); r = q * L; w = 0.16 * L * np.sin(np.pi * np.minimum(1, q * 0.9 + 0.1)); y = H + L * (lift * q - 0.75 * q * q)
                p = np.r_[np.c_[x0 + dx * r + dz * w, y, z0 + dz * r - dx * w], np.c_[x0 + dx * r - dz * w, y, z0 + dz * r + dx * w]]
                f = np.array([[i, 6 + i, i + 1] for i in range(5)] + [[i + 1, 6 + i, 7 + i] for i in range(5)]); add_col(p, np.array([0.30, 0.46, 0.20]) * sh, f)
            continue
        H = max(ht * 10, 1.5 * rw); half = min(0.38 * H, max(0.35 * H, 0.75 * rw)); low = H - 2 * half
        p, f = prism(x0, z0, min(0.45, 0.06 * rw + 0.1), min(0.45, 0.06 * rw + 0.1) * 0.7, -0.3, low + half * 0.6); add_col(p, np.array([0.36, 0.28, 0.2]), f)
        lobes = [(0, 0, 1, 0)] if (rx + ry) / 2 <= 26 else [(0, 0, 0.74, 0.22)] + [(np.cos(a) * o_, np.sin(a) * o_, 0.5 + 0.12 * rnd(t, k, 3), -0.28 + 0.2 * rnd(t, k, 4))
                 for k in range(4) for a, o_ in [(k * 1.571 + rnd(t, k, 1) * 1.2, 0.42 + 0.1 * rnd(t, k, 2))]]
        for li, (ox, oz, sc, yo) in enumerate(lobes):
            m_ = ICO[2 if len(lobes) == 1 and rw > 2.5 else 1]; IV, IF = m_.vertices, m_.faces       # only big single crowns get the finer sphere
            k = 0.86 + 0.28 * rnd(np.round(IV[:, 0] * 50) + t * 7 + li, np.round(IV[:, 1] * 50), np.round(IV[:, 2] * 50))
            s = np.c_[ox + IV[:, 0] * k * sc, yo + IV[:, 1] * k * sc, oz + IV[:, 2] * k * sc]
            e = en(cx + s[:, 0] * rx, cy + s[:, 2] * ry)
            p = np.c_[e[:, 0], low + half * (1 + s[:, 1]), -e[:, 1]]
            uv = np.c_[(cx + s[:, 0] * rx * 0.62) / DW, (cy + s[:, 2] * ry * 0.62) / DH]              # glTF v runs down, like the image
            c = 0.5 + 0.5 * np.clip((s[:, 1] + 1) / 1.6, 0, 1); add_tex(p, uv, np.c_[c, c, c] * np.array([1.0, 1.06, 0.96]), outward(p, IF, p.mean(0)))

    WALL = np.array([0.85, 0.83, 0.79])
    for b in B:
        poly = np.array(b["poly"], float); gh = ground(poly[:, 0], poly[:, 1]); g0 = float(gh.min()); h = g0 + (gh.max() - g0) + (0.25 + 0.6 * b["h"]) * 10; e = en(poly[:, 0], poly[:, 1]); w = np.c_[e[:, 0], -e[:, 1]]; n = len(poly); ctr = np.array([w[:, 0].mean(), (g0 + h) / 2, w[:, 1].mean()])
        for i in range(n):                              # walls, one quad per edge (own vertices: crisp corners)
            j = (i + 1) % n; add_col(np.array([[w[i, 0], h, w[i, 1]], [w[j, 0], h, w[j, 1]], [w[i, 0], g0 - 0.5, w[i, 1]], [w[j, 0], g0 - 0.5, w[j, 1]]]), WALL, outward(np.array([[w[i, 0], h, w[i, 1]], [w[j, 0], h, w[j, 1]], [w[i, 0], g0 - 0.5, w[i, 1]], [w[j, 0], g0 - 0.5, w[j, 1]]]), [[0, 1, 2], [2, 1, 3]], ctr))
        if b["roof"] == "gable":
            if np.hypot(*(w[0] - w[1])) < np.hypot(*(w[1] - w[2])): poly, w = np.roll(poly, -1, 0), np.roll(w, -1, 0)
            rh = h + 0.2 * np.hypot(*(w[1] - w[2])); mp = lambda a_, i, j: (a_[i] + a_[j]) / 2
            R6 = np.r_[w, [mp(w, 1, 2)], [mp(w, 3, 0)]]; U6 = np.r_[poly, [mp(poly, 1, 2)], [mp(poly, 3, 0)]]; Y6 = np.array([h, h, h, h, rh, rh])
            for tri in ([0, 1, 4], [0, 4, 5], [2, 3, 5], [2, 5, 4]):   # each roof face gets its own vertices: flat shaded
                pp = np.c_[R6[tri, 0], Y6[tri], R6[tri, 1]]; add_tex(pp, U6[tri] / [DW, DH], np.ones((3, 3)), outward(pp, [[0, 1, 2]], ctr))
            for tri in ([1, 2, 4], [3, 0, 5]): pp = np.c_[R6[tri, 0], Y6[tri], R6[tri, 1]]; add_col(pp, WALL, outward(pp, [[0, 1, 2]], ctr))
        else:
            tris = trimesh.creation.triangulate_polygon(__import__("shapely.geometry", fromlist=["Polygon"]).Polygon(poly), engine="earcut")
            tv, tf = tris; e2 = en(tv[:, 0], tv[:, 1]); pp = np.c_[e2[:, 0], np.full(len(tv), h), -e2[:, 1]]; add_tex(pp, tv / [DW, DH], np.ones((len(tv), 3)), outward(pp, tf, ctr))

    def normals(p, f):
        n = trimesh.Trimesh(p, f, process=False).vertex_normals.copy(); bad = np.linalg.norm(n, axis=1) < 0.5; n[bad] = [0, 1, 0]; return n     # materials are double sided, so winding doesn't matter
    P, UV, COL, F = np.concatenate(P).astype(np.float32), np.concatenate(UV).astype(np.float32), np.concatenate(COL).astype(np.float32), np.concatenate(F).astype(np.uint32)
    P2, COL2, F2 = np.concatenate(P2).astype(np.float32), np.concatenate(COL2).astype(np.float32), np.concatenate(F2).astype(np.uint32)
    N, N2 = normals(P, F).astype(np.float32), normals(P2, F2).astype(np.float32)
    tex = cv2.imencode(".jpg", cv2.resize(cv2.convertScaleAbs(cv2.imread("../ai3d/web/tex_hd.jpg"), alpha=1.12, beta=4), (2048, 1536), interpolation=cv2.INTER_AREA), [1, 85])[1].tobytes()

    blob = bytearray(); views, accs = [], []
    def put(arr, target=None, ctype=G.FLOAT, typ=G.VEC3, mm=False):
        while len(blob) % 4: blob.append(0)
        b_ = arr.tobytes(); views.append(G.BufferView(buffer=0, byteOffset=len(blob), byteLength=len(b_), target=target)); blob.extend(b_)
        accs.append(G.Accessor(bufferView=len(views) - 1, componentType=ctype, count=len(arr), type=typ, normalized=(ctype == G.UNSIGNED_BYTE), min=arr.min(0).tolist() if mm else None, max=arr.max(0).tolist() if mm else None)); return len(accs) - 1
    a = [put(P, G.ARRAY_BUFFER, mm=True), put(N, G.ARRAY_BUFFER), put(UV, G.ARRAY_BUFFER, typ=G.VEC2), put(np.c_[np.clip(COL, 0, 1) * 255, np.full(len(COL), 255)].astype(np.uint8), G.ARRAY_BUFFER, G.UNSIGNED_BYTE, G.VEC4), put(F.reshape(-1), G.ELEMENT_ARRAY_BUFFER, G.UNSIGNED_INT, G.SCALAR)]
    c = [put(P2, G.ARRAY_BUFFER, mm=True), put(N2, G.ARRAY_BUFFER), put(np.c_[np.clip(COL2, 0, 1) * 255, np.full(len(COL2), 255)].astype(np.uint8), G.ARRAY_BUFFER, G.UNSIGNED_BYTE, G.VEC4), put(F2.reshape(-1), G.ELEMENT_ARRAY_BUFFER, G.UNSIGNED_INT, G.SCALAR)]
    while len(blob) % 4: blob.append(0)
    views.append(G.BufferView(buffer=0, byteOffset=len(blob), byteLength=len(tex))); blob.extend(tex)
    g = G.GLTF2(scene=0, scenes=[G.Scene(nodes=[0])], nodes=[G.Node(mesh=0)], buffers=[G.Buffer(byteLength=len(blob))], bufferViews=views, accessors=accs,
        images=[G.Image(bufferView=len(views) - 1, mimeType="image/jpeg")], samplers=[G.Sampler(magFilter=G.LINEAR, minFilter=G.LINEAR_MIPMAP_LINEAR)], textures=[G.Texture(source=0, sampler=0)],
        materials=[G.Material(pbrMetallicRoughness=G.PbrMetallicRoughness(baseColorTexture=G.TextureInfo(index=0), metallicFactor=0, roughnessFactor=1), doubleSided=True),
                   G.Material(pbrMetallicRoughness=G.PbrMetallicRoughness(metallicFactor=0, roughnessFactor=1), doubleSided=True)],
        meshes=[G.Mesh(primitives=[G.Primitive(attributes=G.Attributes(POSITION=a[0], NORMAL=a[1], TEXCOORD_0=a[2], COLOR_0=a[3]), indices=a[4], material=0),
                                   G.Primitive(attributes=G.Attributes(POSITION=c[0], NORMAL=c[1], COLOR_0=c[2]), indices=c[3], material=1)])])
    g.set_binary_blob(bytes(blob)); g.save_binary("web/farm.glb")
    json.dump(dict(lon=lon0, lat=lat0), open("web/farm.json", "w")); print(len(P), "+", len(P2), "verts,", round(len(blob) / 1e6, 1), "MB")

if __name__ == "__main__":
    main()
