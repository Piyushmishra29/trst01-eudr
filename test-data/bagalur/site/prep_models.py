"""Small-object models for the site page, from Poly Haven scans (polyhaven.com, CC0). Three steps:
  python3 prep_models.py rgba            -> work/ph/<asset>/rgba.png        (colour map + its separate alpha map in one image, so Blender can cut the leaves out)
  blender -b --python prep_models.py     -> work/models_raw.json            (stones cut down to ~100 triangles, base on the ground, 1 = footprint radius)
                                            work/cards/<plant>_{a,b,t}.png  (each scanned plant rendered front, side and top: picture cards. Cutting a 6000-triangle plant to 200 leaves only a few stray leaves; its picture keeps all of it)
  python3 prep_models.py                 -> web/models.json + web/models_atlas.webp   (one sheet: stone colour maps, plant cards, a plain cell; colours evened out so the photo can tint them)
Source files sit in work/ph/<asset>/ (gltf + colour map + alpha map), fetched from api.polyhaven.com/files/<asset>."""
import json, sys, os, math
ASSETS = ["rock_07", "rock_09", "stone_01", "namaqualand_stones_01", "shrub_02", "shrub_03", "wild_rooibos_bush", "fern_02", "nettle_plant", "grass_medium_01", "weed_plant_02"]
# kind 0 stone (mesh, triangle budget), 1 low bush, 2 tuft (picture cards)
STONES = {"rock_07": 120, "rock_09": 110, "stone_01": 120, "namaqualand_stones_01_b": 100, "namaqualand_stones_01_d": 90, "namaqualand_stones_01_e": 110}
PLANTS = {"wild_rooibos_bush_a": 1, "wild_rooibos_bush_b": 1, "wild_rooibos_bush_c": 1, "wild_rooibos_bush_d": 1, "fern_02_b": 1, "fern_02_c": 1, "shrub_02_a": 1, "shrub_02_c": 1,
          "grass_medium_01_large_a": 2, "grass_medium_01_large_b": 2, "grass_medium_01_mid_a": 2, "grass_medium_01_mid_b": 2, "grass_medium_01_tall_a": 2, "weed_plant_02_a": 2, "weed_plant_02_b": 2, "shrub_03_a": 2, "shrub_03_b": 2, "nettle_plant_tall_a": 2}
PICK = {**{k: (0, v) for k, v in STONES.items()}, **{k: (v, 0) for k, v in PLANTS.items()}}; RES = 384
try: import bpy, bmesh
except ImportError: bpy = None

if bpy:
    out = []
    for a in ASSETS:
        bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=f"work/ph/{a}/{a}.gltf")
        for o in list(bpy.data.objects):
            key = next((k for k in PICK if o.type == "MESH" and (o.name == k or o.name.startswith(k + "_LOD") or o.name == k + "_LOD0")), None)
            if not key: continue
            kind, budget = PICK[key]; bpy.ops.object.select_all(action="DESELECT"); o.select_set(True); bpy.context.view_layer.objects.active = o
            o.parent = None; bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
            if kind:                                                                         # a plant: three pictures of the full scan, lit softly from above so it sits under any sun
                for q in bpy.data.objects: q.hide_render = q is not o
                for mt in o.data.materials:
                    mt.use_nodes = True; nt = mt.node_tree; nt.nodes.clear(); im = nt.nodes.new("ShaderNodeTexImage"); im.image = bpy.data.images.load(os.path.abspath(f"work/ph/{a}/rgba.png")); df = nt.nodes.new("ShaderNodeBsdfDiffuse"); tr = nt.nodes.new("ShaderNodeBsdfTransparent"); mx = nt.nodes.new("ShaderNodeMixShader"); ou = nt.nodes.new("ShaderNodeOutputMaterial")
                    nt.links.new(im.outputs["Color"], df.inputs["Color"]); nt.links.new(im.outputs["Alpha"], mx.inputs[0]); nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(df.outputs[0], mx.inputs[2]); nt.links.new(mx.outputs[0], ou.inputs["Surface"])
                W = [o.matrix_world @ v.co for v in o.data.vertices]; cx = (min(v.x for v in W) + max(v.x for v in W)) / 2; cy = (min(v.y for v in W) + max(v.y for v in W)) / 2; z0 = min(v.z for v in W); H = max(v.z for v in W) - z0
                R = sorted(math.hypot(v.x - cx, v.y - cy) for v in W)[int(len(W) * 0.985)]; L = max(2 * R, H) * 1.04       # 98.5 %: one stray stem should not shrink the whole plant in its frame
                sc = bpy.context.scene; sc.render.engine = "CYCLES"; sc.cycles.samples = 24; sc.cycles.use_denoising = False; sc.render.film_transparent = True; sc.view_settings.view_transform = "Standard"; sc.render.resolution_x = sc.render.resolution_y = RES; sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
                if not sc.world: sc.world = bpy.data.worlds.new("w")
                sc.world.use_nodes = True; bg = sc.world.node_tree.nodes.get("Background") or sc.world.node_tree.nodes.new("ShaderNodeBackground"); bg.inputs[0].default_value = (1, 1, 1, 1); bg.inputs[1].default_value = 1.1
                sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 1.6; sun.data.angle = 0.6; sc.collection.objects.link(sun)
                cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); cam.data.type = "ORTHO"; cam.data.clip_end = 100; sc.collection.objects.link(cam); sc.camera = cam; os.makedirs("work/cards", exist_ok=True)
                for tag, loc, rot, scale in [("a", (cx, cy - 20, z0 + L / 2), (math.pi / 2, 0, 0), L), ("b", (cx + 20, cy, z0 + L / 2), (math.pi / 2, 0, math.pi / 2), L), ("t", (cx, cy, z0 + 20), (0, 0, 0), 2 * R * 1.04)]:
                    if tag == "t" and kind != 1: continue
                    cam.location = loc; cam.rotation_euler = rot; cam.data.ortho_scale = scale; sc.render.filepath = os.path.abspath(f"work/cards/{key}_{tag}.png"); bpy.ops.render.render(write_still=True)
                out.append(dict(name=key, asset=a, kind=kind, side=L / R, top=2.08, height=H / R)); print("PLANT", key, "radius %.2f m, height %.2f m" % (R, H)); bpy.data.objects.remove(sun); bpy.data.objects.remove(cam); continue
            m = o.modifiers.new("tri", "TRIANGULATE"); bpy.ops.object.modifier_apply(modifier=m.name); n0 = len(o.data.polygons)
            first = budget if kind == 0 else budget * 3                                     # plants: thin the mesh a little, then keep the biggest leaves whole rather than shrinking every leaf
            if n0 > first: m = o.modifiers.new("dec", "DECIMATE"); m.ratio = first / n0; m.use_collapse_triangulate = True; bpy.ops.object.modifier_apply(modifier=m.name)
            bm = bmesh.new(); bm.from_mesh(o.data); bm.faces.ensure_lookup_table()
            if kind and len(bm.faces) > budget:
                seen = set(); isl = []
                for f in bm.faces:
                    if f.index in seen: continue
                    st = [f]; seen.add(f.index); grp = []
                    while st:
                        g = st.pop(); grp.append(g)
                        for e in g.edges:
                            for h in e.link_faces:
                                if h.index not in seen: seen.add(h.index); st.append(h)
                    isl.append(grp)
                isl.sort(key=lambda g: -sum(f.calc_area() for f in g)); keep = []; n = 0
                for g in isl:
                    if n + len(g) > budget and keep: continue
                    keep += g; n += len(g)
                    if n >= budget: break
                ks = set(f.index for f in keep); bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in ks], context="FACES")
            uvl = bm.loops.layers.uv.active; vs = [v.co.copy() for v in bm.verts]
            cx = (min(v.x for v in vs) + max(v.x for v in vs)) / 2; cy = (min(v.y for v in vs) + max(v.y for v in vs)) / 2; z0 = min(v.z for v in vs); rad = max(math.hypot(v.x - cx, v.y - cy) for v in vs) or 1
            top = max(v.z for v in vs) - z0; P, N, UV, I = [], [], [], []; bm.normal_update()
            for f in bm.faces:                                                               # Blender is z-up; the page is y-up with z towards the viewer
                for l in f.loops:
                    c = l.vert.co; x, y, z = (c.x - cx) / rad, (c.z - z0) / rad, -(c.y - cy) / rad
                    if kind: nx, ny, nz = x, 0.6 + y / max(top / rad, 1e-3), z                # foliage: lit as one soft dome, so single leaves do not flash
                    else: nx, ny, nz = l.vert.normal.x, l.vert.normal.z, -l.vert.normal.y
                    ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1; u, v = l[uvl].uv
                    I.append(len(P) // 3); P += [x, y, z]; N += [nx / ln, ny / ln, nz / ln]; UV += [u, v]
            out.append(dict(name=key, asset=a, kind=kind, tris=len(bm.faces), from_tris=n0, height=top / rad, p=P, n=N, uv=UV)); print("MODEL", key, n0, "->", len(bm.faces), "tris, height/radius %.2f" % (top / rad)); bm.free()
    json.dump(out, open("work/models_raw.json", "w")); sys.exit()

import numpy as np, cv2
from PIL import Image
PLANT_ASSETS = sorted(set(a for a in ASSETS for k in PLANTS if k.startswith(a)))
if sys.argv[1:] == ["rgba"]:
    for a in PLANT_ASSETS: d = Image.open(f"work/ph/{a}/textures/{a}_diff_1k.jpg").convert("RGB"); d.putalpha(Image.open(f"work/ph/{a}/textures/{a}_alpha_1k.png").convert("L").resize(d.size)); d.save(f"work/ph/{a}/rgba.png")
    sys.exit()
def even(rgb, on, keep=0.5, to=200):                                                      # keep the scan's detail and half its colour; the photo supplies the hue
    lum = rgb.mean(2, keepdims=True); rgb = lum + (rgb - lum) * keep; return np.clip(rgb / rgb[on].mean(0) * to, 0, 255)
def bleed(rgb, on):                                                                       # push leaf colour outwards so edges do not pick up a dark fringe when the sheet is shrunk
    m = on.astype(np.uint8); fill = rgb.copy()
    for _ in range(10): d = cv2.dilate(m, np.ones((3, 3), np.uint8)); b = cv2.blur(fill * m[..., None], (3, 3)) / np.maximum(cv2.blur(m.astype(np.float32), (3, 3)), 1e-3)[..., None]; new = (d > 0) & (m == 0); fill[new] = b[new]; m = d
    return fill
raw = json.load(open("work/models_raw.json")); SIZE, BIG, SMALL, PAD = 2048, 512, 256, 4; sheet = Image.new("RGBA", (SIZE, SIZE), (150, 150, 140, 0)); STONE_ASSETS = [a for a in ASSETS if any(k.startswith(a) for k in STONES)]; models = []
for k, a in enumerate(STONE_ASSETS):                                                      # top row: the stones' own colour maps
    rgb = np.asarray(Image.open(f"work/ph/{a}/textures/{a}_diff_1k.jpg").convert("RGB").resize((BIG - 2 * PAD,) * 2, Image.LANCZOS)).astype(np.float32); on = np.ones(rgb.shape[:2], bool)
    cell = np.dstack([even(rgb, on, 0.6, 205), np.full(rgb.shape[:2], 255)]); big = cv2.copyMakeBorder(cell, PAD, PAD, PAD, PAD, cv2.BORDER_REPLICATE); sheet.paste(Image.fromarray(big.astype(np.uint8), "RGBA"), (k * BIG, 0))
slot = 0
def place(path):
    global slot; im = np.asarray(Image.open(path).convert("RGBA").resize((SMALL - 2 * PAD,) * 2, Image.LANCZOS)).astype(np.float32); on = im[..., 3] > 100; rgb = bleed(even(im[..., :3], on), on)
    x, y = slot % 8 * SMALL, BIG + slot // 8 * SMALL; slot += 1; sheet.paste(Image.fromarray(np.dstack([rgb, im[..., 3]]).astype(np.uint8), "RGBA"), (x + PAD, y + PAD)); return [round((x + PAD) / SIZE, 5), round(1 - (y + SMALL - PAD) / SIZE, 5), round((x + SMALL - PAD) / SIZE, 5), round(1 - (y + PAD) / SIZE, 5)]   # u0, v0 (bottom), u1, v1 (top)
for m in raw:
    if m["kind"] == 0:
        k = STONE_ASSETS.index(m["asset"]); uv = np.array(m["uv"]).reshape(-1, 2); uv = uv - np.floor(uv.min(0)); u = (k * BIG + PAD + np.clip(uv[:, 0], 0, 1) * (BIG - 2 * PAD)) / SIZE; v = (PAD + np.clip(uv[:, 1], 0, 1) * (BIG - 2 * PAD)) / SIZE   # glTF v runs down the image, as the sheet does
        models.append(dict(name=m["name"], kind=0, h=round(m["height"], 3), p=[round(c * 1000) for c in m["p"]], n=[round(c * 127) for c in m["n"]], uv=[round(c * 4095) for pair in zip(u, 1 - v) for c in pair]))
    else: models.append(dict(name=m["name"], kind=m["kind"], side=round(m["side"], 3), top=m["top"], h=round(m["height"], 3), cards=[place(f"work/cards/{m['name']}_{t}.png") for t in ("a", "b", "t") if os.path.exists(f"work/cards/{m['name']}_{t}.png")]))
x, y = slot % 8 * SMALL, BIG + slot // 8 * SMALL; sheet.paste(Image.new("RGBA", (SMALL, SMALL), (235, 235, 232, 255)), (x, y)); plain = [round((x + 40) / SIZE, 5), round(1 - (y + SMALL - 40) / SIZE, 5), round((x + SMALL - 40) / SIZE, 5), round(1 - (y + 40) / SIZE, 5)]
assert BIG + (slot // 8 + 1) * SMALL <= SIZE, "sheet full"; sheet.save("web/models_atlas.webp", quality=90, method=6)
json.dump(dict(source="Poly Haven (polyhaven.com), CC0", plain=plain, models=models), open("web/models.json", "w"), separators=(",", ":")); print(len(models), "models;", os.path.getsize("web/models.json") // 1024, "KB +", os.path.getsize("web/models_atlas.webp") // 1024, "KB sheet")
