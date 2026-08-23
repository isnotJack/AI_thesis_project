"""
Blocco C - visualizzazione della SIMULAZIONE su mappa.

Prende il risultato di `oasis_inspired.simula(...)` e produce un HTML
autosufficiente che mostra come il grafo evolve round per round:

- si mostra il SOTTOGRAFO COINVOLTO (i Paesi toccati dalla propagazione e le
  loro relazioni), per restare leggibili;
- uno SLIDER DEI ROUND (0 = stato iniziale) con play;
- lo SPESSORE degli archi = peso della relazione (scala log per tipo);
- gli archi CAMBIATI nel round sono evidenziati: creato / rafforzato /
  indebolito / tagliato (quest'ultimo come "fantasma" barrato);
- i nodi con un CAMBIO DI STATO nel round hanno un anello pulsante e un pop-up
  (es. "carestia.livello_ipc: fase3_crisi -> fase4_emergenza");
- pannello di LOG per il round corrente (eventi, cambi di stato, cambi di archi).

Riusa gli asset/proiezione della mappa del Blocco B.
"""

import json
from pathlib import Path

from src.graph.build_map import GRUPPI, TIPI, _carica_paesi, _centroidi, _geojson_slim

OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "processed" / "graphs" / "simulazioni"


def _coinvolti(res: dict, core: set) -> set:
    """Paesi toccati dalla simulazione: evento iniziale + target/mittenti degli
    eventi + estremi degli archi cambiati."""
    s = {res["evento_iniziale"]["paese"]}
    for snap in res["snapshots"]:
        for e in snap.get("eventi", []):
            if e.get("paese"):
                s.add(e["paese"])
            if e.get("mittente"):
                s.add(e["mittente"])
        for c in snap.get("cambi_archi", []):
            if c.get("da"):
                s.add(c["da"])
            if c.get("verso"):
                s.add(c["verso"])
    return s


def genera(res: dict, titolo: str = "Simulazione", out_path: Path = None) -> Path:
    paesi = _carica_paesi()
    core = set(paesi)
    coord, nome = _centroidi()

    coinvolti = _coinvolti(res, core)
    # includi anche i vicini diretti coinvolti negli archi mostrati
    nodi = []
    for iso3 in sorted(coinvolti):
        if iso3 not in coord:
            continue
        lat, lon = coord[iso3]
        nodi.append({"iso3": iso3, "nome": paesi[iso3]["nome"] if iso3 in paesi else nome.get(iso3, iso3),
                     "gruppo": paesi[iso3].get("gruppo") if iso3 in paesi else None,
                     "lat": lat, "lon": lon, "core": iso3 in core})
    iso_ok = {n["iso3"] for n in nodi}

    # snapshot ridotti al sottografo coinvolto
    snaps = []
    for snap in res["snapshots"]:
        rel = [r for r in snap["relazioni"] if r["da"] in iso_ok and r["a"] in iso_ok]
        snaps.append({
            "round": snap["round"],
            "relazioni": rel,
            "cambi_archi": snap.get("cambi_archi", []),
            "cambi_stato": snap.get("cambi_stato", []),
            "eventi": snap.get("eventi", []),
        })

    meta = {
        "gruppi": GRUPPI, "tipi": TIPI,
        "titolo": titolo,
        "evento": res["evento_iniziale"],
        "trimestre": res.get("trimestre_rif"),
        "n_round": len(snaps) - 1,
    }
    world = _geojson_slim(core)

    html = (_TEMPLATE
            .replace("__WORLD__", json.dumps(world, separators=(",", ":")))
            .replace("__NODI__", json.dumps(nodi, ensure_ascii=False, separators=(",", ":")))
            .replace("__SNAPS__", json.dumps(snaps, ensure_ascii=False, separators=(",", ":")))
            .replace("__META__", json.dumps(meta, ensure_ascii=False)))

    out_path = out_path or (OUT_DIR / f"{titolo}.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    kb = out_path.stat().st_size / 1024
    print(f"Mappa-simulazione scritta in {out_path} ({kb:.0f} KB) - {len(nodi)} nodi, {len(snaps)-1} round")
    return out_path


_TEMPLATE = r"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Simulazione OASIS-inspired</title>
<style>
  :root{ --bg:#f4f1ea; --ocean:#e7ecf1; --land:#d7dce3; --land-b:#fff; --ink:#20242b;
    --muted:#5d6570; --card:#fff; --line:#e2e5ea; --lbl:#1b1f26; --lbl-halo:#fff; }
  body.dark{ --bg:#0e1116; --ocean:#0d1218; --land:#212836; --land-b:#2c3442; --ink:#e9ecf1;
    --muted:#98a1ad; --card:#161b22; --line:#2a313b; --lbl:#eef1f5; --lbl-halo:#0d1218; }
  *{box-sizing:border-box} html,body{margin:0;height:100%;font-family:-apple-system,BlinkMacSystemFont,
    "Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg)}
  #app{position:fixed;inset:0;overflow:hidden}
  #map{width:100%;height:100%;background:var(--ocean);cursor:grab;display:block}
  #map.dragging{cursor:grabbing}
  .land{fill:var(--land);stroke:var(--land-b);stroke-width:.7px;vector-effect:non-scaling-stroke}
  .core{stroke-width:1px;vector-effect:non-scaling-stroke}
  .node-dot{stroke:var(--card);stroke-width:1.2px;vector-effect:non-scaling-stroke;cursor:pointer}
  .node-lbl{font-size:7px;font-weight:700;fill:var(--lbl);paint-order:stroke;stroke:var(--lbl-halo);
    stroke-width:2.4px;vector-effect:non-scaling-stroke;text-anchor:middle;pointer-events:none}
  .ring{fill:none;stroke-width:2px;vector-effect:non-scaling-stroke;opacity:0}
  .ring.on{opacity:1;animation:pulse 1.4s ease-out infinite}
  @keyframes pulse{0%{stroke-opacity:.9}100%{stroke-opacity:0}}
  .arc{fill:none;vector-effect:non-scaling-stroke;opacity:.55;cursor:pointer}
  .arc:hover,.arc.hot{opacity:1}
  .arc.creato{stroke-dasharray:5 3}
  .arc.tagliato{stroke-dasharray:2 4;opacity:.5}
  #part circle{pointer-events:none}
  #panel{position:absolute;top:16px;left:16px;width:300px;max-height:calc(100% - 32px);overflow:auto;
    background:var(--card);border:1px solid var(--line);border-radius:14px;
    box-shadow:0 8px 30px rgba(10,15,25,.16);padding:16px}
  .phead{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}
  h1{font-size:15px;margin:0 0 2px} .sub{font-size:11.5px;color:var(--muted);margin:2px 0 10px;line-height:1.45}
  #theme{flex:0 0 auto;width:30px;height:28px;border:1px solid var(--line);background:var(--card);
    color:var(--ink);border-radius:8px;cursor:pointer;font-size:13px}
  .sec{font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:.7px;color:var(--muted);margin:12px 0 7px}
  #rowr{display:flex;align-items:center;gap:9px}
  #play{width:30px;height:28px;border:1px solid var(--line);background:var(--card);color:var(--ink);
    border-radius:8px;cursor:pointer;font-size:12px;flex:0 0 auto}
  #rslider{flex:1;accent-color:var(--ink)} #rlab{font-variant-numeric:tabular-nums;font-weight:700;min-width:58px;text-align:right}
  .legend{display:flex;align-items:center;gap:8px;font-size:12px;margin:5px 0}
  .legend .sw{width:22px;height:4px;border-radius:3px} .legend .dt{width:11px;height:11px;border-radius:50%}
  .log{font-size:11.5px;line-height:1.45;color:var(--ink)}
  .log .grp{margin:7px 0 3px;font-weight:700;color:var(--muted);font-size:10.5px;text-transform:uppercase;letter-spacing:.5px}
  .log .it{margin:2px 0;padding-left:8px;border-left:2px solid var(--line)}
  .badge{display:inline-block;font-size:10px;font-weight:700;border-radius:5px;padding:1px 5px;color:#fff}
  #zoombar{position:absolute;left:50%;bottom:18px;transform:translateX(-50%);display:flex;align-items:center;
    gap:9px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:6px 11px;
    box-shadow:0 6px 20px rgba(10,15,25,.16)}
  .zb{width:26px;height:24px;border:1px solid var(--line);background:var(--card);color:var(--ink);
    border-radius:7px;cursor:pointer;font-size:15px;line-height:1;display:flex;align-items:center;justify-content:center}
  .zb:hover{border-color:#9aa3af} #zoom{width:150px;accent-color:var(--ink)}
  #tip{position:absolute;pointer-events:none;background:#20242b;color:#fff;font-size:12px;line-height:1.4;
    padding:7px 10px;border-radius:8px;box-shadow:0 6px 20px rgba(0,0,0,.3);opacity:0;max-width:260px;z-index:5}
  .hint{font-size:11px;color:var(--muted);margin-top:10px;padding-top:10px;border-top:1px solid var(--line)}
</style>
</head>
<body>
<div id="app">
  <svg id="map" preserveAspectRatio="xMidYMid meet"></svg>
  <div id="panel">
    <div class="phead"><h1>Simulazione</h1><button id="theme" title="Tema">🌙</button></div>
    <p class="sub" id="scenario"></p>
    <div class="sec">Round</div>
    <div id="rowr"><button id="play">▶</button><input id="rslider" type="range"><span id="rlab"></span></div>
    <div class="sec">Legenda archi</div>
    <div id="leg"></div>
    <div class="sec">Cosa succede in questo round</div>
    <div class="log" id="log"></div>
    <div class="hint"><b>Rotella</b>=zoom · <b>trascina</b>=sposta · spessore=peso · nodo pulsante=cambio di stato</div>
  </div>
  <div id="zoombar">
    <button class="zb" id="zout" title="Riduci">–</button>
    <input id="zoom" type="range" min="0" max="100" value="0">
    <button class="zb" id="zin" title="Ingrandisci">+</button>
  </div>
  <div id="tip"></div>
</div>
<script>
const WORLD=__WORLD__, NODI=__NODI__, SNAPS=__SNAPS__, META=__META__;
const svg=document.getElementById('map'), NS='http://www.w3.org/2000/svg';
const el=(t,a={})=>{const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);return e;};
const proj=(lon,lat)=>[(lon+180)/360*1000,(90-lat)/180*500];
const nodeByIso=Object.fromEntries(NODI.map(n=>[n.iso3,n]));
const COLT=Object.fromEntries(Object.entries(META.tipi).map(([k,v])=>[k,v.col]));
const key=(a,b,t)=>a+'|'+b+'|'+t;

/* scala spessore per tipo (log) */
const scala={};
for(const t in META.tipi){
  let lo=Infinity,hi=0;
  for(const s of SNAPS) for(const r of s.relazioni) if(r.tipo===t){lo=Math.min(lo,r.peso);hi=Math.max(hi,r.peso);}
  scala[t]=(lo===Infinity)?null:{lo:Math.log(Math.max(1,lo)),hi:Math.log(Math.max(2,hi))};
}
const spessore=(t,p)=>{const s=scala[t];if(!s||s.hi<=s.lo)return 2.4;
  return 1.2+4.6*(Math.log(Math.max(1,p))-s.lo)/(s.hi-s.lo);};

/* defs frecce per tipo */
const defs=el('defs');
for(const t in META.tipi){const m=el('marker',{id:'ar-'+t,viewBox:'0 0 10 10',refX:8,refY:5,
  markerWidth:6,markerHeight:6,orient:'auto-start-reverse',markerUnits:'userSpaceOnUse'});
  m.appendChild(el('path',{d:'M0 0 L10 5 L0 10 z',fill:COLT[t]}));defs.appendChild(m);}
svg.appendChild(defs);

/* terre + core coinvolti */
function pathD(g){const P=g.type==='Polygon'?[g.coordinates]:g.coordinates;let d='';
  for(const poly of P)for(const ring of poly){ring.forEach((pt,i)=>{const[x,y]=proj(pt[0],pt[1]);
    d+=(i?'L':'M')+x.toFixed(1)+' '+y.toFixed(1);});d+='Z';}return d;}
const gLand=el('g');for(const f of WORLD.features)gLand.appendChild(el('path',{d:pathD(f.geometry),class:'land'}));
svg.appendChild(gLand);
const grByIso=Object.fromEntries(NODI.map(n=>[n.iso3,n.gruppo]));
const gCore=el('g');
for(const f of WORLD.features){const n=nodeByIso[f.id];if(!n||!n.core)continue;const col=META.gruppi[grByIso[f.id]].col;
  gCore.appendChild(el('path',{d:pathD(f.geometry),class:'core',fill:col,'fill-opacity':.45,stroke:col}));}
svg.appendChild(gCore);

const gArcs=el('g'),gGhost=el('g'),gNodes=el('g'),gPart=el('g',{id:'part'});
svg.appendChild(gGhost);svg.appendChild(gArcs);svg.appendChild(gNodes);svg.appendChild(gPart);

/* nodi + anelli pulsanti (dimensione schermo costante via rescale) */
const rings={}, NODEELS=[];
for(const n of NODI){const[x,y]=proj(n.lon,n.lat);
  const col=n.core?META.gruppi[n.gruppo].col:'#8a94a3';
  const ring=el('circle',{cx:x,cy:y,r:6,class:'ring',stroke:col});rings[n.iso3]=ring;gNodes.appendChild(ring);
  const c=el('circle',{cx:x,cy:y,r:3.6,class:'node-dot',fill:col,'data-iso':n.iso3});
  c.addEventListener('mousemove',e=>tipNodo(e,n.iso3));c.addEventListener('mouseleave',hideTip);
  const t=el('text',{x:x,y:y-6,class:'node-lbl'});t.textContent=n.iso3;
  gNodes.appendChild(c);gNodes.appendChild(t);
  NODEELS.push({x,y,dot:c,lbl:t,ring,r0:n.core?6.5:5});}
function rescale(){const r=svg.getBoundingClientRect();if(!r.width)return;const k=vb.w/r.width;
  for(const o of NODEELS){o.dot.setAttribute('r',(o.r0*k).toFixed(2));
    o.ring.setAttribute('r',(11*k).toFixed(2));
    o.lbl.style.fontSize=(11*k).toFixed(2)+'px';o.lbl.setAttribute('y',(o.y-(o.r0+4)*k).toFixed(2));}
  for(const p of particles)p.dot.setAttribute('r',(2.2*k).toFixed(2));}

/* geometria archi */
function geo(a,b){const[x1,y1]=proj(a.lon,a.lat),[x2,y2]=proj(b.lon,b.lat);
  const mx=(x1+x2)/2,my=(y1+y2)/2,dx=x2-x1,dy=y2-y1,l=Math.hypot(dx,dy)||1,o=Math.min(70,l*.22);
  return{x1,y1,cx:mx-dy/l*o,cy:my+dx/l*o,x2,y2};}
const dstr=g=>`M${g.x1.toFixed(1)} ${g.y1.toFixed(1)} Q${g.cx.toFixed(1)} ${g.cy.toFixed(1)} ${g.x2.toFixed(1)} ${g.y2.toFixed(1)}`;
const bez=(g,t)=>{const u=1-t;return[u*u*g.x1+2*u*t*g.cx+t*t*g.x2,u*u*g.y1+2*u*t*g.cy+t*t*g.y2];};

let particles=[];
function tick(ts){for(const p of particles){p.t+=p.sp*(1/60);if(p.t>1)p.t-=1;
  const[x,y]=bez(p.g,p.t);p.dot.setAttribute('cx',x);p.dot.setAttribute('cy',y);}requestAnimationFrame(tick);}
requestAnimationFrame(tick);

/* rendering di un round */
function render(r){
  const snap=SNAPS[r];
  const opById={}; for(const c of snap.cambi_archi) opById[key(c.da,c.verso,c.tipo)]=c.op;
  const cambiati=new Set(snap.cambi_stato.map(c=>c.paese));
  gArcs.textContent='';gGhost.textContent='';gPart.textContent='';particles=[];

  for(const rel of snap.relazioni){
    const na=nodeByIso[rel.da],nb=nodeByIso[rel.a];if(!na||!nb)continue;
    const g=geo(na,nb),op=opById[key(rel.da,rel.a,rel.tipo)];
    const p=el('path',{d:dstr(g),class:'arc'+(op==='crea'?' creato':''),stroke:COLT[rel.tipo],
      'stroke-width':spessore(rel.tipo,rel.peso).toFixed(2)});
    if(op){p.classList.add('hot');}
    p.addEventListener('mousemove',e=>tipArco(e,rel,op));p.addEventListener('mouseleave',hideTip);
    gArcs.appendChild(p);
    // particella
    const dot=el('circle',{r:1.9,fill:'#fff',stroke:COLT[rel.tipo],'stroke-width':1.2});
    gPart.appendChild(dot);particles.push({dot,g,t:Math.random(),sp:.3});
  }
  // archi tagliati in questo round: fantasma barrato
  for(const c of snap.cambi_archi){if(c.op!=='taglia')continue;
    const na=nodeByIso[c.da],nb=nodeByIso[c.verso];if(!na||!nb)continue;const g=geo(na,nb);
    gGhost.appendChild(el('path',{d:dstr(g),class:'arc tagliato',stroke:COLT[c.tipo],'stroke-width':2}));
    const[mx,my]=bez(g,.5);const s=6;
    gGhost.appendChild(el('path',{d:`M${mx-s} ${my-s} L${mx+s} ${my+s} M${mx+s} ${my-s} L${mx-s} ${my+s}`,
      stroke:'#e5383b','stroke-width':2,'vector-effect':'non-scaling-stroke'}));
  }
  // anelli sui nodi con cambio di stato
  for(const iso in rings)rings[iso].classList.toggle('on',cambiati.has(iso));
  document.getElementById('rlab').textContent=r===0?'iniziale':('round '+r);
  document.getElementById('rslider').value=r;
  renderLog(snap);
  rescale();
}

/* pop-up */
const tip=document.getElementById('tip');
function statoDi(iso,snap){return snap.cambi_stato.filter(c=>c.paese===iso);}
let ROUND=0;
function tipNodo(e,iso){const n=nodeByIso[iso];const cs=statoDi(iso,SNAPS[ROUND]);
  let h=`<b>${n.nome} (${iso})</b>`;
  if(cs.length)h+='<br>'+cs.map(c=>`${c.campo}: ${c.prima} → <b>${c.dopo}</b>`).join('<br>');
  tip.innerHTML=h;showTip(e);}
function tipArco(e,rel,op){tip.innerHTML=`<b>${rel.da} → ${rel.a}</b> · ${rel.tipo}`+
  `<br>peso ${Math.round(rel.peso).toLocaleString('it-IT')}`+(op?`<br><i>${op} in questo round</i>`:'');showTip(e);}
function showTip(e){tip.style.opacity=1;const pad=14;let x=e.clientX+pad,y=e.clientY+pad;const r=tip.getBoundingClientRect();
  if(x+r.width>innerWidth)x=e.clientX-r.width-pad;if(y+r.height>innerHeight)y=e.clientY-r.height-pad;
  tip.style.left=x+'px';tip.style.top=y+'px';}
function hideTip(){tip.style.opacity=0;}

/* log del round */
function renderLog(snap){
  const L=document.getElementById('log');let h='';
  if(snap.eventi&&snap.eventi.length){h+='<div class="grp">Eventi</div>';
    for(const e of snap.eventi)h+=`<div class="it">${e.mittente?e.mittente+' → ':''}<b>${e.paese}</b> [${e.tipo}]: ${e.testo}</div>`;}
  if(snap.cambi_stato.length){h+='<div class="grp">Cambi di stato</div>';
    for(const c of snap.cambi_stato)h+=`<div class="it"><b>${c.paese}</b> ${c.campo}: ${c.prima} → <b>${c.dopo}</b></div>`;}
  if(snap.cambi_archi.length){h+='<div class="grp">Cambi di relazioni</div>';
    for(const c of snap.cambi_archi)h+=`<div class="it"><b>${c.da} → ${c.verso}</b> [${c.tipo}] `+
      `<span class="badge" style="background:${COLT[c.tipo]||'#888'}">${c.op}</span> `+
      `${c.peso_prima} → ${c.peso_dopo}${c.motivo?' · '+c.motivo:''}</div>`;}
  if(!h)h='<div class="it" style="border:none;color:var(--muted)">nessun cambiamento</div>';
  L.innerHTML=h;
}

/* pannello: scenario, legenda, slider, play, tema */
document.getElementById('scenario').innerHTML=
  `<b>${META.titolo}</b> · evento iniziale su <b>${META.evento.paese}</b> `+
  `(${META.trimestre}): ${META.evento.testo}`;
const leg=document.getElementById('leg');
for(const t in META.tipi){const d=document.createElement('div');d.className='legend';
  d.innerHTML=`<span class="sw" style="background:${META.tipi[t].col}"></span>${META.tipi[t].nome}`;leg.appendChild(d);}
const rs=document.getElementById('rslider');rs.min=0;rs.max=META.n_round;rs.step=1;rs.value=0;
rs.oninput=()=>{stopPlay();ROUND=+rs.value;render(ROUND);};
let playT=null;const play=document.getElementById('play');
function stopPlay(){if(playT){clearInterval(playT);playT=null;play.textContent='▶';}}
play.onclick=()=>{if(playT){stopPlay();return;}if(ROUND>=META.n_round)ROUND=-1;play.textContent='⏸';
  playT=setInterval(()=>{ROUND++;render(ROUND);if(ROUND>=META.n_round)stopPlay();},1500);};
const theme=document.getElementById('theme');
theme.onclick=()=>{const d=!document.body.classList.contains('dark');document.body.classList.toggle('dark',d);theme.textContent=d?'☀️':'🌙';};

/* zoom/pan + barra zoom in basso */
let vb={x:0,y:0,w:1000,h:500},HOME_W=1000;
const ZMIN=0.6,ZMAX=16,zoomInput=document.getElementById('zoom');
function setVB(){svg.setAttribute('viewBox',`${vb.x.toFixed(1)} ${vb.y.toFixed(1)} ${vb.w.toFixed(1)} ${vb.h.toFixed(1)}`);rescale();}
const curZoom=()=>HOME_W/vb.w;
function syncZoomUI(){zoomInput.value=100*Math.log(curZoom()/ZMIN)/Math.log(ZMAX/ZMIN);}
function setZoom(z,ax,ay){z=Math.max(ZMIN,Math.min(ZMAX,z));
  ax=ax==null?vb.x+vb.w/2:ax;ay=ay==null?vb.y+vb.h/2:ay;
  const nw=HOME_W/z,nh=vb.h*(nw/vb.w);
  vb.x=ax-(ax-vb.x)*(nw/vb.w);vb.y=ay-(ay-vb.y)*(nh/vb.h);vb.w=nw;vb.h=nh;setVB();syncZoomUI();}
function fit(){const P=NODI.map(n=>proj(n.lon,n.lat));if(!P.length){setVB();return;}
  let a=Math.min(...P.map(p=>p[0])),b=Math.max(...P.map(p=>p[0])),c=Math.min(...P.map(p=>p[1])),d=Math.max(...P.map(p=>p[1]));
  const px=(b-a)*.18+40,py=(d-c)*.30+40;a-=px;b+=px;c-=py;d+=py;
  let w=b-a,h=d-c;const cx=(a+b)/2,cy=(c+d)/2;const r=svg.getBoundingClientRect();
  const W=r.width||1400,H=r.height||900,PL=Math.min(360,W*.34),Wc=Math.max(1,W-PL),A=Wc/H;
  if(w/h>A)h=w/A;else w=h*A;vb={x:cx-w*(PL/Wc+.5),y:cy-h/2,w:w*(W/Wc),h};HOME_W=vb.w;setVB();syncZoomUI();}
fit();addEventListener('resize',fit);
function toSvg(cx,cy){const r=svg.getBoundingClientRect();return[vb.x+(cx-r.left)/r.width*vb.w,vb.y+(cy-r.top)/r.height*vb.h];}
svg.addEventListener('wheel',e=>{e.preventDefault();const[mx,my]=toSvg(e.clientX,e.clientY);
  setZoom(curZoom()*(e.deltaY<0?1.18:1/1.18),mx,my);},{passive:false});
zoomInput.oninput=()=>setZoom(ZMIN*Math.pow(ZMAX/ZMIN,zoomInput.value/100));
document.getElementById('zin').onclick=()=>setZoom(curZoom()*1.4);
document.getElementById('zout').onclick=()=>setZoom(curZoom()/1.4);
let pan=null;svg.addEventListener('mousedown',e=>{pan={x:e.clientX,y:e.clientY,vx:vb.x,vy:vb.y};svg.classList.add('dragging');});
addEventListener('mousemove',e=>{if(!pan)return;const r=svg.getBoundingClientRect();
  vb.x=pan.vx-(e.clientX-pan.x)/r.width*vb.w;vb.y=pan.vy-(e.clientY-pan.y)/r.height*vb.h;setVB();});
addEventListener('mouseup',()=>{svg.classList.remove('dragging');pan=null;});

render(0);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    from src.simulation.oasis_inspired import simula, responder_mock
    from src.simulation.scenari import SCENARI
    res = simula(SCENARI["siccita_darfur"], responder_mock, n_round=3, verbose=False)
    genera(res, titolo="demo_siccita_darfur")
