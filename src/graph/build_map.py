"""
Blocco B (parte 2) - visualizzazione su MAPPA delle relazioni tra i paesi.

Genera un unico file HTML autosufficiente (data/processed/graphs/grafo_mappa.html)
con un planisfero tematico interattivo:

- si apre "vuoto": si vedono solo i 17 paesi del progetto, evidenziati e
  colorati per gruppo, su un planisfero chiaro di contesto;
- gli ARCHI sono spenti all'avvio e si accendono da un pannello, un tipo alla
  volta (Cyber / Migrazione / Coinvolgimento militare);
- ogni arco e' curvo e diretto; lungo l'arco scorrono dei puntini luminosi
  dall'origine alla destinazione (verso attaccante->vittima, ecc.);
- SLIDER TEMPORALE (2018–2024 + "Tutti") con play/pausa per far scorrere gli anni;
- bottone PAESI PERIFERICI: di default off (solo i 17 paesi); attivandolo
  compaiono anche i paesi esterni coinvolti (con il loro nome se non sono troppi);
- TEMA chiaro/scuro, controllo ZOOM in basso, zoom con rotella, trascinamento,
  clic su un paese per isolarne le relazioni.

Nessuna libreria esterna: SVG + JavaScript vanilla, dati e geometrie inline.
Asset (scaricati una volta in src/graph/assets/):
- countries.geo.json  (confini paese, id = ISO alpha-3)   johan/world.geo.json
- centroids.json      (lat/lon rappresentativa per ISO3)  eesur/country-codes-lat-long
"""

import json
from collections import defaultdict
from pathlib import Path

import pandas as pd
import yaml

BASE = Path(__file__).resolve().parents[2]
ASSETS = Path(__file__).resolve().parent / "assets"
CONFIG = BASE / "config" / "countries.yaml"
ARCHI = BASE / "data" / "processed" / "graphs" / "archi.csv"
OUT = BASE / "data" / "processed" / "graphs" / "grafo_mappa.html"

# finestra temporale del progetto (lo slider si muove qui dentro)
ANNI = list(range(2018, 2025))
ANNI_SET = {str(a) for a in ANNI}

# centroidi mancanti nella tabella (punti rappresentativi manuali)
CENTROIDI_EXTRA = {"SSD": (7.5, 30.0), "CUW": (12.2, -69.0), "SXM": (18.04, -63.05)}

GRUPPI = {
    1: {"nome": "Attori cyber offensivi", "col": "#c1121f"},
    2: {"nome": "Alta instabilità", "col": "#e07a1e"},
    3: {"nome": "Bersagli cyber", "col": "#1f6feb"},
    4: {"nome": "Casi di controllo", "col": "#2a9d8f"},
}
TIPI = {
    "cyber": {"nome": "Cyber  ·  attaccante → vittima", "col": "#e63946"},
    "migrazione": {"nome": "Migrazione  ·  origine → destinazione", "col": "#3a7ca5"},
    "militare": {"nome": "Coinvolgimento militare  ·  interventore → teatro", "col": "#e8912d"},
}


def _carica_paesi() -> dict:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    return {p["iso3"]: p for p in cfg["paesi"]}


def _centroidi() -> tuple:
    dati = json.loads((ASSETS / "centroids.json").read_text(encoding="utf-8"))
    coord = {c["alpha3"]: (float(c["latitude"]), float(c["longitude"]))
             for c in dati["ref_country_codes"]}
    nome = {c["alpha3"]: c["country"] for c in dati["ref_country_codes"]}
    coord.update(CENTROIDI_EXTRA)
    return coord, nome


def _round_coords(obj, nd=2):
    if isinstance(obj, list):
        if obj and isinstance(obj[0], (int, float)):
            return [round(float(obj[0]), nd), round(float(obj[1]), nd)]
        return [_round_coords(x, nd) for x in obj]
    return obj


def _geojson_slim(core: set) -> dict:
    g = json.loads((ASSETS / "countries.geo.json").read_text(encoding="utf-8"))
    for f in g["features"]:
        f["geometry"]["coordinates"] = _round_coords(f["geometry"]["coordinates"])
        f["properties"] = {"core": f.get("id") in core}
    return g


def _tipo_valore(riga):
    """(tipo_breve, valore, unita) per una riga di archi.csv."""
    t = riga["tipo"]
    if t == "cyber":
        return "cyber", 1, "incidenti"
    if t == "migrazione":
        return "migrazione", (0 if pd.isna(riga["peso"]) else int(riga["peso"])), "rifugiati"
    if t == "coinvolgimento_militare":
        return "militare", (0 if pd.isna(riga["peso"]) else int(riga["peso"])), "eventi militari"
    return None, 0, ""


def _anno(periodo) -> str:
    p = str(periodo)
    return p[:4] if p[:4].isdigit() else None


def _nodi(paesi: dict, coord: dict, nome: dict, usati: set) -> list:
    nodi = []
    for iso3 in sorted(usati | set(paesi)):
        if iso3 not in coord:
            continue
        lat, lon = coord[iso3]
        if iso3 in paesi:
            nodi.append({"iso3": iso3, "nome": paesi[iso3].get("nome", iso3),
                         "gruppo": paesi[iso3].get("gruppo"), "lat": lat, "lon": lon, "core": True})
        else:
            nodi.append({"iso3": iso3, "nome": nome.get(iso3, iso3),
                         "gruppo": None, "lat": lat, "lon": lon, "core": False})
    return nodi


def _archi(core: set, coord: dict) -> tuple:
    """Aggrega archi.csv per (da, a, tipo): totale + dettaglio per anno (nella
    finestra 2018–2024). Ritorna (archi, paesi_usati, conteggi_core)."""
    df = pd.read_csv(ARCHI)
    acc = {}
    for _, r in df.iterrows():
        a, b = r["da"], r["a"]
        if a not in coord or b not in coord:      # senza coordinate non si disegna
            continue
        t, val, u = _tipo_valore(r)
        if t is None:
            continue
        k = (a, b, t)
        e = acc.get(k)
        if e is None:
            e = acc[k] = {"a": a, "b": b, "t": t, "u": u,
                          "per": not (a in core and b in core), "tot": 0, "y": defaultdict(int)}
        e["tot"] += val
        anno = _anno(r["periodo"])
        if anno in ANNI_SET:
            e["y"][anno] += val

    archi, usati, conteggi = [], set(), defaultdict(int)
    for e in acc.values():
        e["y"] = dict(e["y"])
        archi.append(e)
        usati.add(e["a"]); usati.add(e["b"])
        if not e["per"]:
            conteggi[e["t"]] += 1
    return archi, usati, dict(conteggi)


def costruisci(verbose: bool = True) -> Path:
    paesi = _carica_paesi()
    core = set(paesi)
    coord, nome = _centroidi()

    archi, usati, conteggi = _archi(core, coord)
    nodi = _nodi(paesi, coord, nome, usati)
    world = _geojson_slim(core)

    meta = {
        "gruppi": GRUPPI,
        "tipi": {t: {**info, "n": conteggi.get(t, 0)} for t, info in TIPI.items()},
        "anni": ANNI,
    }

    html = (_TEMPLATE
            .replace("__WORLD__", json.dumps(world, separators=(",", ":")))
            .replace("__NODI__", json.dumps(nodi, ensure_ascii=False, separators=(",", ":")))
            .replace("__ARCHI__", json.dumps(archi, ensure_ascii=False, separators=(",", ":")))
            .replace("__META__", json.dumps(meta, ensure_ascii=False)))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    if verbose:
        kb = OUT.stat().st_size / 1024
        core_n = sum(1 for n in nodi if n["core"])
        print(f"Mappa scritta in {OUT}  ({kb:.0f} KB)")
        print(f"  nodi: {len(nodi)} ({core_n} core + {len(nodi)-core_n} periferici)")
        print(f"  archi: {len(archi)}  (coppie core per tipo: {conteggi})")
    return OUT


# =========================================================================== #
#  TEMPLATE HTML  (SVG + JS vanilla, tutto inline)
# =========================================================================== #
_TEMPLATE = r"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Relazioni geopolitico-cyber · mappa interattiva</title>
<style>
  :root{
    --bg:#f4f1ea; --ocean:#e7ecf1; --land:#d7dce3; --land-b:#ffffff;
    --ink:#20242b; --muted:#5d6570; --card:#ffffff; --line:#e2e5ea;
    --lbl:#1b1f26; --lbl-halo:#ffffff; --perif-lbl:#5a636e; --credit-bg:rgba(244,241,234,.72);
  }
  body.dark{
    --bg:#0e1116; --ocean:#0d1218; --land:#212836; --land-b:#2c3442;
    --ink:#e9ecf1; --muted:#98a1ad; --card:#161b22; --line:#2a313b;
    --lbl:#eef1f5; --lbl-halo:#0d1218; --perif-lbl:#9aa3af; --credit-bg:rgba(13,18,24,.72);
  }
  *{box-sizing:border-box}
  html,body{margin:0;height:100%;font-family:-apple-system,BlinkMacSystemFont,
    "Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg)}
  #app{position:fixed;inset:0;overflow:hidden}
  #map{width:100%;height:100%;background:var(--ocean);cursor:grab;display:block}
  #map.dragging{cursor:grabbing}

  .land{fill:var(--land);stroke:var(--land-b);stroke-width:.7px;vector-effect:non-scaling-stroke}
  .core{stroke-width:1px;vector-effect:non-scaling-stroke;cursor:pointer}
  .node-dot{stroke:var(--card);stroke-width:1.2px;vector-effect:non-scaling-stroke;cursor:pointer}
  .node-lbl{font-size:7px;font-weight:700;fill:var(--lbl);paint-order:stroke;stroke:var(--lbl-halo);
    stroke-width:2.4px;vector-effect:non-scaling-stroke;text-anchor:middle;pointer-events:none;user-select:none}
  .perif{fill:#8a94a3;stroke:var(--card);stroke-width:.8px;vector-effect:non-scaling-stroke;cursor:pointer}
  .perif-lbl{font-size:5.5px;font-weight:600;fill:var(--perif-lbl);paint-order:stroke;stroke:var(--lbl-halo);
    stroke-width:1.7px;vector-effect:non-scaling-stroke;text-anchor:middle;pointer-events:none;user-select:none}
  .faded{opacity:.16}

  .arc{fill:none;stroke-width:1.3px;vector-effect:non-scaling-stroke;opacity:.5;cursor:pointer}
  .arc.per{opacity:.28;stroke-width:1px}
  .arc:hover,.arc.hot{opacity:1;stroke-width:2.6px}
  #part circle{pointer-events:none}

  #panel{position:absolute;top:16px;left:16px;width:292px;max-height:calc(100% - 32px);
    overflow:auto;background:var(--card);border:1px solid var(--line);border-radius:14px;
    box-shadow:0 8px 30px rgba(10,15,25,.16);padding:16px 16px 14px}
  .phead{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}
  #panel h1{font-size:15px;margin:0 0 2px;letter-spacing:.2px}
  #theme{flex:0 0 auto;width:30px;height:28px;border:1px solid var(--line);background:var(--card);
    color:var(--ink);border-radius:8px;cursor:pointer;font-size:13px;line-height:1}
  #theme:hover{border-color:#9aa3af}
  #panel .sub{font-size:11.5px;color:var(--muted);margin:2px 0 12px;line-height:1.45}
  .sec{font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:.7px;
    color:var(--muted);margin:14px 0 8px}
  .toggle{display:flex;align-items:center;gap:10px;width:100%;border:1px solid var(--line);
    background:transparent;border-radius:10px;padding:9px 11px;margin-bottom:8px;cursor:pointer;
    font-size:12.5px;color:var(--ink);text-align:left}
  .toggle:hover{border-color:#9aa3af}
  .toggle .sw{width:26px;height:4px;border-radius:3px;flex:0 0 auto;opacity:.35}
  .toggle .dotmark{width:11px;height:11px;border-radius:50%;flex:0 0 auto;opacity:.5}
  .toggle .tx{flex:1;line-height:1.25}
  .toggle .ct{font-variant-numeric:tabular-nums;color:var(--muted);font-size:11px}
  .toggle.on{border-color:transparent;background:var(--ink);color:var(--card);box-shadow:0 3px 10px rgba(10,15,25,.2)}
  .toggle.on .sw,.toggle.on .dotmark{opacity:1}
  .toggle.on .ct{color:var(--card);opacity:.7}
  #timerow{display:flex;align-items:center;gap:9px}
  #play{width:30px;height:28px;border:1px solid var(--line);background:var(--card);color:var(--ink);
    border-radius:8px;cursor:pointer;font-size:12px;line-height:1;flex:0 0 auto}
  #play:hover{border-color:#9aa3af}
  #slider,#zoom{accent-color:var(--ink)}
  #slider{flex:1}
  #ylab{font-variant-numeric:tabular-nums;font-size:12.5px;font-weight:700;min-width:40px;text-align:right}
  .legend{display:flex;align-items:center;gap:9px;font-size:12px;color:var(--ink);margin:6px 0}
  .legend .dot{width:12px;height:12px;border-radius:50%;flex:0 0 auto}
  .hint{font-size:11px;color:var(--muted);line-height:1.5;margin-top:12px;padding-top:12px;border-top:1px solid var(--line)}
  .hint b{color:var(--ink);font-weight:600}
  #reset{margin-top:10px;width:100%;border:1px solid var(--line);background:var(--card);border-radius:9px;
    padding:7px;font-size:11.5px;color:var(--muted);cursor:pointer}
  #reset:hover{border-color:#9aa3af;color:var(--ink)}

  #zoombar{position:absolute;left:50%;bottom:20px;transform:translateX(-50%);display:flex;align-items:center;
    gap:9px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:6px 11px;
    box-shadow:0 6px 20px rgba(10,15,25,.16)}
  .zb{width:26px;height:24px;border:1px solid var(--line);background:var(--card);color:var(--ink);
    border-radius:7px;cursor:pointer;font-size:15px;line-height:1;display:flex;align-items:center;justify-content:center}
  .zb:hover{border-color:#9aa3af}
  #zoom{width:150px}

  #tip{position:absolute;pointer-events:none;background:#20242b;color:#fff;font-size:12px;line-height:1.4;
    padding:7px 10px;border-radius:8px;box-shadow:0 6px 20px rgba(0,0,0,.32);opacity:0;max-width:250px;z-index:5}
  #tip .verso{font-weight:700;margin-bottom:1px}
  #tip .peso{color:#d7dbe2}
  .credit{position:absolute;right:14px;bottom:11px;font-size:10.5px;color:var(--muted);
    background:var(--credit-bg);padding:3px 8px;border-radius:6px}
</style>
</head>
<body>
<div id="app">
  <svg id="map" preserveAspectRatio="xMidYMid meet"></svg>
  <div id="panel">
    <div class="phead">
      <h1>Relazioni geopolitico-cyber</h1>
      <button id="theme" title="Tema chiaro / scuro">🌙</button>
    </div>
    <p class="sub">17 paesi osservati · 2018–2024. Accendi un tipo di relazione;
      i puntini scorrono dall'origine alla destinazione.</p>
    <div class="sec">Relazioni</div>
    <div id="toggles"></div>
    <div class="sec">Periodo</div>
    <div id="timerow">
      <button id="play" title="Scorri gli anni">▶</button>
      <input id="slider" type="range">
      <span id="ylab">Tutti</span>
    </div>
    <div class="sec">Opzioni</div>
    <button id="perif" class="toggle">
      <span class="dotmark" style="background:#8a94a3"></span>
      <span class="tx">Paesi periferici</span></button>
    <div class="sec">Paesi per gruppo</div>
    <div id="gruppi"></div>
    <button id="reset">↺ reimposta vista</button>
    <div class="hint"><b>Rotella</b> = zoom · <b>trascina</b> = sposta ·
      <b>clic su un paese</b> = isola le sue relazioni</div>
  </div>
  <div id="zoombar">
    <button class="zb" id="zout" title="Riduci">–</button>
    <input id="zoom" type="range" min="0" max="100" value="0">
    <button class="zb" id="zin" title="Ingrandisci">+</button>
  </div>
  <div id="tip"></div>
  <div class="credit">Fonti: ACLED · UNHCR · CFR Cyber Operations</div>
</div>

<script>
const WORLD = __WORLD__;
const NODI  = __NODI__;
const ARCHI = __ARCHI__;
const META  = __META__;

const svg = document.getElementById('map');
const SVGNS = 'http://www.w3.org/2000/svg';
const el = (t,a={})=>{ const e=document.createElementNS(SVGNS,t);
  for(const k in a) e.setAttribute(k,a[k]); return e; };
const proj = (lon,lat)=>[ (lon+180)/360*1000, (90-lat)/180*500 ];
const nodeByIso = Object.fromEntries(NODI.map(n=>[n.iso3,n]));

/* frecce direzionali per tipo */
const defs = el('defs');
for(const t in META.tipi){
  const m = el('marker',{id:'arr-'+t, viewBox:'0 0 10 10', refX:8, refY:5,
    markerWidth:6, markerHeight:6, orient:'auto-start-reverse', markerUnits:'userSpaceOnUse'});
  m.appendChild(el('path',{d:'M0 0 L10 5 L0 10 z', fill:META.tipi[t].col}));
  defs.appendChild(m);
}
svg.appendChild(defs);

/* terre + paesi core */
function pathD(geom){
  const polys = geom.type==='Polygon' ? [geom.coordinates] : geom.coordinates;
  let d='';
  for(const poly of polys) for(const ring of poly){
    ring.forEach((pt,i)=>{ const [x,y]=proj(pt[0],pt[1]); d+=(i?'L':'M')+x.toFixed(1)+' '+y.toFixed(1); });
    d+='Z';
  }
  return d;
}
const gLand = el('g');
for(const f of WORLD.features) gLand.appendChild(el('path',{d:pathD(f.geometry), class:'land'}));
svg.appendChild(gLand);

const isoGruppo = Object.fromEntries(NODI.filter(n=>n.core).map(n=>[n.iso3,n.gruppo]));
const gCore = el('g');
for(const f of WORLD.features){
  if(!f.properties.core) continue;
  const col = META.gruppi[isoGruppo[f.id]].col;
  const p = el('path',{d:pathD(f.geometry), class:'core', 'data-iso':f.id, fill:col,'fill-opacity':.5, stroke:col});
  p.addEventListener('mouseenter',e=>paeseTip(e,f.id));
  p.addEventListener('mousemove',muoviTip);
  p.addEventListener('mouseleave',nascondiTip);
  p.addEventListener('click',e=>{ e.stopPropagation(); setFocus(f.id); });
  gCore.appendChild(p);
}
svg.appendChild(gCore);

/* archi (tutti creati, mostrati/nascosti da refresh) */
function arcGeo(a,b){
  const [x1,y1]=proj(a.lon,a.lat), [x2,y2]=proj(b.lon,b.lat);
  const mx=(x1+x2)/2,my=(y1+y2)/2,dx=x2-x1,dy=y2-y1,len=Math.hypot(dx,dy)||1,off=Math.min(70,len*0.22);
  return {x1,y1,cx:mx-dy/len*off,cy:my+dx/len*off,x2,y2};
}
const geoD = g=>`M${g.x1.toFixed(1)} ${g.y1.toFixed(1)} Q${g.cx.toFixed(1)} ${g.cy.toFixed(1)} ${g.x2.toFixed(1)} ${g.y2.toFixed(1)}`;
const bez = (g,t)=>{ const u=1-t; return [u*u*g.x1+2*u*t*g.cx+t*t*g.x2, u*u*g.y1+2*u*t*g.cy+t*t*g.y2]; };
const gArcs = el('g'); svg.appendChild(gArcs);
const arcEls = [];
for(const e of ARCHI){
  const na=nodeByIso[e.a], nb=nodeByIso[e.b]; if(!na||!nb) continue;
  const g=arcGeo(na,nb);
  const p=el('path',{d:geoD(g), class:'arc'+(e.per?' per':''), stroke:META.tipi[e.t].col, 'marker-end':'url(#arr-'+e.t+')'});
  p.style.display='none'; p._e=e; p._g=g;
  p.addEventListener('mouseenter',ev=>{ p.classList.add('hot'); arcoTip(ev,p); });
  p.addEventListener('mousemove',muoviTip);
  p.addEventListener('mouseleave',()=>{ p.classList.remove('hot'); nascondiTip(); });
  gArcs.appendChild(p); arcEls.push(p);
}

/* nodi: periferici (sotto, con etichetta nascosta) poi core (sopra) */
const gNodes = el('g'); const perifDots={}, perifLbl={};
for(const n of NODI){ if(n.core) continue;
  const [x,y]=proj(n.lon,n.lat);
  const c=el('circle',{cx:x,cy:y,r:2.4,class:'perif','data-iso':n.iso3});
  c.style.display='none';
  c.addEventListener('mouseenter',e=>paeseTip(e,n.iso3));
  c.addEventListener('mousemove',muoviTip); c.addEventListener('mouseleave',nascondiTip);
  const tl=el('text',{x:x,y:y+8.5,class:'perif-lbl','data-iso':n.iso3});
  tl.textContent = n.nome.length>18 ? n.nome.slice(0,17)+'…' : n.nome;
  tl.style.display='none';
  perifDots[n.iso3]=c; perifLbl[n.iso3]=tl;
  gNodes.appendChild(c); gNodes.appendChild(tl);
}
for(const n of NODI){ if(!n.core) continue;
  const [x,y]=proj(n.lon,n.lat); const col=META.gruppi[n.gruppo].col;
  const c=el('circle',{cx:x,cy:y,r:3.6,class:'node-dot','data-iso':n.iso3,fill:col});
  c.addEventListener('mouseenter',e=>paeseTip(e,n.iso3));
  c.addEventListener('mousemove',muoviTip); c.addEventListener('mouseleave',nascondiTip);
  c.addEventListener('click',e=>{ e.stopPropagation(); setFocus(n.iso3); });
  const t=el('text',{x:x,y:y-6,class:'node-lbl','data-iso':n.iso3}); t.textContent=n.iso3;
  gNodes.appendChild(c); gNodes.appendChild(t);
}
svg.appendChild(gNodes);

/* particelle animate */
const gPart = el('g',{id:'part'}); svg.appendChild(gPart);
let particles=[]; const CAP=340;
function buildParticles(vis){
  gPart.textContent=''; particles=[];
  let arcs=vis;
  if(arcs.length>CAP) arcs=[...vis].sort((a,b)=>b._w-a._w).slice(0,CAP);
  for(const p of arcs){
    const col=META.tipi[p._e.t].col;
    const trail=el('circle',{r:3.0,fill:col,opacity:.22});
    const dot=el('circle',{r:1.9,fill:'#fff',stroke:col,'stroke-width':1.2});
    gPart.appendChild(trail); gPart.appendChild(dot);
    particles.push({dot,trail,g:p._g,t:Math.random(),sp:0.26+Math.random()*0.12});
  }
}
let last=0;
function tick(ts){
  const dt = last ? Math.min(0.05,(ts-last)/1000) : 0.016; last=ts;
  for(const pa of particles){
    pa.t+=pa.sp*dt; if(pa.t>1) pa.t-=1;
    const [x,y]=bez(pa.g,pa.t); pa.dot.setAttribute('cx',x); pa.dot.setAttribute('cy',y);
    const [tx,ty]=bez(pa.g,Math.max(0,pa.t-0.035)); pa.trail.setAttribute('cx',tx); pa.trail.setAttribute('cy',ty);
  }
  requestAnimationFrame(tick);
}
requestAnimationFrame(tick);

/* ---------------- stato + refresh ---------------- */
const state = { layers:{cyber:false,migrazione:false,militare:false}, year:'all', perif:false, focus:null };
const curW = e => state.year==='all' ? e.tot : (e.y[state.year]||0);
const passYear = e => state.year==='all' ? e.tot>0 : (e.y[state.year]||0)>0;
const LABEL_MAX = 28;

function refresh(){
  const vis=[];
  for(const p of arcEls){
    const e=p._e;
    let ok = state.layers[e.t] && (state.perif || !e.per) && passYear(e);
    if(ok && state.focus) ok = (e.a===state.focus || e.b===state.focus);
    p.style.display = ok ? '' : 'none';
    if(ok){ p._w = curW(e); vis.push(p); }
  }
  const attivi=new Set();
  if(state.perif) for(const p of vis){
    if(!nodeByIso[p._e.a].core) attivi.add(p._e.a);
    if(!nodeByIso[p._e.b].core) attivi.add(p._e.b);
  }
  const mostraLbl = state.perif && (!!state.focus || attivi.size<=LABEL_MAX);
  for(const iso in perifDots){
    const on=attivi.has(iso);
    perifDots[iso].style.display = on ? '' : 'none';
    perifLbl[iso].style.display = (on && mostraLbl) ? '' : 'none';
  }
  const rel=new Set();
  if(state.focus){ rel.add(state.focus); for(const p of vis){ rel.add(p._e.a); rel.add(p._e.b); } }
  gNodes.querySelectorAll('.node-dot,.node-lbl').forEach(n=>{
    n.classList.toggle('faded', !!state.focus && !rel.has(n.getAttribute('data-iso')));
  });
  gCore.querySelectorAll('.core').forEach(n=>{
    n.classList.toggle('faded', !!state.focus && !rel.has(n.getAttribute('data-iso')));
  });
  buildParticles(vis);
}

/* ---------------- tooltip ---------------- */
const tip=document.getElementById('tip');
const fmt=v=>v.toLocaleString('it-IT');
function arcoTip(e,p){ const a=p._e;
  const suff = state.year==='all' ? '' : ' · '+state.year;
  tip.innerHTML=`<div class="verso">${a.a} → ${a.b}</div><div class="peso">${fmt(p._w)} ${a.u}${suff}</div>`;
  mostraTip(e);
}
function paeseTip(e,iso){ const n=nodeByIso[iso]; if(!n) return;
  const sub = n.core ? META.gruppi[n.gruppo].nome : 'paese periferico';
  tip.innerHTML=`<div class="verso">${n.nome} (${iso})</div><div class="peso">${sub}</div>`;
  mostraTip(e);
}
function mostraTip(e){ tip.style.opacity=1; muoviTip(e); }
function muoviTip(e){
  const pad=14; let x=e.clientX+pad, y=e.clientY+pad; const r=tip.getBoundingClientRect();
  if(x+r.width>innerWidth) x=e.clientX-r.width-pad;
  if(y+r.height>innerHeight) y=e.clientY-r.height-pad;
  tip.style.left=x+'px'; tip.style.top=y+'px';
}
function nascondiTip(){ tip.style.opacity=0; }

function setFocus(iso){ state.focus = state.focus===iso ? null : iso; refresh(); }

/* ---------------- pannello ---------------- */
const box=document.getElementById('toggles');
for(const t in META.tipi){ const info=META.tipi[t];
  const b=document.createElement('button'); b.className='toggle';
  b.innerHTML=`<span class="sw" style="background:${info.col}"></span>`+
    `<span class="tx">${info.nome}</span><span class="ct">${info.n}</span>`;
  b.onclick=()=>{ state.layers[t]=!state.layers[t]; b.classList.toggle('on',state.layers[t]); refresh(); };
  box.appendChild(b);
}
const gbox=document.getElementById('gruppi');
for(const g in META.gruppi){ const info=META.gruppi[g];
  const membri=NODI.filter(n=>String(n.gruppo)===g).map(n=>n.iso3).join(' · ');
  const d=document.createElement('div'); d.className='legend';
  d.innerHTML=`<span class="dot" style="background:${info.col}"></span>`+
    `<span><b>${info.nome}</b><br><span style="color:#8b929c;font-size:11px">${membri}</span></span>`;
  gbox.appendChild(d);
}
const bperif=document.getElementById('perif');
bperif.onclick=()=>{ state.perif=!state.perif; bperif.classList.toggle('on',state.perif); refresh(); };

/* tema chiaro/scuro */
const theme=document.getElementById('theme');
function applyTheme(dark){ document.body.classList.toggle('dark',dark);
  theme.textContent = dark ? '☀️' : '🌙'; }
try{ applyTheme(localStorage.getItem('map-theme')==='dark'); }catch(e){}
theme.onclick=()=>{ const dark=!document.body.classList.contains('dark'); applyTheme(dark);
  try{ localStorage.setItem('map-theme', dark?'dark':'light'); }catch(e){} };

/* slider temporale + play */
const anni=META.anni, slider=document.getElementById('slider'), ylab=document.getElementById('ylab');
slider.min=anni[0]-1; slider.max=anni[anni.length-1]; slider.step=1; slider.value=anni[0]-1;
function setYear(v){
  if(v<=anni[0]-1){ state.year='all'; slider.value=anni[0]-1; ylab.textContent='Tutti'; }
  else { state.year=String(v); slider.value=v; ylab.textContent=v; }
  refresh();
}
slider.oninput=()=>{ stopPlay(); setYear(+slider.value); };
let playT=null;
const play=document.getElementById('play');
function stopPlay(){ if(playT){ clearInterval(playT); playT=null; play.textContent='▶'; } }
play.onclick=()=>{
  if(playT){ stopPlay(); return; }
  if(state.year==='all') setYear(anni[0]);
  play.textContent='⏸';
  playT=setInterval(()=>{
    let y = state.year==='all' ? anni[0] : parseInt(state.year);
    setYear(y>=anni[anni.length-1] ? anni[0] : y+1);
  }, 1300);
};

/* ---------------- zoom / pan ---------------- */
let vb={x:0,y:0,w:1000,h:500}, HOME_W=1000;
const ZMIN=0.6, ZMAX=16;
const zoomInput=document.getElementById('zoom');
function setVB(){ svg.setAttribute('viewBox',
  `${vb.x.toFixed(1)} ${vb.y.toFixed(1)} ${vb.w.toFixed(1)} ${vb.h.toFixed(1)}`); }
const curZoom=()=>HOME_W/vb.w;
function syncZoomUI(){ const z=curZoom();
  zoomInput.value = 100*Math.log(z/ZMIN)/Math.log(ZMAX/ZMIN); }
function setZoom(z, ax, ay){
  z=Math.max(ZMIN,Math.min(ZMAX,z));
  ax = ax==null ? vb.x+vb.w/2 : ax; ay = ay==null ? vb.y+vb.h/2 : ay;
  const nw=HOME_W/z, nh=vb.h*(nw/vb.w);
  vb.x=ax-(ax-vb.x)*(nw/vb.w); vb.y=ay-(ay-vb.y)*(nh/vb.h); vb.w=nw; vb.h=nh; setVB(); syncZoomUI();
}
function fitToNodes(){
  const P=NODI.filter(n=>n.core).map(n=>proj(n.lon,n.lat));
  let minX=Math.min(...P.map(p=>p[0])), maxX=Math.max(...P.map(p=>p[0]));
  let minY=Math.min(...P.map(p=>p[1])), maxY=Math.max(...P.map(p=>p[1]));
  const px=(maxX-minX)*0.08+16, py=(maxY-minY)*0.30+16;
  minX-=px; maxX+=px; minY-=py; maxY+=py;
  let w=maxX-minX, h=maxY-minY; const cx=(minX+maxX)/2, cy=(minY+maxY)/2;
  const r=svg.getBoundingClientRect(); const W=r.width||1400, H=r.height||900;
  const PL=Math.min(360, W*0.34); const Wc=Math.max(1,W-PL), Ac=Wc/H;
  if(w/h>Ac) h=w/Ac; else w=h*Ac;
  vb={ x: cx - w*(PL/Wc + 0.5), y: cy - h/2, w: w*(W/Wc), h };
  HOME_W=vb.w; setVB(); syncZoomUI();
}
fitToNodes(); addEventListener('resize', fitToNodes);
function toSvg(cx,cy){ const r=svg.getBoundingClientRect();
  return [ vb.x+(cx-r.left)/r.width*vb.w, vb.y+(cy-r.top)/r.height*vb.h ]; }
svg.addEventListener('wheel',e=>{ e.preventDefault();
  const [mx,my]=toSvg(e.clientX,e.clientY);
  setZoom(curZoom()*(e.deltaY<0?1.18:1/1.18), mx, my);
},{passive:false});
zoomInput.oninput=()=>{ setZoom(ZMIN*Math.pow(ZMAX/ZMIN, zoomInput.value/100)); };
document.getElementById('zin').onclick=()=>setZoom(curZoom()*1.4);
document.getElementById('zout').onclick=()=>setZoom(curZoom()/1.4);
let pan=null, moved=false;
svg.addEventListener('mousedown',e=>{ pan={x:e.clientX,y:e.clientY,vx:vb.x,vy:vb.y}; moved=false; svg.classList.add('dragging'); });
addEventListener('mousemove',e=>{ if(!pan)return; const r=svg.getBoundingClientRect();
  const dx=(e.clientX-pan.x)/r.width*vb.w, dy=(e.clientY-pan.y)/r.height*vb.h;
  if(Math.abs(e.clientX-pan.x)+Math.abs(e.clientY-pan.y)>3) moved=true;
  vb.x=pan.vx-dx; vb.y=pan.vy-dy; setVB(); });
addEventListener('mouseup',()=>{ svg.classList.remove('dragging'); pan=null; });
svg.addEventListener('click',()=>{ if(!moved && state.focus) setFocus(state.focus); });
document.getElementById('reset').onclick=()=>{ fitToNodes(); };

refresh();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    costruisci()
