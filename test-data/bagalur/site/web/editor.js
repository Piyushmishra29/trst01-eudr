// Boundary editor (open the page with ?edit). Drag a corner to move it, drag a small "+" handle to add a point and bend the line,
// right-click a corner (or select it and press Delete) to remove it. Save writes edits/parcels.json on the server; the viewer loads that file on every visit.
export function start(c) {
  const { THREE, ED, parcels, camera, controls, pick, groundY, buildParcel, labelParcel, refreshList, geom, select, go, toast, treeG, reshadow, labs, labEl, parcelG, parcelS, markDirty } = c;
  ED.on = true; let cur = null, selV = -1, drag = null, unsaved = false; const undo = [], redo = [], v3 = new THREE.Vector3();
  const css = document.createElement("style"); css.textContent = `
    #edp { position:fixed; right:20px; top:20px; width:270px; padding:16px 18px; border-radius:18px; background:rgba(250,249,246,.94); backdrop-filter:blur(14px); box-shadow:0 10px 40px rgba(0,0,0,.18); font:13px/1.45 "DM Sans",system-ui,sans-serif; color:#1d1d1b; z-index:30; }
    #edp h3 { margin:0 0 2px; font:400 19px "DM Serif Display",serif; } #edp p { margin:6px 0; color:#6b675f; font-size:12px; } #edp .row { display:flex; flex-wrap:wrap; gap:6px; margin-top:10px; }
    #edp button { border:1px solid #d9d5cc; background:#fff; border-radius:999px; padding:6px 12px; font:inherit; cursor:pointer; } #edp button:hover { border-color:#1d1d1b; } #edp button:disabled { opacity:.4; cursor:default; }
    #edp button.go { background:#1d1d1b; color:#fff; border-color:#1d1d1b; } #edp label { display:flex; gap:8px; align-items:center; margin-top:8px; font-size:12px; } #edst { font-weight:500; color:#1d1d1b !important; }
    #card { display:none !important; } #edh { position:fixed; inset:0; pointer-events:none; z-index:20; }
    #edh i { position:absolute; width:14px; height:14px; margin:-8px 0 0 -8px; border-radius:50%; background:#fff; border:2px solid #1d1d1b; box-shadow:0 1px 5px rgba(0,0,0,.45); pointer-events:auto; cursor:grab; touch-action:none; }
    #edh i.sel { background:#ffb347; } #edh i.mid { width:10px; height:10px; margin:-6px 0 0 -6px; border:1.5px solid #fff; background:rgba(29,29,27,.55); } #edh i.mid:hover { background:#ffb347; border-color:#1d1d1b; }`;
  document.head.appendChild(css);
  const panel = document.createElement("div"); panel.id = "edp"; panel.innerHTML = `<h3>Edit boundaries</h3><p id="edst">Click a parcel to edit it</p>
    <p>Drag a white corner to move it. Drag a small dark dot to add a point there and bend the line. Right-click a corner to remove it. Corners snap to nearby corners of other parcels (hold Alt to switch that off).</p>
    <div class="row"><button data-e="undo">Undo</button><button data-e="redo">Redo</button><button data-e="new">New parcel</button><button data-e="del">Delete parcel</button></div>
    <label><input type="checkbox" id="edtrees"> Show trees while editing</label>
    <div class="row"><button class="go" data-e="save">Save</button><button data-e="dl">Download file</button><button data-e="revert">Discard changes</button></div>`;
  const hand = document.createElement("div"); hand.id = "edh"; document.body.append(hand, panel);
  const st = t => panel.querySelector("#edst").textContent = t, snap = () => JSON.stringify(parcels.map(p => ({ id: p.id, ring: p.ring })));
  let baseline = snap();
  treeG.visible = false; reshadow(); go("top", 900); markDirty();

  function redraw(p) { Object.assign(p, geom(p.ring)); buildParcel(p); labelParcel(p); markDirty(); }
  function restore(json) { const want = JSON.parse(json), keepId = cur?.id;
    for (let i = parcels.length - 1; i >= 0; i--) if (!want.find(w => w.id === parcels[i].id)) drop(parcels[i]);
    for (const w of want) { let p = parcels.find(a => a.id === w.id); if (!p) { p = { id: w.id, ring: w.ring }; parcels.push(p); } p.ring = w.ring.map(q => q.slice()); redraw(p); }
    parcels.sort((a, b) => a.id.localeCompare(b.id)); refreshList(); cur = parcels.find(p => p.id === keepId) || null; selV = -1; layout(); changed(false); }
  function drop(p) { parcelG.remove(p.fill, p.ghost, p.sel); parcelS.remove(p.under, p.top); if (p.lab) { labEl.removeChild(p.lab.el); labs.splice(labs.indexOf(p.lab), 1); } parcels.splice(parcels.indexOf(p), 1); }
  function commit() { undo.push(lastState); if (undo.length > 100) undo.shift(); redo.length = 0; lastState = snap(); changed(true); }
  let lastState = snap();
  function changed(pushed) { unsaved = snap() !== baseline; refreshList(); buttons(); st(cur ? `Parcel ${cur.id} · ${(cur.m2 / 4046.8564).toFixed(2)} ac · ${cur.ring.length} points${unsaved ? " · not saved" : ""}` : unsaved ? "Changes not saved" : "Click a parcel to edit it"); }
  function buttons() { panel.querySelector('[data-e="undo"]').disabled = !undo.length; panel.querySelector('[data-e="redo"]').disabled = !redo.length; panel.querySelector('[data-e="del"]').disabled = !cur; panel.querySelector('[data-e="revert"]').disabled = !unsaved; }

  const scr = (x, z) => { v3.set(x, groundY(x, z) + 0.6, z).project(camera); return v3.z > 1 || v3.z < -1 ? null : [(v3.x + 1) / 2 * innerWidth, (1 - v3.y) / 2 * innerHeight]; };
  function layout() { if (drag) return place(); hand.textContent = ""; if (!cur) return; const n = cur.ring.length;
    cur.ring.forEach((q, i) => { const m = document.createElement("i"); m.className = "mid"; m.dataset.m = i; hand.appendChild(m); });
    cur.ring.forEach((q, i) => { const e = document.createElement("i"); e.dataset.v = i; if (i === selV) e.className = "sel"; hand.appendChild(e); }); place(); }
  function place() { if (!cur) return; const n = cur.ring.length; for (const e of hand.children) { let s; if (e.dataset.m !== undefined) { const i = +e.dataset.m, a = cur.ring[i], b = cur.ring[(i + 1) % n], sa = scr(...a), sb = scr(...b); s = sa && sb && Math.hypot(sa[0] - sb[0], sa[1] - sb[1]) > 34 ? scr((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) : null; } else s = scr(...cur.ring[+e.dataset.v]);
      e.style.display = s ? "" : "none"; if (s) { e.style.left = s[0] + "px"; e.style.top = s[1] + "px"; } } }
  controls.addEventListener("change", place); addEventListener("resize", place);
  ED.onSelect = p => { if (p === cur) return; cur = p; selV = -1; setTimeout(() => { layout(); changed(false); }, 0); };

  hand.addEventListener("pointerdown", e => { const t = e.target; if (t === hand || !cur || e.button !== 0) return; e.preventDefault(); let i;
    if (t.dataset.m !== undefined) { i = +t.dataset.m + 1; const a = cur.ring[i - 1], b = cur.ring[i % cur.ring.length]; cur.ring.splice(i, 0, [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]); selV = i; redraw(cur); layout(); } else { i = +t.dataset.v; selV = i; layout(); }
    drag = { i, moved: t.dataset.m !== undefined }; try { hand.setPointerCapture(e.pointerId); } catch { } hand.style.pointerEvents = "auto"; hand.style.cursor = "grabbing"; });
  hand.addEventListener("pointermove", e => { if (!drag) return; const p = pick(e); if (!p) return; let x = p.x, z = p.z;
    if (!e.altKey) { let best = 12; for (const o of parcels) if (o !== cur) for (const q of o.ring) { const s = scr(...q); if (!s) continue; const d = Math.hypot(s[0] - e.clientX, s[1] - e.clientY); if (d < best) { best = d; x = q[0]; z = q[1]; } } }
    cur.ring[drag.i] = [Math.round(x * 100) / 100, Math.round(z * 100) / 100]; drag.moved = true; redraw(cur); place(); changed(false); });
  const end = e => { if (!drag) return; const moved = drag.moved; drag = null; hand.style.pointerEvents = ""; hand.style.cursor = ""; try { hand.releasePointerCapture(e.pointerId); } catch { } if (moved) commit(); layout(); };
  hand.addEventListener("pointerup", end); hand.addEventListener("pointercancel", end);
  const removeV = i => { if (!cur || i < 0) return; if (cur.ring.length <= 3) return toast("A parcel needs at least 3 points"); cur.ring.splice(i, 1); selV = -1; redraw(cur); layout(); commit(); };
  hand.addEventListener("contextmenu", e => { e.preventDefault(); if (e.target.dataset.v !== undefined) removeV(+e.target.dataset.v); });
  addEventListener("keydown", e => { if (e.target.tagName === "INPUT") return; const z = (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z";
    if (z && e.shiftKey || (e.ctrlKey && e.key.toLowerCase() === "y")) { e.preventDefault(); act("redo"); } else if (z) { e.preventDefault(); act("undo"); } else if ((e.key === "Delete" || e.key === "Backspace") && selV >= 0) { e.preventDefault(); removeV(selV); } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); act("save"); } });

  const payload = () => JSON.stringify({ version: 1, saved: new Date().toISOString(), crs: "viewer metres: x east, z south, origin = centre of the 4000x3000 satellite block (UTM 43N top-left 808152 E, 1418908 N, 0.5 m/px)", parcels: parcels.map(p => ({ id: p.id, ring: p.ring, m2: p.m2 })) }, null, 1);
  async function save() { let pw = null; try { pw = localStorage.getItem("edpw"); } catch { } if (!pw) pw = prompt("Editor password"); if (!pw) return; const body = payload(), hd = { Authorization: "Basic " + btoa("editor:" + pw), "Content-Type": "application/json" };
    st("Saving…"); try { const r = await fetch("edits/parcels.json", { method: "PUT", headers: hd, body });
      if (r.status === 401 || r.status === 403) { try { localStorage.removeItem("edpw"); } catch { } st("Wrong password"); return toast("Wrong password, try Save again"); }
      if (!r.ok) throw new Error(r.status); try { localStorage.setItem("edpw", pw); } catch { } fetch(`edits/history/${Date.now()}.json`, { method: "PUT", headers: hd, body }).catch(() => { });
      baseline = snap(); changed(false); toast("Saved. The live page now shows these boundaries."); } catch (err) { st("Could not save here (" + err.message + ")"); toast("Save failed. Use Download file and send it over."); } }
  function act(a) {
    if (a === "undo" && undo.length) { redo.push(lastState); lastState = undo.pop(); restore(lastState); } else if (a === "redo" && redo.length) { undo.push(lastState); lastState = redo.pop(); restore(lastState); }
    else if (a === "new") { const p = pick({ clientX: innerWidth / 2, clientY: innerHeight / 2 }); if (!p) return; const s = Math.max(15, camera.position.distanceTo(p) * 0.06), r2 = n => Math.round(n * 100) / 100;
      let k = 1; while (parcels.find(a => a.id === String(k).padStart(2, "0"))) k++; const np = { id: String(k).padStart(2, "0"), ring: [[-s, -s], [s, -s], [s, s], [-s, s]].map(([dx, dz]) => [r2(p.x + dx), r2(p.z + dz)]) };
      parcels.push(np); redraw(np); parcels.sort((a, b) => a.id.localeCompare(b.id)); commit(); select(np, false); }
    else if (a === "del" && cur && confirm(`Delete parcel ${cur.id}?`)) { const p = cur; select(null, false); cur = null; drop(p); layout(); commit(); markDirty(); }
    else if (a === "revert" && unsaved && confirm("Discard all changes since the last save?")) { undo.push(lastState); lastState = baseline; restore(baseline); }
    else if (a === "save") save();
    else if (a === "dl") { const u = URL.createObjectURL(new Blob([payload()], { type: "application/json" })), l = document.createElement("a"); l.href = u; l.download = "parcels.json"; l.click(); setTimeout(() => URL.revokeObjectURL(u), 2000); } }
  panel.addEventListener("click", e => { const a = e.target.dataset?.e; if (a) act(a); });
  panel.querySelector("#edtrees").addEventListener("change", e => { treeG.visible = e.target.checked; reshadow(); markDirty(); });
  addEventListener("beforeunload", e => { if (unsaved) { e.preventDefault(); e.returnValue = ""; } });
  buttons(); window.__ed = { payload, parcels, act };
}
