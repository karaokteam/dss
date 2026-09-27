import { useEffect, useRef } from "react";
import worldUrl from "world-atlas/countries-50m.json?url";
import { api } from "../api";

// Açılış animasyonu (~6 sn): dünya dönüp üsse kilitlenir, yakınlaşır ve operasyon ekranına geçer.
// Tıklama ya da herhangi bir tuş atlatır. Tuvale elle ortografik izdüşüm (yalnızca çizgi, dolgu yok).

type Lines = { xyz: Float32Array; starts: Uint32Array };   // birim küre vektörleri + her çizginin başlangıç indisi
type Topo = {
  transform: { scale: [number, number]; translate: [number, number] }; arcs: [number, number][][];
  objects: { countries: { geometries: { type: string; arcs: number[][] | number[][][] }[] } };
};
type View = { ex: number; ey: number; nx: number; ny: number; nz: number; vx: number; vy: number; vz: number };

const DEG = Math.PI / 180;
const T = { spinEnd: 3.4, lock: 3.2, titleOut: 4.1, zoom: 4.55, fade: 5.3, end: 6.05 };   // saniye
const START = { lon: 105, lat: 30 };
const ZMAX = 60;                       // son yakınlaşma katı
const ORBITS = [{ rx: 1.64, ry: 1.64, rot: 0 }, { rx: 1.8, ry: 0.6, rot: -0.22 }, { rx: 1.42, ry: 1.02, rot: 0.55 }];

const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
const phase = (t: number, a: number, b: number) => clamp01((t - a) / (b - a));
const easeOut = (x: number) => 1 - (1 - x) ** 3;
const easeInOut = (x: number) => (x < 0.5 ? 4 * x * x * x : 1 - (-2 * x + 2) ** 3 / 2);

function lines(polys: [number, number][][]): Lines {
  const n = polys.reduce((s, p) => s + p.length, 0);
  const xyz = new Float32Array(n * 3), starts = new Uint32Array(polys.length + 1);
  let k = 0;
  polys.forEach((p, j) => {
    starts[j] = k;
    for (const [lon, lat] of p) {
      const l = lon * DEG, f = lat * DEG, c = Math.cos(f);
      xyz[k * 3] = c * Math.cos(l); xyz[k * 3 + 1] = c * Math.sin(l); xyz[k * 3 + 2] = Math.sin(f); k++;
    }
  });
  starts[polys.length] = k;
  return { xyz, starts };
}

// TopoJSON yayları: tek ülkenin kullandığı yay kıyı, iki ülkenin paylaştığı yay sınır
function decodeWorld(topo: Topo) {
  const { scale: [sx, sy], translate: [tx, ty] } = topo.transform;
  const used = new Uint8Array(topo.arcs.length);
  const mark = (i: number) => { used[i < 0 ? ~i : i]++; };
  for (const g of topo.objects.countries.geometries) {
    const polys = g.type === "Polygon" ? [g.arcs as number[][]] : g.type === "MultiPolygon" ? (g.arcs as number[][][]) : [];
    polys.forEach((poly) => poly.forEach((ring) => ring.forEach(mark)));
  }
  const arcs = topo.arcs.map((a) => {
    let x = 0, y = 0;
    return a.map(([dx, dy]) => { x += dx; y += dy; return [x * sx + tx, y * sy + ty] as [number, number]; });
  });
  return { coast: lines(arcs.filter((_, i) => used[i] === 1)), border: lines(arcs.filter((_, i) => used[i] > 1)) };
}

function graticule(step = 15): Lines {
  const polys: [number, number][][] = [];
  for (let lon = -180; lon < 180; lon += step) { const p: [number, number][] = []; for (let lat = -80; lat <= 80; lat += 2) p.push([lon, lat]); polys.push(p); }
  for (let lat = -75; lat <= 75; lat += step) { const p: [number, number][] = []; for (let lon = -180; lon <= 180; lon += 2) p.push([lon, lat]); polys.push(p); }
  return lines(polys);
}

// Ortografik izdüşüm: (lon0, lat0) ekran merkezine bakar
function view(lon0: number, lat0: number): View {
  const l = lon0 * DEG, f = lat0 * DEG, cl = Math.cos(l), sl = Math.sin(l), cf = Math.cos(f), sf = Math.sin(f);
  return { ex: -sl, ey: cl, nx: -sf * cl, ny: -sf * sl, nz: cf, vx: cf * cl, vy: cf * sl, vz: sf };
}

function project({ xyz, starts }: Lines, v: View, cx: number, cy: number, R: number) {
  const path = new Path2D();
  for (let j = 0; j + 1 < starts.length; j++) {
    let pen = false;
    for (let k = starts[j] * 3, end = starts[j + 1] * 3; k < end; k += 3) {
      const x = xyz[k], y = xyz[k + 1], z = xyz[k + 2];
      if (x * v.vx + y * v.vy + z * v.vz <= 0) { pen = false; continue; }   // arka yarıküre
      const px = cx + R * (x * v.ex + y * v.ey), py = cy - R * (x * v.nx + y * v.ny + z * v.nz);
      if (pen) path.lineTo(px, py); else { path.moveTo(px, py); pen = true; }
    }
  }
  return path;
}

function projectPoint(lon: number, lat: number, v: View, cx: number, cy: number, R: number) {
  const l = lon * DEG, f = lat * DEG, c = Math.cos(f), x = c * Math.cos(l), y = c * Math.sin(l), z = Math.sin(f);
  if (x * v.vx + y * v.vy + z * v.vz <= 0) return null;
  return { x: cx + R * (x * v.ex + y * v.ey), y: cy - R * (x * v.nx + y * v.ny + z * v.nz) };
}

function makeStars(n: number) {
  let s = 7;
  const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  return Array.from({ length: n }, () => ({ x: rnd(), y: rnd(), r: 0.6 + rnd() * 1.1, a: 0.12 + rnd() * 0.45, p: rnd() * 6.3 }));
}

const HUD = "absolute font-mono text-[11px] tracking-[0.18em] leading-5";
const CORNER = "absolute w-5 h-5 border-sky-400/50";

export default function Intro({ onDone }: { onDone: () => void }) {
  const root = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const title = useRef<HTMLDivElement>(null);
  const status = useRef<HTMLDivElement>(null);
  const clock = useRef<HTMLDivElement>(null);
  const lonEl = useRef<HTMLSpanElement>(null);
  const latEl = useRef<HTMLSpanElement>(null);
  const done = useRef(onDone);
  done.current = onDone;

  useEffect(() => {
    const el = root.current!, cv = canvas.current!, ctx = cv.getContext("2d")!;
    const base = { lat: 39.92184, lon: 32.85306 };
    const grat = graticule(), stars = makeStars(220);
    let world: ReturnType<typeof decodeWorld> | null = null, ready = false;
    fetch(worldUrl).then((r) => r.json()).then((topo: Topo) => { world = decodeWorld(topo); }).catch(() => {}).finally(() => { ready = true; });
    api.overview().then((o) => { base.lat = o.base.lat; base.lon = o.base.lon; }).catch(() => {});

    let w = 0, h = 0, dpr = 1;
    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2); w = window.innerWidth; h = window.innerHeight;
      cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
    };
    resize();

    let t = 0, waited = 0, last = performance.now(), raf = 0, finished = false, skipAt: number | null = null;
    const skip = () => { if (skipAt === null) skipAt = t; };
    const text = (node: HTMLElement | null, s: string) => { if (node && node.textContent !== s) node.textContent = s; };

    const finish = () => { if (!finished) { finished = true; done.current(); } };
    const frame = (now: number) => {
      try { draw(now); } catch { finish(); }   // çizim hatası uygulamayı kilitlemesin
    };
    const draw = (now: number) => {
      const dt = Math.max(0, Math.min(0.1, (now - last) / 1000)); last = now;   // ilk kare damgası mount anından önce olabilir
      if (ready || skipAt !== null || (waited += dt) > 1.5) t += dt;   // harita verisini en çok 1.5 sn bekle

      let op = 1 - easeInOut(phase(t, T.fade, T.end));
      if (skipAt !== null) op = Math.min(op, 1 - (t - skipAt) / 0.35);
      if (op <= 0) { finish(); return; }
      el.style.opacity = String(op);
      el.style.pointerEvents = t > T.fade || skipAt !== null ? "none" : "auto";

      // dönüş → kilit → yakınlaşma
      const sp = easeInOut(phase(t, 0.15, T.spinEnd));
      const lon0 = START.lon + (base.lon - START.lon) * sp, lat0 = START.lat + (base.lat - START.lat) * sp;
      const zp = phase(t, T.zoom, T.end), zf = Math.exp(Math.log(ZMAX) * zp ** 1.5);
      const ga = easeOut(phase(t, 0, 0.8));                         // küre belirme
      const R0 = Math.min(0.395 * h, 0.36 * w), R = R0 * zf * (0.92 + 0.08 * ga);
      const cx = w / 2, cy = h * (0.59 - 0.09 * easeInOut(clamp01(zp * 2)));
      const v = view(lon0, lat0), u = R0 / 320;

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.globalAlpha = 1;
      ctx.fillStyle = "#02060c"; ctx.fillRect(0, 0, w, h);
      const bg = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.max(w, h) * 0.8);
      bg.addColorStop(0, "rgba(14,40,80,0.5)"); bg.addColorStop(1, "rgba(2,6,12,0)");
      ctx.fillStyle = bg; ctx.fillRect(0, 0, w, h);
      ctx.fillStyle = "#cbd5e1";
      for (const s of stars) { ctx.globalAlpha = s.a * (0.7 + 0.3 * Math.sin(t * 2 + s.p)); ctx.fillRect(s.x * w, s.y * h, s.r, s.r); }

      // atmosfer + küre
      ctx.globalAlpha = ga;
      const atm = ctx.createRadialGradient(cx, cy, R * 0.96, cx, cy, R * 1.28);
      atm.addColorStop(0, "rgba(59,150,255,0.5)"); atm.addColorStop(0.25, "rgba(40,110,230,0.2)"); atm.addColorStop(1, "rgba(20,60,160,0)");
      ctx.fillStyle = atm; ctx.beginPath(); ctx.arc(cx, cy, R * 1.28, 0, Math.PI * 2); ctx.fill();
      const sph = ctx.createRadialGradient(cx - R * 0.2, cy - R * 0.25, R * 0.05, cx, cy, R);
      sph.addColorStop(0, "#0a1726"); sph.addColorStop(0.7, "#081a2e"); sph.addColorStop(0.92, "#0d3052"); sph.addColorStop(1, "#1d5f96");
      ctx.fillStyle = sph; ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.fill();

      ctx.lineJoin = "round"; ctx.lineCap = "round";
      ctx.strokeStyle = "rgba(70,130,210,0.17)"; ctx.lineWidth = 0.7; ctx.stroke(project(grat, v, cx, cy, R));
      if (world) {
        ctx.strokeStyle = "rgba(70,150,230,0.4)"; ctx.stroke(project(world.border, v, cx, cy, R));
        const coast = project(world.coast, v, cx, cy, R);
        ctx.strokeStyle = "rgba(56,189,248,0.16)"; ctx.lineWidth = 3.2; ctx.stroke(coast);   // parıltı
        const g = ctx.createLinearGradient(cx - R, cy - R, cx + R * 0.8, cy + R);
        g.addColorStop(0, "#2d7dd2"); g.addColorStop(0.45, "#3aa7ea"); g.addColorStop(0.72, "#4fdccf"); g.addColorStop(1, "#8dffd8");
        ctx.strokeStyle = g; ctx.lineWidth = 1.1; ctx.stroke(coast);
      }
      ctx.strokeStyle = "rgba(125,200,255,0.85)"; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.stroke();

      // yörüngeler + uydu (yakınlaşırken söner)
      const oa = ga * (1 - clamp01(zp * 3));
      if (oa > 0) {
        ctx.globalAlpha = oa; ctx.strokeStyle = "rgba(148,163,184,0.13)"; ctx.lineWidth = 1;
        for (const o of ORBITS) { ctx.beginPath(); ctx.ellipse(cx, cy, o.rx * R, o.ry * R, o.rot, 0, Math.PI * 2); ctx.stroke(); }
        const o = ORBITS[1], a = t * 0.8 + 1.2;
        const lx = o.rx * R * Math.cos(a), ly = o.ry * R * Math.sin(a);
        const sx = cx + lx * Math.cos(o.rot) - ly * Math.sin(o.rot), sy = cy + lx * Math.sin(o.rot) + ly * Math.cos(o.rot);
        if (Math.sin(a) > 0 || Math.hypot(sx - cx, sy - cy) > R) {     // kürenin arkasındayken gizli
          const halo = ctx.createRadialGradient(sx, sy, 0, sx, sy, 9);
          halo.addColorStop(0, "rgba(255,255,255,0.9)"); halo.addColorStop(0.25, "rgba(186,230,253,0.5)"); halo.addColorStop(1, "rgba(186,230,253,0)");
          ctx.fillStyle = halo; ctx.beginPath(); ctx.arc(sx, sy, 9, 0, Math.PI * 2); ctx.fill();
        }
      }

      // hedef kilidi: halkalar dışarıdan daralır, çentikler dönerek yerine oturur
      const lk = phase(t, T.lock, T.lock + 0.55), p = lk > 0 ? projectPoint(base.lon, base.lat, v, cx, cy, R) : null;
      if (p) {
        const e = easeOut(lk), rs = zf ** 0.65 * u;
        const outer = 34 * rs * (1 + 2 * (1 - e)), inner = 14 * rs, rot = (-21 - 70 * (1 - e)) * DEG;
        ctx.globalAlpha = ga * e;
        ctx.strokeStyle = "rgba(248,113,113,0.9)"; ctx.fillStyle = "rgba(248,113,113,0.95)"; ctx.lineWidth = Math.max(1.2, 1.4 * rs);
        ctx.beginPath(); ctx.arc(p.x, p.y, outer, 0, Math.PI * 2); ctx.stroke();
        ctx.beginPath(); ctx.arc(p.x, p.y, inner, 0, Math.PI * 2); ctx.stroke();
        ctx.beginPath(); ctx.arc(p.x, p.y, 4.5 * rs, 0, Math.PI * 2); ctx.fill();
        ctx.lineWidth = Math.max(1, 0.8 * rs);
        for (let i = 0; i < 4; i++) {
          const a = rot + (i * Math.PI) / 2, c = Math.cos(a), s = Math.sin(a);
          ctx.beginPath(); ctx.moveTo(p.x + c * outer * 0.7, p.y + s * outer * 0.7); ctx.lineTo(p.x + c * outer * 1.45, p.y + s * outer * 1.45); ctx.stroke();
        }
        const pulse = ((t - T.lock) % 1.1) / 1.1;
        ctx.globalAlpha = ga * e * (1 - pulse) * 0.5 * (1 - zp); ctx.lineWidth = 1;
        ctx.beginPath(); ctx.arc(p.x, p.y, outer * (1 + pulse * 1.3), 0, Math.PI * 2); ctx.stroke();

        const la = phase(t, T.lock + 0.25, T.lock + 0.75);       // etiket daktilo gibi yazılır
        if (la > 0) {
          const name = "MERKEZ ÜS", coords = `${base.lat.toFixed(4)}°N · ${base.lon.toFixed(4)}°E`;
          ctx.globalAlpha = ga;
          ctx.font = "600 12px ui-monospace, SFMono-Regular, Menlo, monospace"; ctx.fillStyle = "#fca5a5";
          ctx.fillText(name.slice(0, Math.ceil(name.length * la)), p.x + 30, p.y - 3);
          ctx.font = "10px ui-monospace, SFMono-Regular, Menlo, monospace"; ctx.fillStyle = "rgba(203,213,225,0.75)";
          ctx.fillText(coords.slice(0, Math.ceil(coords.length * la)), p.x + 30, p.y + 11);
        }
      }

      // yazılar
      const tl = title.current;
      if (tl) {
        const ls = 0.45 + 0.3 * (1 - easeOut(phase(t, 0.1, 1.2)));
        tl.style.opacity = String(easeOut(phase(t, 0.1, 0.9)) * (1 - phase(t, T.titleOut, T.titleOut + 0.5)));
        tl.style.letterSpacing = tl.style.paddingLeft = `${ls}em`;
      }
      text(status.current, t < T.lock ? "SİSTEM BAŞLATILIYOR" + ".".repeat(Math.floor(t * 3) % 4) : "HEDEF KİLİTLENDİ · MERKEZ ÜS");
      text(clock.current, new Date().toLocaleTimeString("tr-TR", { hour12: false }));
      text(lonEl.current, lon0.toFixed(4));
      text(latEl.current, lat0.toFixed(4));

      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);

    window.addEventListener("resize", resize);
    window.addEventListener("keydown", skip);
    el.addEventListener("pointerdown", skip);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      window.removeEventListener("keydown", skip);
      el.removeEventListener("pointerdown", skip);
    };
  }, []);

  return (
    <div ref={root} className="fixed inset-0 z-[10000] overflow-hidden select-none cursor-pointer bg-[#02060c]">
      <canvas ref={canvas} className="absolute inset-0 w-full h-full" />
      <i className={`${CORNER} left-2 top-2 border-l border-t`} />
      <i className={`${CORNER} right-2 top-2 border-r border-t`} />
      <i className={`${CORNER} left-2 bottom-2 border-l border-b`} />
      <i className={`${CORNER} right-2 bottom-2 border-r border-b`} />
      <div className={`${HUD} left-6 top-5`}>
        <div className="text-slate-500">ÜS GÖZETİM VE ANALİZ SİSTEMİ</div>
        <div ref={status} className="text-slate-100 font-bold">SİSTEM BAŞLATILIYOR</div>
      </div>
      <div className={`${HUD} right-6 top-5 text-right`}>
        <div ref={clock} className="text-slate-100 font-bold" />
        <div className="text-slate-500">WGS84 · EPSG:4326</div>
      </div>
      <div className={`${HUD} left-6 bottom-5`}>
        <div><span className="text-slate-500 inline-block w-16">BOYLAM</span><span ref={lonEl} className="text-slate-100" /></div>
        <div><span className="text-slate-500 inline-block w-16">ENLEM</span><span ref={latEl} className="text-slate-100" /></div>
      </div>
      <div className={`${HUD} right-6 bottom-5 !text-[10px] text-slate-600`}>ATLAMAK İÇİN TIKLA</div>
      <div ref={title} className="absolute inset-x-0 text-center text-slate-50 pointer-events-none"
        style={{ top: "7.5vh", fontSize: "min(11.5vh, 13vw)", fontWeight: 600, lineHeight: 1, opacity: 0,
          fontFamily: '"Segoe UI", system-ui, -apple-system, sans-serif',
          textShadow: "0 0 18px rgba(125,211,252,.55), 0 0 44px rgba(56,189,248,.35)" }}>KARAOK</div>
    </div>
  );
}
