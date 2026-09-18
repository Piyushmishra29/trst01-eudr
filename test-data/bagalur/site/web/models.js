// Structures and planting for the site model. Everything is merged into a handful of meshes: a few draw calls however many trees there are.
import * as THREE from "three";

const rnd = (a, b, c) => { const x = Math.sin(a * 127.1 + b * 311.7 + c * 74.7) * 43758.5453; return x - Math.floor(x); };

class Geo {                                                   // flat-shaded quads and triangles, optional uv + colour
  constructor() { this.p = []; this.uv = []; this.c = []; this.i = []; }
  vert(v, uv, col) { this.p.push(v[0], v[1], v[2]); if (uv) this.uv.push(uv[0], uv[1]); if (col) this.c.push(col[0], col[1], col[2]); return this.p.length / 3 - 1; }
  quad(a, b, c, d, uvf, cols) { const o = [a, b, c, d].map((v, k) => this.vert(v, uvf && uvf(v), cols && cols[k])); this.i.push(o[0], o[1], o[2], o[2], o[1], o[3]); }
  tri(a, b, c, uvf, col) { const o = [a, b, c].map(v => this.vert(v, uvf && uvf(v), col)); this.i.push(o[0], o[1], o[2]); }
  build() { const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.Float32BufferAttribute(this.p, 3)); if (this.uv.length) g.setAttribute("uv", new THREE.Float32BufferAttribute(this.uv, 2));
    if (this.c.length) g.setAttribute("color", new THREE.Float32BufferAttribute(this.c, 3)); g.setIndex(this.i); g.computeVertexNormals(); return g; }
}

// ---- structures: straight walls with a plinth and soft grounding, photo roofs with eaves (pitched) or a parapet (flat), a few windows on house-sized blocks
export function buildStructures(list, { groundY, toPhoto, DW, DH, tex, wide }) {
  const roof = new Geo(), roofW = new Geo(), wall = new Geo(), glass = new Geo(), WALL = [0.93, 0.91, 0.87], LOW = [0.70, 0.68, 0.64], PLINTH = [0.50, 0.47, 0.43], TRIM = [0.36, 0.34, 0.32], SHED = [0.80, 0.81, 0.80];
  const uvf = v => { const [u, w] = toPhoto(v[0], v[2]); return [u / DW, 1 - w / DH]; }, uvw = v => wide ? [(v[0] - wide.x0) / (wide.x1 - wide.x0), 1 - (v[2] - wide.z0) / (wide.z1 - wide.z0)] : [0, 0];   // roofs outside the main photo take their picture from the 500 m photo
  const tmp = new THREE.Color();
  for (const s of list) {
    let ring, P = null, hw, hd; const h = s.h;
    if (s.ring) { ring = s.ring.map(q => q.slice()); if (ring.reduce((t, q, k) => { const n = ring[(k + 1) % ring.length]; return t + q[0] * n[1] - n[0] * q[1]; }, 0) < 0) ring.reverse(); }
    else { let { x, z, w, d, a } = s; if (d > w) { [w, d] = [d, w]; a += Math.PI / 2; }                      // w = long side: the ridge runs along it
      const ex = [Math.cos(a), Math.sin(a)], ez = [-Math.sin(a), Math.cos(a)]; hw = w / 2; hd = d / 2; P = (lx, lz, y) => [x + ex[0] * lx + ez[0] * lz, y, z + ex[1] * lx + ez[1] * lz];
      ring = [[-hw, -hd], [hw, -hd], [hw, hd], [-hw, hd]].map(([lx, lz]) => { const q = P(lx, lz, 0); return [q[0], q[2]]; }); }
    const ys = ring.map(q => groundY(q[0], q[1])), y0 = Math.min(...ys), yb = y0 - 1.2, y1 = Math.max(...ys) + h, n = ring.length, W = (q, y) => [q[0], y, q[1]];
    const area = Math.abs(ring.reduce((t, q, k) => { const m = ring[(k + 1) % n]; return t + q[0] * m[1] - m[0] * q[1]; }, 0)) / 2, house = !s.big && area < 280, body = s.big ? SHED : WALL, gable = s.roof === "gable" && P, par = !gable && !s.big ? 0.55 : 0, yt = y1 + par;
    const fromWide = s.src === "wide", R = fromWide ? roofW : roof, uv = fromWide ? uvw : uvf, rq = (A, B, C, D) => R.quad(A, B, C, D, uv);
    ring.forEach((qa, k) => { const qb = ring[(k + 1) % n], len = Math.hypot(qb[0] - qa[0], qb[1] - qa[1]), nx = (qb[1] - qa[1]) / len, nz = -(qb[0] - qa[0]) / len, Q = (t, y, off) => [qa[0] + (qb[0] - qa[0]) * t + nx * off, y, qa[1] + (qb[1] - qa[1]) * t + nz * off];
      wall.quad(W(qa, yt), W(qb, yt), W(qa, y0 + 0.9), W(qb, y0 + 0.9), null, [body, body, body, body]);
      wall.quad(W(qa, y0 + 0.9), W(qb, y0 + 0.9), W(qa, yb), W(qb, yb), null, [body, body, LOW, LOW]);                                                       // the last 0.9 m darkens towards the ground: reads as contact shadow and splash-back
      const o = 0.12; wall.quad(Q(0, y0 + 0.45, o), Q(1, y0 + 0.45, o), Q(0, yb, o), Q(1, yb, o), null, [PLINTH, PLINTH, PLINTH, PLINTH]); wall.quad(Q(0, y0 + 0.45, 0), Q(1, y0 + 0.45, 0), Q(0, y0 + 0.45, o), Q(1, y0 + 0.45, o), null, [PLINTH, PLINTH, PLINTH, PLINTH]);   // plinth band, a touch proud of the wall
      if (house && len > 4.5 && h > 2.6) { const m = Math.max(1, Math.floor((len - 1.6) / 3.1)), floors = h > 5.6 ? 2 : 1;
        for (let f = 0; f < floors; f++) for (let q = 0; q < m; q++) { const t = (q + 0.5) / m, w2 = 0.55 / len, yw = y0 + 1.05 + f * 3, door = f === 0 && q === 0 && k === (s.g % n);
          glass.quad(Q(t - w2, yw + 1.25, 0.05), Q(t + w2, yw + 1.25, 0.05), Q(t - w2, door ? y0 + 0.45 : yw, 0.05), Q(t + w2, door ? y0 + 0.45 : yw, 0.05)); } }
      if (par) { const t = 0.22, inset = (q, p, m) => { const e1 = [q[0] - p[0], q[1] - p[1]], e2 = [m[0] - q[0], m[1] - q[1]], l1 = Math.hypot(...e1), l2 = Math.hypot(...e2), n1 = [-e1[1] / l1, e1[0] / l1], n2 = [-e2[1] / l2, e2[0] / l2], bx = n1[0] + n2[0], bz = n1[1] + n2[1], k2 = t / Math.max(0.3, (bx * n1[0] + bz * n1[1])); return [q[0] + bx * k2, q[1] + bz * k2]; };
        const ia = inset(qa, ring[(k + n - 1) % n], qb), ib = inset(qb, qa, ring[(k + 2) % n]); wall.quad(W(qa, yt), W(ia, yt), W(qb, yt), W(ib, yt), null, [WALL, WALL, WALL, WALL]); wall.quad(W(ia, yt), W(ia, y1), W(ib, yt), W(ib, y1), null, [LOW, LOW, LOW, LOW]); } });
    if (gable) { const ov = 0.5, rise = Math.min(0.2 * 2 * hd, 3.2), slope = rise / hd, ye = y1 - ov * slope, yr = y1 + rise, L = hw + ov, D = hd + ov, F = 0.2, T4 = [TRIM, TRIM, TRIM, TRIM];
      rq(P(-L, 0, yr), P(L, 0, yr), P(-L, -D, ye), P(L, -D, ye)); rq(P(L, 0, yr), P(-L, 0, yr), P(L, D, ye), P(-L, D, ye));
      for (const sx of [-1, 1]) wall.tri(P(sx * hw, -hd, y1), P(sx * hw, hd, y1), P(sx * hw, 0, yr), null, body);
      for (const sz of [-1, 1]) wall.quad(P(-L, sz * D, ye), P(L, sz * D, ye), P(-L, sz * D, ye - F), P(L, sz * D, ye - F), null, T4);                        // fascia: gives the roof an edge
      for (const sx of [-1, 1]) for (const sz of [-1, 1]) wall.quad(P(sx * L, 0, yr), P(sx * L, sz * D, ye), P(sx * L, 0, yr - F), P(sx * L, sz * D, ye - F), null, T4);
    } else for (const [i, j, k] of THREE.ShapeUtils.triangulateShape(ring.map(q => new THREE.Vector2(q[0], q[1])), [])) { const T = [ring[i], ring[k], ring[j]].map(q => W(q, y1));   // wound to face up: the shadow bias follows the geometric normal
      R.tri(T[0], T[1], T[2], uv); }
  }
  const g = new THREE.Group(), roofM = new THREE.MeshStandardMaterial({ map: tex, roughness: 0.7, side: THREE.DoubleSide }), wallM = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.92, side: THREE.DoubleSide });
  const glassM = new THREE.MeshStandardMaterial({ color: 0x1d262c, roughness: 0.25, metalness: 0.1, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -2 });
  const roofWM = new THREE.MeshStandardMaterial({ color: 0xb9b4ab, roughness: 0.7, side: THREE.DoubleSide });
  roofM.color.setScalar(1.25); for (const [geo, m] of [[roof, roofM], [roofW, roofWM], [wall, wallM], [glass, glassM]]) { const mesh = new THREE.Mesh(geo.build(), m); mesh.castShadow = m !== glassM; mesh.receiveShadow = true; g.add(mesh); }
  return { group: g, roofM, roofWM };
}

// ---- leaves: one small texture of overlapping leaves, used on every card
const drawLeaves = g => { for (let i = 0; i < 150; i++) { const a = rnd(i, 1, 1) * 6.283, r = Math.pow(rnd(i, 2, 1), 0.6) * 100, x = 128 + Math.cos(a) * r, y = 128 + Math.sin(a) * r * 0.92, l = 150 + 105 * rnd(i, 3, 1) * (0.55 + 0.45 * (1 - y / 256));
    g.save(); g.translate(x, y); g.rotate(rnd(i, 4, 1) * 6.283); g.fillStyle = `rgb(${l | 0},${l | 0},${l * 0.97 | 0})`; g.beginPath(); g.ellipse(0, 0, 20 + 10 * rnd(i, 5, 1), 8 + 4 * rnd(i, 6, 1), 0, 0, 6.283); g.fill(); g.restore(); } };
function leafTexture() {
  const c = document.createElement("canvas"); c.width = c.height = 256; drawLeaves(c.getContext("2d"));
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; return t;
}

// ---- planting. Rows: x, z, crown radius, height, kind (0 tree, 1 palm, 2 shrub, 3 tree on the satellite land), light rgb, dark rgb
export function buildFlora(rows, { groundY, lite, toPhoto, DW, DH, DPX }) {
  const cards = { p: [], n: [], uv: [], c: [], i: [] }, far = { p: [], n: [], uv: [], c: [], i: [] }, core = { p: [], c: [], n: [] }, hi = new THREE.Color(), lo = new THREE.Color(), m4 = new THREE.Matrix4();
  const ico0 = new THREE.IcosahedronGeometry(1, 0).attributes.position, ico1 = new THREE.IcosahedronGeometry(1, 1).attributes.position, hsl = {};
  const leafy = (c, gain) => leafy0(c, gain, hsl);
  const card = (B, cx, cy, cz, dx, dy, dz, size, col, ti, k) => {                                     // one leaf cluster: a square facing roughly outward, lit as if it were part of a round crown
    let nx = dx + (rnd(ti, k, 11) - 0.5) * 1.1, ny = dy + (rnd(ti, k, 12) - 0.5) * 1.1, nz = dz + (rnd(ti, k, 13) - 0.5) * 1.1, l = Math.hypot(nx, ny, nz) || 1; nx /= l; ny /= l; nz /= l;
    let tx = -nz, ty = 0, tz = nx; l = Math.hypot(tx, tz); if (l < 0.01) { tx = 1; tz = 0; l = 1; } tx /= l; tz /= l; const bx = ny * tz - nz * ty, by = nz * tx - nx * tz, bz = nx * ty - ny * tx, s = size / 2, o = B.p.length / 3;
    const sn = [dx * 0.75, dy * 0.75 + 0.5, dz * 0.75], sl = Math.hypot(...sn), rot = rnd(ti, k, 14) * 6.283, cr = Math.cos(rot), sr = Math.sin(rot);
    for (const [u, v] of [[-1, 1], [1, 1], [-1, -1], [1, -1]]) { const a = (u * cr - v * sr) * s, b = (u * sr + v * cr) * s; B.p.push(cx + tx * a + bx * b, cy + ty * a + by * b, cz + tz * a + bz * b); B.n.push(sn[0] / sl, sn[1] / sl, sn[2] / sl); B.uv.push((u + 1) / 2, (v + 1) / 2); B.c.push(col.r, col.g, col.b); }
    B.i.push(o, o + 1, o + 2, o + 2, o + 1, o + 3); };
  const trunkRows = [], palms = [];
  rows.forEach(([x, z, r, h, kind, c1, c2], ti) => {
    const onSat = kind === 3; if (onSat) { const [u, v] = toPhoto(x, z); if (Math.max(-u, u - DW, -v, v - DH) * DPX < (lite ? 120 : 260)) kind = 0; }   // close to the survey they get full crowns; further out a few big cards are enough
    if (kind === 3 && lite && ti % 2) return; leafy(hi.setHex(c1), 1.75); leafy(lo.setHex(c2), 1.55);
    const y0 = onSat ? -0.5 : groundY(x, z);
    if (kind === 1) { palms.push([x, y0, z, r, h, ti]); trunkRows.push([x, y0, z, 0.24, h + 0.3]); return; }
    const half = kind === 2 ? 0.55 * h : Math.min(0.4 * h, Math.max(0.34 * h, 0.8 * r)), cy = kind === 2 ? y0 + 0.45 * h : y0 + h - half;
    if (kind === 0) trunkRows.push([x, y0, z, Math.max(0.1, Math.min(0.42, r * 0.075)), h - 1.2 * half]);
    const B = kind === 3 ? far : cards, n = kind === 3 ? (lite ? 3 : 5) : kind === 2 ? 6 : Math.round(Math.min(56, 5 + 8 * (r / Math.min(0.95 * r, 2.3)) ** 2) * (lite ? 0.6 : 1)), col = new THREE.Color();   // leaf clusters stay about 2 m across, so a big crown gets more of them, not bigger ones
    for (let k = 0; k < n; k++) { const dy = kind === 3 && k === 0 ? 1 : -0.45 + 1.45 * rnd(ti, k, 1), a = (k + rnd(ti, k, 2)) * 2.39996, q = Math.sqrt(Math.max(0, 1 - dy * dy)), dx = Math.cos(a) * q, dz = Math.sin(a) * q, push = (r > 2.6 ? 0.66 : 0.52) + 0.2 * rnd(ti, k, 3);
      col.copy(lo).lerp(hi, THREE.MathUtils.clamp(0.45 + 0.65 * dy + 0.25 * (rnd(ti, k, 4) - 0.5), 0, 1)).multiplyScalar(0.9 + 0.22 * rnd(ti, k, 5));
      card(B, x + dx * r * push, cy + dy * half * push, z + dz * r * push, dx, dy, dz, (kind === 3 ? 1.4 * r : Math.min(1.05 * r, 2.3 + Math.max(0, r - 3.5) * 0.45)) * (0.85 + 0.35 * rnd(ti, k, 6)), col, ti, k); }
    if (kind === 3) return; const ip = r > 3.4 && !onSat && !lite ? ico1 : ico0, idx = ip === ico1 ? ICO1 : ICO0, dk = lo.clone().multiplyScalar(0.7);            // dark core: gaps between the leaves read as shade, not as sky
    for (const v of idx) { const jit = 0.85 + 0.3 * rnd(ti, Math.round(ip.getX(v) * 50) + Math.round(ip.getZ(v) * 50) * 7, Math.round(ip.getY(v) * 50)); core.p.push(x + ip.getX(v) * r * 0.6 * jit, cy + ip.getY(v) * half * 0.6 * jit, z + ip.getZ(v) * r * 0.6 * jit); core.c.push(dk.r, dk.g, dk.b); core.n.push(ip.getX(v), ip.getY(v), ip.getZ(v)); } });   // round normals: no facets showing between the leaves
  const mk = B => { const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.Float32BufferAttribute(B.p, 3)); g.setAttribute("normal", new THREE.Float32BufferAttribute(B.n, 3)); g.setAttribute("uv", new THREE.Float32BufferAttribute(B.uv, 2)); g.setAttribute("color", new THREE.Float32BufferAttribute(B.c, 3)); g.setIndex(B.i); return g; };
  const leafM = new THREE.MeshStandardMaterial({ map: leafTexture(), alphaTest: 0.4, vertexColors: true, roughness: 1, emissive: 0x070d04, side: THREE.DoubleSide }), group = new THREE.Group();
  leafM.onBeforeCompile = sh => { sh.fragmentShader = sh.fragmentShader.replace("#include <normal_fragment_begin>", "float faceDirection = 1.0; vec3 normal = normalize( vNormal ); vec3 nonPerturbedNormal = normal;"); };   // cards keep their round-crown normal on both faces: even shading whichever side faces the camera
  const leaves = new THREE.Mesh(mk(cards), leafM), farLeaves = new THREE.Mesh(mk(far), leafM); leaves.castShadow = leaves.receiveShadow = true; leaves.isLine = farLeaves.isLine = true;   // flag only: the contact-shading pass ignores alpha, so it skips the cards (as it does lines) and shades the cores
  const cg = new THREE.BufferGeometry(); cg.setAttribute("position", new THREE.Float32BufferAttribute(core.p, 3)); cg.setAttribute("color", new THREE.Float32BufferAttribute(core.c, 3)); cg.setAttribute("normal", new THREE.Float32BufferAttribute(core.n, 3));
  const cores = new THREE.Mesh(cg, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 1 })); cores.castShadow = true;
  const trunks = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.7, 1, 1, 5, 1, true).translate(0, 0.5, 0), new THREE.MeshStandardMaterial({ color: 0x5a4736, roughness: 1 }), trunkRows.length);
  trunkRows.forEach(([x, y, z, r, len], k) => trunks.setMatrixAt(k, m4.makeScale(r, Math.max(len, 0.01), r).setPosition(x, y - 0.3, z))); trunks.castShadow = true;
  const pv = [], pc = [], pi = [], F = 13, S = 5;                                                       // coconut palms: arching fronds
  for (const [x0, y0, z0, r, h, t] of palms) { const L = r * 1.05;
    for (let f = 0; f < F; f++) { const a = f / F * 6.2832 + rnd(t, f, 5) * 0.4, dx = Math.cos(a), dz = Math.sin(a), lift = 0.25 + 0.3 * rnd(t, f, 6), base = pv.length / 3, sh = 0.75 + 0.35 * rnd(t, f, 7);
      for (let k = 0; k <= S; k++) { const qq = k / S, rr = qq * L, w = 0.16 * L * Math.sin(Math.PI * Math.min(1, qq * 0.9 + 0.1)), y = y0 + h + L * (lift * qq - 0.75 * qq * qq);
        for (const sg of [-1, 1]) { pv.push(x0 + dx * rr - dz * w * sg, y, z0 + dz * rr + dx * w * sg); pc.push(0.30 * sh, 0.46 * sh, 0.20 * sh); } if (k < S) { const v = base + k * 2; pi.push(v, v + 1, v + 2, v + 2, v + 1, v + 3); } } } }
  const pg = new THREE.BufferGeometry(); pg.setAttribute("position", new THREE.Float32BufferAttribute(pv, 3)); pg.setAttribute("color", new THREE.Float32BufferAttribute(pc, 3)); pg.setIndex(pi); pg.computeVertexNormals();
  const palmMesh = new THREE.Mesh(pg, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.9, side: THREE.DoubleSide })); palmMesh.castShadow = true;
  group.add(cores, leaves, farLeaves, trunks, palmMesh); return group;
}
function leafy0(c, gain, hsl) { c.getHSL(hsl); const h = hsl.h > 0.62 ? hsl.h - 1 : hsl.h; return c.setHSL((h + (0.27 - h) * 0.45 + 1) % 1, Math.min(0.62, Math.max(hsl.s * 1.25, 0.26)), Math.min(0.5, hsl.l * gain)); }   // the photo sees leaves from above, in their own shade: lift them, and ease dry-season browns towards leaf green
const flat = g => { const i = g.index; return i ? Array.from(i.array) : Array.from({ length: g.attributes.position.count }, (_, k) => k); };
const ICO0 = flat(new THREE.IcosahedronGeometry(1, 0)), ICO1 = flat(new THREE.IcosahedronGeometry(1, 1));

// ---- small things on the ground (build_ground.py): stones, low bushes, grass and weed tufts, each where the photo shows one and tinted with its colour there.
// Rows: x*10, z*10, size cm, kind (0 stone, 1 low bush, 2 tuft), rgb. Shapes come from real scans (prep_models.py: Poly Haven, CC0): plants as picture cards of the scanned plant (front, side, top),
// stones as the scanned mesh near the camera and a plain lump further off. 40 m tiles that switch off beyond a few hundred metres, where all this is smaller than a pixel.
export function buildGround(rows, { groundY, lite, toPhoto, DW, DH, models, atlas, wantNear }) {
  const TILE = 40, tiles = new Map(), col = new THREE.Color(), hsl = {}, ico = new THREE.IcosahedronGeometry(1, 0), ip = ico.attributes.position, icoIdx = flat(ico), newB = () => ({ p: [], n: [], uv: [], c: [], i: [] });
  const byKind = [[], [], []]; for (const m of models.models) byKind[m.kind].push(m); const PL = models.plain;
  const tileOf = (x, z) => { const k = Math.floor(x / TILE) + "," + Math.floor(z / TILE); let t = tiles.get(k); if (!t) tiles.set(k, t = { P: newB(), S: newB(), stones: [] }); return t; };
  const yAt = (x, z) => { const [pu, pv] = toPhoto(x, z); return pu > 4 && pv > 4 && pu < DW - 4 && pv < DH - 4 ? groundY(x, z) : -0.25; };
  const card = (B, pts, uv, flip, c, sh) => { const o = B.p.length / 3, [u0, v0, u1, v1] = uv, ua = flip ? u1 : u0, ub = flip ? u0 : u1; pts.forEach((q, k) => { B.p.push(...q); B.n.push(0, 1, 0); B.uv.push(k % 2 ? ub : ua, k < 2 ? v1 : v0); const f = sh[k < 2 ? 0 : 1]; B.c.push(c.r * f, c.g * f, c.b * f); }); B.i.push(o, o + 1, o + 2, o + 2, o + 1, o + 3); };   // lit like the ground it stands on
  rows.forEach(([xi, zi, cm, kind, rgb], ti) => {
    if (lite && kind && ti % 2) return; const x = xi / 10, z = zi / 10, s = cm / 100, y0 = yAt(x, z), T = tileOf(x, z); col.setHex(rgb);
    if (kind === 0) { T.stones.push([x, y0, z, s, rgb, ti]); const B = T.S;                             // far stone: a squashed, dented lump, flat-faced, a little sunk into the soil
      const rot = rnd(ti, 1, 21) * 6.283, cr = Math.cos(rot), sr = Math.sin(rot), sq = 0.45 + 0.3 * rnd(ti, 2, 21), o = B.p.length / 3, P = []; col.multiplyScalar(1.15);
      for (let v = 0; v < ip.count; v++) { const j = 0.72 + 0.5 * rnd(ti, v, 22), a = ip.getX(v) * j, b = ip.getY(v) * j, c = ip.getZ(v) * j * (0.75 + 0.4 * rnd(ti, 3, 21)); P.push([x + (a * cr - c * sr) * s * 0.5, y0 + (b * sq + sq * 0.55) * s * 0.5, z + (a * sr + c * cr) * s * 0.5]); }
      for (let f = 0; f < icoIdx.length; f += 3) { const A = P[icoIdx[f]], Bp = P[icoIdx[f + 1]], C = P[icoIdx[f + 2]], ux = Bp[0] - A[0], uy = Bp[1] - A[1], uz = Bp[2] - A[2], vx = C[0] - A[0], vy = C[1] - A[1], vz = C[2] - A[2]; let nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx; const l = Math.hypot(nx, ny, nz) || 1; nx /= l; ny /= l; nz /= l;
        for (const Q of [A, Bp, C]) { B.p.push(...Q); B.n.push(nx, ny, nz); B.uv.push(PL[0] + (PL[2] - PL[0]) * rnd(ti, f, 23), PL[1] + (PL[3] - PL[1]) * rnd(ti, f, 24)); const sh = (Q[1] - y0 < 0.06 * s ? 0.6 : 1) * (0.92 + 0.16 * rnd(ti, f, 25)); B.c.push(col.r * sh, col.g * sh, col.b * sh); } }
      for (let f = 0; f < icoIdx.length; f++) B.i.push(o + f); return; }
    const pool = byKind[kind], M = pool[Math.floor(rnd(ti, 5, 51) * pool.length) % pool.length], rot = rnd(ti, 6, 51) * 6.283, B = T.P;
    const sc = (kind === 1 ? 1.15 * s : THREE.MathUtils.clamp(s / M.h, 0.2, M.h < 0.8 ? 0.4 : 0.55)) * (0.9 + 0.25 * rnd(ti, 7, 51)), w = M.side * sc / 2, yb = y0 - 0.04 * sc, yt = yb + 2 * w;
    if (kind === 1) leafy0(col, 1.6, hsl); col.multiplyScalar((kind === 1 ? 1.55 : 2.1) * (0.9 + 0.2 * rnd(ti, 8, 51)));   // the cards are evened out to mid grey, so the tint carries the full colour
    const sides = kind === 1 ? 3 : 2;
    for (let k = 0; k < sides; k++) { const a = rot + k * Math.PI / sides, dx = Math.cos(a) * w, dz = Math.sin(a) * w; card(B, [[x - dx, yt, z - dz], [x + dx, yt, z + dz], [x - dx, yb, z - dz], [x + dx, yb, z + dz]], M.cards[k % 2], k === 2, col, [1.05, 0.6]); }
    if (kind === 1 && M.cards[2]) { const t = M.top * sc / 2, cr = Math.cos(rot) * t, sr = Math.sin(rot) * t, yy = y0 + 0.5 * M.h * sc; card(B, [[x - cr + sr, yy, z - sr - cr], [x + cr + sr, yy, z + sr - cr], [x - cr - sr, yy, z - sr + cr], [x + cr - sr, yy, z + sr + cr]], M.cards[2], false, col, [1, 1]); } });   // seen from above a bush is its top view, not two thin lines
  const mat = new THREE.MeshStandardMaterial({ map: atlas, alphaTest: 0.4, vertexColors: true, roughness: 1, side: THREE.DoubleSide }), group = new THREE.Group(), list = [];
  mat.onBeforeCompile = sh => { sh.fragmentShader = sh.fragmentShader.replace("#include <normal_fragment_begin>", "float faceDirection = 1.0; vec3 normal = normalize( vNormal ); vec3 nonPerturbedNormal = normal;"); };   // both faces of a card share its normal
  const mesh = B => { const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.Float32BufferAttribute(B.p, 3)); g.setAttribute("normal", new THREE.Float32BufferAttribute(B.n, 3)); g.setAttribute("uv", new THREE.Float32BufferAttribute(B.uv, 2)); g.setAttribute("color", new THREE.Float32BufferAttribute(B.c, 3)); if (B.i.length) g.setIndex(B.i); g.computeBoundingSphere();
    const o = new THREE.Mesh(g, mat); o.receiveShadow = true; o.isLine = true; o.matrixAutoUpdate = false; o.visible = false; group.add(o); return o; };   // isLine: the contact-shading pass ignores alpha, so it skips these as it does the leaf cards
  for (const T of tiles.values()) { T.c = new THREE.Vector3(); const bs = []; for (const k of ["P", "S"]) { T[k] = T[k].p.length ? mesh(T[k]) : null; if (T[k]) bs.push(T[k].geometry.boundingSphere); } T.c.copy(bs[0].center); T.r = Math.max(...bs.map(b => b.radius + b.center.distanceTo(T.c))); list.push(T); }
  const buildNear = T => { const B = newB(), pool = byKind[0];                                          // the scanned stones, for the tiles around the camera: built as it arrives, a few per frame
    for (const [x, y0, z, s, rgb, ti] of T.stones) { const M = pool[Math.floor(rnd(ti, 5, 51) * pool.length) % pool.length], rot = rnd(ti, 6, 51) * 6.283, cr = Math.cos(rot), sr = Math.sin(rot), sc = s * 0.55 * (0.9 + 0.25 * rnd(ti, 7, 51)), sink = 0.18 * M.h * sc; col.setHex(rgb).multiplyScalar(1.7);
      for (let v = 0; v < M.p.length; v += 3) { const a = M.p[v] / 1000, b = M.p[v + 1] / 1000, c = M.p[v + 2] / 1000, na = M.n[v] / 127, nc = M.n[v + 2] / 127, sh = 0.55 + 0.45 * Math.min(1, b / M.h * 2.2);
        B.p.push(x + (a * cr - c * sr) * sc, y0 - sink + b * sc, z + (a * sr + c * cr) * sc); B.n.push(na * cr - nc * sr, M.n[v + 1] / 127, na * sr + nc * cr); B.c.push(col.r * sh, col.g * sh, col.b * sh); }
      for (let v = 0; v < M.uv.length; v++) B.uv.push(M.uv[v] / 4095); }
    T.near = mesh(B); };
  const R = lite ? 220 : 380, RN = 120, update = cam => { let built = 0, pending = false; const near = !lite && (!wantNear || wantNear());
    for (const T of list) { const d = cam.position.distanceTo(T.c) - T.r, on = d < R, isNear = near && T.S && d < (T.isNear ? RN + 12 : RN);
      if (isNear && !T.near) { if (built < 3) { buildNear(T); built++; } else pending = true; }
      T.isNear = isNear && !!T.near; if (T.P) T.P.visible = on; if (T.S) T.S.visible = on && !T.isNear; if (T.near) T.near.visible = T.isNear; }
    const idle = list.filter(T => T.near && !T.isNear); if (idle.length > 60) for (const T of idle.slice(0, idle.length - 60)) { group.remove(T.near); T.near.geometry.dispose(); T.near = null; }   // keep memory bounded on a long wander
    return pending; };
  return { group, update, count: rows.length };
}
