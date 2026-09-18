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
export function buildStructures(list, { groundY, toPhoto, DW, DH, tex }) {
  const roof = new Geo(), wall = new Geo(), glass = new Geo(), WALL = [0.93, 0.91, 0.87], LOW = [0.70, 0.68, 0.64], PLINTH = [0.50, 0.47, 0.43], TRIM = [0.36, 0.34, 0.32], SHED = [0.80, 0.81, 0.80];
  const uvf = v => { const [u, w] = toPhoto(v[0], v[2]); return [u / DW, 1 - w / DH]; };
  const tmp = new THREE.Color();
  for (const s of list) {
    let ring, P = null, hw, hd; const h = s.h;
    if (s.ring) { ring = s.ring.map(q => q.slice()); if (ring.reduce((t, q, k) => { const n = ring[(k + 1) % ring.length]; return t + q[0] * n[1] - n[0] * q[1]; }, 0) < 0) ring.reverse(); }
    else { let { x, z, w, d, a } = s; if (d > w) { [w, d] = [d, w]; a += Math.PI / 2; }                      // w = long side: the ridge runs along it
      const ex = [Math.cos(a), Math.sin(a)], ez = [-Math.sin(a), Math.cos(a)]; hw = w / 2; hd = d / 2; P = (lx, lz, y) => [x + ex[0] * lx + ez[0] * lz, y, z + ex[1] * lx + ez[1] * lz];
      ring = [[-hw, -hd], [hw, -hd], [hw, hd], [-hw, hd]].map(([lx, lz]) => { const q = P(lx, lz, 0); return [q[0], q[2]]; }); }
    const ys = ring.map(q => groundY(q[0], q[1])), y0 = Math.min(...ys), yb = y0 - 1.2, y1 = Math.max(...ys) + h, n = ring.length, W = (q, y) => [q[0], y, q[1]];
    const area = Math.abs(ring.reduce((t, q, k) => { const m = ring[(k + 1) % n]; return t + q[0] * m[1] - m[0] * q[1]; }, 0)) / 2, house = !s.big && area < 280, body = s.big ? SHED : WALL, gable = s.roof === "gable" && P, par = !gable && !s.big ? 0.55 : 0, yt = y1 + par;
    const plain = null, rq = (A, B, C, D) => plain ? wall.quad(A, B, C, D, null, [plain, plain, plain, plain]) : roof.quad(A, B, C, D, uvf);
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
      if (plain) wall.tri(T[0], T[1], T[2], null, plain); else roof.tri(T[0], T[1], T[2], uvf); }
  }
  const g = new THREE.Group(), roofM = new THREE.MeshStandardMaterial({ map: tex, roughness: 0.7, side: THREE.DoubleSide }), wallM = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.92, side: THREE.DoubleSide });
  const glassM = new THREE.MeshStandardMaterial({ color: 0x1d262c, roughness: 0.25, metalness: 0.1, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -2 });
  roofM.color.setScalar(1.25); for (const [geo, m] of [[roof, roofM], [wall, wallM], [glass, glassM]]) { const mesh = new THREE.Mesh(geo.build(), m); mesh.castShadow = m !== glassM; mesh.receiveShadow = true; g.add(mesh); }
  return { group: g, roofM };
}

// ---- leaves: one small texture of overlapping leaves, used on every card
function leafTexture() {
  const c = document.createElement("canvas"); c.width = c.height = 256; const g = c.getContext("2d");
  for (let i = 0; i < 150; i++) { const a = rnd(i, 1, 1) * 6.283, r = Math.pow(rnd(i, 2, 1), 0.6) * 100, x = 128 + Math.cos(a) * r, y = 128 + Math.sin(a) * r * 0.92, l = 150 + 105 * rnd(i, 3, 1) * (0.55 + 0.45 * (1 - y / 256));
    g.save(); g.translate(x, y); g.rotate(rnd(i, 4, 1) * 6.283); g.fillStyle = `rgb(${l | 0},${l | 0},${l * 0.97 | 0})`; g.beginPath(); g.ellipse(0, 0, 20 + 10 * rnd(i, 5, 1), 8 + 4 * rnd(i, 6, 1), 0, 0, 6.283); g.fill(); g.restore(); }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; return t;
}

// ---- planting. Rows: x, z, crown radius, height, kind (0 tree, 1 palm, 2 shrub, 3 tree on the satellite land), light rgb, dark rgb
export function buildFlora(rows, { groundY, lite, toPhoto, DW, DH, DPX }) {
  const cards = { p: [], n: [], uv: [], c: [], i: [] }, far = { p: [], n: [], uv: [], c: [], i: [] }, core = { p: [], c: [], n: [] }, hi = new THREE.Color(), lo = new THREE.Color(), m4 = new THREE.Matrix4();
  const ico0 = new THREE.IcosahedronGeometry(1, 0).attributes.position, ico1 = new THREE.IcosahedronGeometry(1, 1).attributes.position, hsl = {};
  const leafy = (c, gain) => { c.getHSL(hsl); const h = hsl.h > 0.62 ? hsl.h - 1 : hsl.h; return c.setHSL((h + (0.27 - h) * 0.45 + 1) % 1, Math.min(0.62, Math.max(hsl.s * 1.25, 0.26)), Math.min(0.5, hsl.l * gain)); };   // the photo sees crowns from above, in their own shade: lift them, and ease dry-season browns towards leaf green
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
const flat = g => { const i = g.index; return i ? Array.from(i.array) : Array.from({ length: g.attributes.position.count }, (_, k) => k); };
const ICO0 = flat(new THREE.IcosahedronGeometry(1, 0)), ICO1 = flat(new THREE.IcosahedronGeometry(1, 1));
