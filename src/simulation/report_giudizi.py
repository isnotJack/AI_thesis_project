"""
Blocco C - report grafico dei giudizi.

Legge i giudizi prodotti da judge.py per un esperimento e produce un unico HTML
autosufficiente (grafici in CSS/SVG, nessuna libreria esterna):
- CLASSIFICA dei modelli per punteggio medio del giudice (+ sotto-punteggi);
- GROUNDING OGGETTIVO: % di scelte ancorate alla KB (dai tag base_kb), per modello;
- HEATMAP punteggio per scenario × modello;
- le MOTIVAZIONI del giudice (perche' quel punteggio) con le evidenze.

Output: data/processed/giudizi/<test>/report.html

Uso: python3 -m src.simulation.report_giudizi --test test3_tag_kb
"""

import argparse
import html
import statistics as st
from pathlib import Path

from src.simulation.judge import GIUD, carica_giudizio
from src.simulation.run_simulazione import modelli_disponibili, scenari_disponibili

CAMPI = ["punteggio", "coerenza_kb", "plausibilita", "fedelta_grounding"]
ETICH = {"punteggio": "Punteggio", "coerenza_kb": "Coerenza KB",
         "plausibilita": "Plausibilità", "fedelta_grounding": "Fedeltà grounding"}


def _esc(s):
    return html.escape(str(s if s is not None else ""))


def _colore(v):
    if v is None:
        return "#c9ced6"
    h = max(0, min(120, v * 1.2))     # 0=rosso, 100=verde
    return f"hsl({h:.0f} 65% 45%)"


def _media(vals):
    vals = [v for v in vals if isinstance(v, (int, float))]
    return round(st.mean(vals), 1) if vals else None


def _raccogli(test):
    scen = scenari_disponibili(test)
    modelli = sorted({m for s in scen for m in modelli_disponibili(test, s)})
    dati = {}   # (scenario, modello) -> out
    for s in scen:
        for m in modelli_disponibili(test, s):
            g = carica_giudizio(test, s, m)
            if g:
                dati[(s, m)] = g
    return scen, modelli, dati


def _bar(label, v, maxv=100):
    w = 0 if v is None else max(2, v / maxv * 100)
    return (f'<div class="row"><div class="lab">{_esc(label)}</div>'
            f'<div class="track"><div class="fill" style="width:{w:.0f}%;background:{_colore(v)}">'
            f'{"" if v is None else f"{v:g}"}</div></div></div>')


def genera_report(test: str, out_path: Path = None) -> Path:
    scen, modelli, dati = _raccogli(test)
    giudice = next(iter(dati.values()), {}).get("giudice", "?") if dati else "?"

    # aggregati per modello
    agg = {}
    for m in modelli:
        vals = {c: _media([dati[(s, m)]["giudizio"].get(c) for s in scen if (s, m) in dati]) for c in CAMPI}
        gr = _media([dati[(s, m)]["metriche_grounding"].get("perc_grounded")
                     for s in scen if (s, m) in dati])
        vals["grounding"] = gr
        agg[m] = vals
    ordine = sorted(modelli, key=lambda m: (agg[m]["punteggio"] is not None, agg[m]["punteggio"] or 0), reverse=True)

    # 1) classifica
    classifica = ""
    for i, m in enumerate(ordine):
        medaglia = ["🥇", "🥈", "🥉"][i] if i < 3 else "&nbsp;&nbsp;"
        sub = " · ".join(f'{ETICH[c]}: <b>{agg[m][c] if agg[m][c] is not None else "n/d"}</b>' for c in CAMPI[1:])
        classifica += (f'<div class="mcard"><div class="mtop">{medaglia} <b>{_esc(m)}</b>'
                       f'<span class="big" style="color:{_colore(agg[m]["punteggio"])}">'
                       f'{agg[m]["punteggio"] if agg[m]["punteggio"] is not None else "n/d"}</span></div>'
                       f'{_bar("punteggio medio", agg[m]["punteggio"])}'
                       f'<div class="sub">{sub}</div></div>')

    # 2) grounding oggettivo
    grounding = "".join(_bar(m, agg[m]["grounding"]) for m in ordine)

    # 3) heatmap scenario x modello
    th = "".join(f"<th>{_esc(m)}</th>" for m in modelli)
    righe = ""
    for s in scen:
        celle = ""
        for m in modelli:
            g = dati.get((s, m))
            v = g["giudizio"].get("punteggio") if g else None
            celle += f'<td style="background:{_colore(v)};color:#fff">{"" if v is None else f"{v:g}"}</td>'
        righe += f"<tr><th class='rl'>{_esc(s)}</th>{celle}</tr>"

    # 4) motivazioni
    motiv = ""
    for s in scen:
        for m in modelli:
            g = dati.get((s, m))
            if not g:
                continue
            gd = g["giudizio"]
            ev = "".join(f'<li>{_esc(e.get("osservazione"))} <span class="ref">({_esc(e.get("riferimento"))})</span></li>'
                         for e in (gd.get("evidenze") or []))
            motiv += (f'<div class="mot"><div class="moth"><b>{_esc(s)}</b> · {_esc(m)} '
                      f'<span class="pt" style="background:{_colore(gd.get("punteggio"))}">{gd.get("punteggio")}</span></div>'
                      f'<div class="motb">{_esc(gd.get("motivazione"))}</div>'
                      f'{"<ul>"+ev+"</ul>" if ev else ""}</div>')

    page = (_TEMPLATE.replace("__TEST__", _esc(test)).replace("__GIUDICE__", _esc(giudice))
            .replace("__N__", str(len(dati))).replace("__CLASSIFICA__", classifica)
            .replace("__GROUNDING__", grounding).replace("__TH__", th).replace("__RIGHE__", righe)
            .replace("__MOTIV__", motiv))
    out_path = out_path or (GIUD / test / "report.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    print(f"Report scritto in {out_path}  ({len(dati)} valutazioni, {len(modelli)} modelli)")
    return out_path


_TEMPLATE = """<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Report giudizi — __TEST__</title>
<style>
  :root{--bg:#f4f1ea;--card:#fff;--ink:#20242b;--muted:#5d6570;--line:#e2e5ea}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
  .wrap{max-width:1000px;margin:0 auto;padding:22px}
  h1{font-size:19px;margin:0 0 2px} .subh{color:var(--muted);font-size:12.5px;margin-bottom:18px}
  h2{font-size:14px;margin:26px 0 10px;border-bottom:1px solid var(--line);padding-bottom:5px}
  .cards{display:flex;gap:12px;flex-wrap:wrap}
  .mcard{flex:1 1 220px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;box-shadow:0 4px 14px rgba(10,15,25,.05)}
  .mtop{display:flex;align-items:center;gap:8px;font-size:13.5px} .big{margin-left:auto;font-size:24px;font-weight:800}
  .sub{font-size:11px;color:var(--muted);margin-top:6px}
  .row{display:flex;align-items:center;gap:8px;margin:4px 0} .lab{font-size:11.5px;color:var(--muted);min-width:120px}
  .track{flex:1;background:#eef1f4;border-radius:6px;overflow:hidden;height:18px}
  .fill{height:100%;color:#fff;font-size:11px;font-weight:700;text-align:right;padding-right:6px;line-height:18px;border-radius:6px;min-width:22px}
  table{border-collapse:collapse;width:100%;font-size:12px;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
  th,td{padding:7px 9px;text-align:center} th{background:#fafafa;font-weight:700} .rl{text-align:left;background:#fafafa}
  td{font-weight:700;font-variant-numeric:tabular-nums}
  .mot{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin:8px 0}
  .moth{font-size:12.5px;margin-bottom:4px} .pt{color:#fff;border-radius:5px;padding:1px 7px;font-weight:700;margin-left:6px}
  .motb{font-size:12.5px;line-height:1.5;color:#333} .mot ul{margin:6px 0 0;padding-left:18px;font-size:11.5px;color:var(--muted)}
  .ref{color:#8b929c}
</style></head><body><div class="wrap">
<h1>Report dei giudizi — __TEST__</h1>
<div class="subh">Modello giudice: <b>__GIUDICE__</b> · __N__ valutazioni (scenario × modello). Punteggi 0–100 (verde = alto).</div>
<h2>🏆 Classifica modelli (punteggio medio del giudice)</h2>
<div class="cards">__CLASSIFICA__</div>
<h2>📌 Grounding oggettivo — % di scelte ancorate alla KB (dai tag base_kb)</h2>
__GROUNDING__
<h2>🗺️ Punteggio per scenario × modello</h2>
<table><tr><th class="rl">scenario</th>__TH__</tr>__RIGHE__</table>
<h2>💬 Motivazioni del giudice</h2>
__MOTIV__
</div></body></html>"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Report grafico dei giudizi.")
    ap.add_argument("--test", required=True)
    a = ap.parse_args()
    genera_report(a.test)
