"""Realistic instanced trees for Cesium (web/trees.glb): trunk + branches + alpha leaf cards, the way game foliage is built.
Species: broadleaf (mango-like, 4 shapes x 3 leaf tints), coconut palm, areca palm. One glTF node per prototype with
EXT_mesh_gpu_instancing, so 854 trees cost a few thousand vertices. Leaf, frond and bark textures are drawn here (no third-party assets)."""
import json, numpy as np, cv2, pygltflib as G
from build_model import en, M, T
from geo import ground
rng = np.random.default_rng(7)

# ---------- textures
def leaf_poly(c, L, W, ang, n=9):
    t = np.linspace(0, 1, n); w = W * np.sin(np.pi * t ** 0.8) * (1 - 0.35 * t); up = np.c_[t * L, w]; dn = np.c_[t[::-1] * L, -w[::-1]]
    p = np.r_[up, dn]; R = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]]); return (p @ R.T + c).astype(np.int32)
def leaf_atlas(S=1024):                                   # 2 x 2 clusters of lance-shaped leaves, RGBA
    img = np.zeros((S, S, 4), np.uint8); h = S // 2
    for ty in range(2):
        for tx in range(2):
            c0 = np.array([tx * h + h / 2, ty * h + h / 2]); n = 70
            for k in range(n):
                d = k / n; ang = rng.uniform(0, 6.283); base = c0 + rng.normal(0, h * 0.13, 2) * (1 - 0.3 * d); L = h * rng.uniform(0.2, 0.3); W = L * rng.uniform(0.13, 0.19)
                tip = base + L * np.array([np.cos(ang), np.sin(ang)])
                if np.abs(tip - c0).max() > h * 0.47: continue
                v = 0.45 + 0.55 * d + rng.uniform(-0.08, 0.08)             # later leaves sit on top and catch more light
                col = np.array([36 + 26 * v, 66 + 58 * v, 44 + 40 * v]) * rng.uniform(0.9, 1.1)      # BGR: deep, slightly olive green
                pts = leaf_poly(base, L, W, ang); cv2.fillPoly(img, [pts], (*[int(x) for x in np.clip(col, 0, 255)], 255), cv2.LINE_AA)
                cv2.line(img, tuple(base.astype(int)), tuple(tip.astype(int)), (*[int(x) for x in np.clip(col * 1.25 + 12, 0, 255)], 255), 1, cv2.LINE_AA)
    img[..., :3] = cv2.GaussianBlur(img[..., :3], (0, 0), 0.7); return img
def frond_tex(Wd=1024, Hd=256):                           # one palm frond: rachis + leaflets, RGBA
    img = np.zeros((Hd, Wd, 4), np.uint8); cy = Hd / 2
    for k in range(64):
        t = 0.06 + 0.92 * k / 63; x = t * Wd; L = Hd * 0.47 * np.sin(np.pi * min(1, t * 0.85 + 0.12)) ** 0.7
        for sgn in (-1, 1):
            a = sgn * np.radians(rng.uniform(52, 66)); col = np.array([40, 104, 74]) * rng.uniform(0.8, 1.15) + np.array([0, 16, 18]) * t
            cv2.fillPoly(img, [leaf_poly(np.array([x, cy]), L, L * 0.06, a)], (*[int(v) for v in np.clip(col, 0, 255)], 255), cv2.LINE_AA)
    cv2.line(img, (0, int(cy)), (Wd - 8, int(cy)), (70, 140, 120, 255), 5, cv2.LINE_AA); return img
def bark_tex(S=128):
    n = rng.normal(0, 1, (S, S // 8)); n = cv2.resize(n.astype(np.float32), (S, S), interpolation=cv2.INTER_CUBIC); n = cv2.GaussianBlur(n, (0, 0), 1) + rng.normal(0, 0.35, (S, S))
    g = np.clip(0.5 + 0.18 * n, 0, 1)[..., None]; return (g * np.array([70, 100, 128]) + (1 - g) * np.array([28, 40, 52])).astype(np.uint8)
png = lambda im: cv2.imencode(".png", im)[1].tobytes()
cv2.imwrite("work/leaf_atlas.png", leaf_atlas()); cv2.imwrite("work/frond.png", frond_tex())

# ---------- prototype meshes (unit tree: x, z in crown radii; y in tree heights)
class Mesh:
    def __init__(s): s.p, s.n, s.uv, s.f = [], [], [], []
    def add(s, p, n, uv, f): o = sum(len(x) for x in s.p); s.p.append(np.asarray(p, np.float32)); s.n.append(np.asarray(n, np.float32)); s.uv.append(np.asarray(uv, np.float32)); s.f.append(np.asarray(f, np.uint32) + o)
    def arrays(s): n = np.concatenate(s.n); n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-9; return np.concatenate(s.p), n.astype(np.float32), np.concatenate(s.uv), np.concatenate(s.f).reshape(-1)
def tube(m, pts, radii, k=6):                             # tapered tube along a polyline
    pts = np.asarray(pts, float); a = np.arange(k + 1) * 2 * np.pi / k
    for i in range(len(pts) - 1):
        d = pts[i + 1] - pts[i]; d /= np.linalg.norm(d); u = np.cross(d, [0.3, 0.1, 1]); u /= np.linalg.norm(u); v = np.cross(d, u)
        ring = lambda c, r: c + r * (np.outer(np.cos(a), u) + np.outer(np.sin(a), v)); nr = np.outer(np.cos(a), u) + np.outer(np.sin(a), v)
        p = np.r_[ring(pts[i], radii[i]), ring(pts[i + 1], radii[i + 1])]; uv = np.r_[np.c_[a / 6.283 * 2, np.full(k + 1, i * 1.5)], np.c_[a / 6.283 * 2, np.full(k + 1, (i + 1) * 1.5)]]
        f = [[j, j + 1, k + 1 + j] for j in range(k)] + [[j + 1, k + 2 + j, k + 1 + j] for j in range(k)]; m.add(p, np.r_[nr, nr], uv, f)
def broadleaf(seed, squat=1.0):
    r = np.random.default_rng(seed); wood, leaf = Mesh(), Mesh(); cy, ry = 0.64, 0.36 * squat
    tube(wood, [[0, -0.03, 0], [r.normal(0, .02), 0.22, r.normal(0, .02)], [r.normal(0, .03), 0.46, r.normal(0, .03)]], [0.075, 0.055, 0.04])
    for b in range(4):
        a = b * 1.57 + r.uniform(0, 1); tube(wood, [[0, 0.3 + 0.04 * b, 0], [0.3 * np.cos(a), 0.5, 0.3 * np.sin(a)], [0.62 * np.cos(a), 0.62 + r.uniform(-.05, .08), 0.62 * np.sin(a)]], [0.035, 0.022, 0.008], 4)
    for k in range(120):
        d = r.normal(size=3); d /= np.linalg.norm(d); d[1] = abs(d[1]) * 0.9 - 0.25 if k % 3 else d[1]; d /= np.linalg.norm(d)
        rad = r.uniform(0.55, 0.98) * (1 + 0.12 * np.sin(5 * np.arctan2(d[2], d[0]) + seed)); c = np.array([d[0] * rad, cy + d[1] * rad * ry, d[2] * rad])
        s_ = r.uniform(0.34, 0.5); t1 = np.cross(d, r.normal(size=3)); t1 /= np.linalg.norm(t1); t2 = np.cross(d, t1)
        if k % 4 == 0: t1, t2 = np.array([1.0, 0, 0]), np.array([0, 0, 1.0])                  # some flat cards: the crown stays full seen from above
        t1, t2 = t1 * s_, t2 * s_ * np.array([1, 0.55, 1])                                     # y is in tree heights (about 1.8 crown radii)
        tx, ty = r.integers(0, 2, 2) * 0.5; e = 0.02
        nrm = d * np.array([1, 1 / ry * 0.5, 1]) + np.array([0, 0.35, 0])                       # "ball" normals: soft, volumetric shading
        leaf.add([c - t1 - t2, c + t1 - t2, c + t1 + t2, c - t1 + t2], [nrm] * 4, [[tx + e, ty + e], [tx + .5 - e, ty + e], [tx + .5 - e, ty + .5 - e], [tx + e, ty + .5 - e]], [[0, 1, 2], [0, 2, 3]])
    return wood, leaf
def palm(seed, fronds=17, top=0.84, lean=0.12, droop=1.0, trunk_r=0.05):
    r = np.random.default_rng(seed); wood, leaf = Mesh(), Mesh(); la = r.uniform(0, 6.28)
    sp = [[lean * np.cos(la) * t ** 2, top * t - 0.03, lean * np.sin(la) * t ** 2] for t in np.linspace(0, 1, 6)]; tube(wood, sp, np.linspace(trunk_r * 1.35, trunk_r * 0.8, 6)); tp = np.array(sp[-1])
    for k in range(fronds):
        a = k / fronds * 6.283 + r.uniform(-.2, .2); lift = (0.5 if k % 2 else 0.18) + r.uniform(-.06, .06); dx, dz = np.cos(a), np.sin(a); q = np.linspace(0, 1, 7)
        rr = q * (1.0 if k % 2 == 0 else 0.8); y = tp[1] + 0.02 + (lift * q - droop * (0.42 + 0.2 * (k % 2 == 0)) * q ** 2) * 0.55; w = 0.2
        L_ = np.c_[tp[0] + dx * rr + dz * w, y - 0.03 * (q > 0), tp[2] + dz * rr - dx * w]; R_ = np.c_[tp[0] + dx * rr - dz * w, y - 0.03 * (q > 0), tp[2] + dz * rr + dx * w]
        leaf.add(np.r_[L_, R_], [[dx * 0.3, 1, dz * 0.3]] * 14, np.r_[np.c_[q, np.zeros(7)], np.c_[q, np.ones(7)]], [[i, i + 1, 7 + i] for i in range(6)] + [[i + 1, 8 + i, 7 + i] for i in range(6)])
    return wood, leaf

# ---------- instances
blocks = json.load(open("web/data.json"))["blocks"]; im = cv2.imread("../ai3d/web/tex_hd.jpg")
AREC = [np.float32(b_["ring"]) for b_ in blocks if b_["crop"] == "areca"]; d_ll = json.load(open("web/data.json"))["trees"]
val = np.array([max(t[5:8]) for t in d_ll]); q1, q2 = np.quantile(val, [0.35, 0.75])
TINT = [(0.78, 0.84, 0.72), (0.92, 0.98, 0.8), (1.0, 1.0, 0.78)]                              # dark mango green, mid, light / young
protos = {}                                                 # key -> (wood, leaf, leaf material, [instances])
for s_ in range(4):
    for ti in range(3): protos[("b", s_, ti)] = (*broadleaf(11 + s_, [1, 1.15, 0.85, 1][s_]), ("leaf", ti), [])
protos[("coco",)] = (*palm(3), ("frond", 1), []); protos[("areca",)] = (*palm(5, fronds=10, top=0.8, lean=0.03, droop=0.8, trunk_r=0.035), ("frond", 1), [])
for i, (cx, cy, rx, ry, ht, pm) in enumerate(T):
    rw = (rx + ry) / 2 * M; e = en(cx, cy); pos = [float(e[0]), float(ground(cx, cy)) - 0.15, float(-e[1])]; ang = rnd_ = float(rng.uniform(0, 6.283)); rot = [0, np.sin(ang / 2), 0, np.cos(ang / 2)]
    in_areca = any(cv2.pointPolygonTest(a_, (d_ll[i][0], d_ll[i][1]), False) >= 0 for a_ in AREC)
    if pm: H = max(ht * 16, 2.4 * rw); protos[("coco",)][3].append((pos, rot, [rw * 1.15, H / 0.84 * 0.9, rw * 1.15]))
    elif in_areca and rw < 2.6: H = max(ht * 12, 2.6 * rw); protos[("areca",)][3].append((pos, rot, [rw * 1.2, H, rw * 1.2]))
    else:
        H = max(ht * 10, 1.55 * rw); ti = 0 if val[i] < q1 else 1 if val[i] < q2 else 2
        protos[("b", i % 4, ti)][3].append((pos, rot, [rw * 1.12, H, rw * 1.12]))
# every counted orchard plant gets a tree too (the crown detector only finds the big, separate trees)
from scipy.spatial import cKDTree
kd = cKDTree(np.array([[t[0], t[1]] for t in T])); extra = 0
for x, y, crop in json.load(open("work/block_plants.json")):
    if kd.query([x, y])[0] * M < (2.0 if crop == "mango" else 1.2): continue
    e = en(x, y); pos = [float(e[0]), float(ground(x, y)) - 0.15, float(-e[1])]; ang = float(rng.uniform(0, 6.283)); rot = [0, np.sin(ang / 2), 0, np.cos(ang / 2)]; extra += 1
    if crop == "mango": rw = rng.uniform(1.5, 2.3); protos[("b", int(rng.integers(0, 4)), 0 if rng.uniform() < 0.7 else 1)][3].append((pos, rot, [rw, rw * rng.uniform(1.5, 1.9), rw]))
    else: rw = rng.uniform(0.9, 1.4); protos[("areca",)][3].append((pos, rot, [rw, rw * rng.uniform(2.4, 3.2), rw]))
json.dump(dict(detected=len(T), orchard=extra, total=len(T) + extra), open("web/tree_count.json", "w"))
print({("-".join(map(str, k))): len(v[3]) for k, v in protos.items()}, "extra orchard plants:", extra)

# ---------- glTF
blob = bytearray(); views, accs = [], []
def put(arr, target=None, ctype=G.FLOAT, typ=G.VEC3, mm=False):
    while len(blob) % 4: blob.append(0)
    b_ = np.ascontiguousarray(arr).tobytes(); views.append(G.BufferView(buffer=0, byteOffset=len(blob), byteLength=len(b_), target=target)); blob.extend(b_)
    accs.append(G.Accessor(bufferView=len(views) - 1, componentType=ctype, count=len(arr), type=typ, min=arr.min(0).tolist() if mm else None, max=arr.max(0).tolist() if mm else None)); return len(accs) - 1
def put_img(data):
    while len(blob) % 4: blob.append(0)
    views.append(G.BufferView(buffer=0, byteOffset=len(blob), byteLength=len(data))); blob.extend(data); return len(views) - 1
imgs = [G.Image(bufferView=put_img(png(leaf_atlas())), mimeType="image/png"), G.Image(bufferView=put_img(png(frond_tex())), mimeType="image/png"), G.Image(bufferView=put_img(png(bark_tex())), mimeType="image/png")]
mats, mat_ix = [], {}
def mat(kind, ti):
    if (kind, ti) not in mat_ix:
        tex = dict(leaf=0, frond=1, bark=2)[kind]; f = [*(min(1.0, c_) for c_ in (TINT[ti] if kind != "bark" else (1, 1, 1))), 1.0]
        mats.append(G.Material(pbrMetallicRoughness=G.PbrMetallicRoughness(baseColorTexture=G.TextureInfo(index=tex), baseColorFactor=f, metallicFactor=0, roughnessFactor=0.85 if kind != "bark" else 1),
                               doubleSided=True, alphaMode="MASK" if kind != "bark" else "OPAQUE", alphaCutoff=0.45 if kind != "bark" else None)); mat_ix[(kind, ti)] = len(mats) - 1
    return mat_ix[(kind, ti)]
nodes, meshes = [], []
for key, (wood, leaf, lm, inst) in protos.items():
    if not inst: continue
    prims = []
    for m_, mt in ((wood, mat("bark", 0)), (leaf, mat(*lm))):
        p, n, uv, f = m_.arrays(); prims.append(G.Primitive(attributes=G.Attributes(POSITION=put(p, G.ARRAY_BUFFER, mm=True), NORMAL=put(n, G.ARRAY_BUFFER), TEXCOORD_0=put(uv, G.ARRAY_BUFFER, typ=G.VEC2)), indices=put(f, G.ELEMENT_ARRAY_BUFFER, G.UNSIGNED_INT, G.SCALAR), material=mt))
    meshes.append(G.Mesh(primitives=prims)); tr, ro, sc = [np.array([x[j] for x in inst], np.float32) for j in range(3)]
    nodes.append(G.Node(mesh=len(meshes) - 1, extensions={"EXT_mesh_gpu_instancing": {"attributes": {"TRANSLATION": put(tr), "ROTATION": put(ro, typ=G.VEC4), "SCALE": put(sc)}}}))
g = G.GLTF2(scene=0, scenes=[G.Scene(nodes=list(range(len(nodes))))], nodes=nodes, meshes=meshes, materials=mats, images=imgs, samplers=[G.Sampler(magFilter=G.LINEAR, minFilter=G.LINEAR_MIPMAP_LINEAR, wrapS=G.REPEAT, wrapT=G.REPEAT)],
            textures=[G.Texture(source=i, sampler=0) for i in range(3)], buffers=[G.Buffer(byteLength=len(blob))], bufferViews=views, accessors=accs, extensionsUsed=["EXT_mesh_gpu_instancing"], extensionsRequired=["EXT_mesh_gpu_instancing"])
g.set_binary_blob(bytes(blob)); g.save_binary("web/trees.glb"); print(round(len(blob) / 1e6, 2), "MB")
