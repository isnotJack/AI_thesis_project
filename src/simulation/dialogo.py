"""
Blocco C - vista "dialogo" affiancata tra modelli.

Per uno scenario, genera un HTML con una COLONNA per modello, uno accanto
all'altro: per ogni round si vede l'agente che reagisce, il suo RAGIONAMENTO
(come e' arrivato alla decisione), la reazione, i cambi di stato, le azioni
sugli archi (con il motivo) e gli eventi generati. Serve a confrontare COME
i diversi modelli arrivano alle loro scelte sullo stesso scenario.

Output: data/processed/simulazioni/<test>/<scenario>/dialogo.html

Uso:
    python3 -m src.simulation.dialogo --test test2_stessa_fascia_round10
    python3 -m src.simulation.dialogo --test test1_baseline --scenario ransomware_usa
"""

import argparse
import html
from pathlib import Path

from src.simulation.run_simulazione import (OUT, carica, modelli_disponibili,
                                            scenari_disponibili)

# colori intestazione colonna (ciclici)
_COLORI = ["#1f6feb", "#c1121f", "#2a9d8f", "#e07a1e", "#6a4c93", "#0a7d6b"]
_OPCOL = {"crea": "#2a9d8f", "rafforza": "#1f6feb", "indebolisci": "#e07a1e", "taglia": "#c1121f"}


def _esc(s):
    return html.escape(str(s if s is not None else ""))


def _card(h: dict) -> str:
    if "reazione" not in h:                      # nodo non-core: inerte
        return (f'<div class="card inert"><span class="round">round {h.get("round")}</span> '
                f'<b>{_esc(h.get("paese"))}</b> — {_esc(h.get("nota","non reagisce"))}</div>')
    parti = [f'<div class="hd"><span class="round">round {h["round"]}</span> <b>{_esc(h["paese"])}</b></div>']
    if h.get("ragionamento"):
        parti.append(f'<div class="rag">💭 {_esc(h["ragionamento"])}</div>')
    if h.get("reazione"):
        parti.append(f'<div class="rz">{_esc(h["reazione"])}</div>')
    for k, v in (h.get("aggiornamenti_stato") or {}).items():
        parti.append(f'<div class="st">stato · {_esc(k)} = <b>{_esc(v)}</b></div>')
    for a in h.get("archi", []):
        col = _OPCOL.get(a.get("op"), "#888")
        tag = f' <span class="tag">{_esc(a.get("base_kb"))}</span>' if a.get("base_kb") else ""
        parti.append(f'<div class="arc" style="border-color:{col}">'
                     f'<span class="op" style="background:{col}">{_esc(a.get("op"))}</span> '
                     f'{_esc(a.get("da"))} → {_esc(a.get("verso"))} [{_esc(a.get("tipo"))}] '
                     f'{_esc(a.get("peso_prima"))}→{_esc(a.get("peso_dopo"))}'
                     f'{" · "+_esc(a.get("motivo")) if a.get("motivo") else ""}{tag}</div>')
    for e in h.get("eventi_generati", []):
        tag = f' <span class="tag">{_esc(e.get("base_kb"))}</span>' if e.get("base_kb") else ""
        parti.append(f'<div class="ev">→ evento a <b>{_esc(e.get("paese"))}</b> '
                     f'[{_esc(e.get("tipo"))}]: {_esc(e.get("testo"))}{tag}</div>')
    if h.get("basi_kb"):
        chips = " ".join(f'<span class="chip">{_esc(t)}</span>' for t in h["basi_kb"])
        parti.append(f'<div class="basi">basi KB: {chips}</div>')
    return '<div class="card">' + "".join(parti) + "</div>"


def _colonna(modello: str, res: dict, colore: str) -> str:
    corpo = "".join(_card(h) for h in res["storico"]) or '<div class="card inert">nessuna reazione</div>'
    return (f'<div class="col"><div class="colh" style="background:{colore}">{_esc(modello)}</div>'
            f'<div class="colb">{corpo}</div></div>')


def genera_dialogo(test: str, scenario: str, out_path: Path = None) -> Path:
    mods = modelli_disponibili(test, scenario)
    if not mods:
        return None
    ev = carica(test, scenario, mods[0])["evento_iniziale"]
    colonne = "".join(_colonna(m, carica(test, scenario, m), _COLORI[i % len(_COLORI)])
                      for i, m in enumerate(mods))
    htmlpage = _TEMPLATE.replace("__TITOLO__", _esc(f"{scenario}  ·  {test}")) \
        .replace("__EVENTO__", f"<b>{_esc(ev['paese'])}</b> — {_esc(ev['testo'])}") \
        .replace("__COLONNE__", colonne)
    out_path = out_path or (OUT / test / scenario / "dialogo.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(htmlpage, encoding="utf-8")
    return out_path


def genera_tutti(test: str) -> int:
    n = 0
    for s in scenari_disponibili(test):
        if genera_dialogo(test, s):
            n += 1
    return n


_TEMPLATE = """<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Dialogo — __TITOLO__</title>
<style>
  :root{--bg:#f4f1ea;--card:#fff;--ink:#20242b;--muted:#5d6570;--line:#e2e5ea}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
  .top{padding:14px 18px;border-bottom:1px solid var(--line);background:var(--card);position:sticky;top:0;z-index:2}
  .top h1{font-size:15px;margin:0 0 3px} .top .ev{font-size:12.5px;color:var(--muted)}
  .cols{display:flex;gap:14px;padding:16px;overflow-x:auto;align-items:flex-start}
  .col{flex:1 0 340px;max-width:460px;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;box-shadow:0 4px 16px rgba(10,15,25,.06)}
  .colh{color:#fff;font-weight:700;font-size:13px;padding:9px 12px;position:sticky;top:0}
  .colb{max-height:76vh;overflow-y:auto;padding:10px 11px}
  .card{border:1px solid var(--line);border-left:3px solid #cfd4dc;border-radius:9px;padding:9px 10px;margin-bottom:9px;font-size:12.5px;line-height:1.45}
  .card.inert{color:var(--muted);border-left-color:#e2e5ea;background:#fafafa;font-size:11.5px}
  .hd{margin-bottom:4px} .round{font-size:10.5px;font-weight:700;color:#fff;background:#20242b;border-radius:5px;padding:1px 6px}
  .rag{background:#eef2ff;border-radius:7px;padding:6px 8px;margin:5px 0;font-style:italic;color:#33406b}
  .rz{margin:4px 0}
  .st{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11px;color:#444;background:#f4f6f8;border-radius:5px;padding:2px 6px;margin:3px 0;display:inline-block}
  .arc{border-left:3px solid #888;padding:3px 8px;margin:4px 0;background:#fbfbfc;border-radius:5px}
  .arc .op{color:#fff;font-size:10px;font-weight:700;border-radius:4px;padding:1px 5px;margin-right:4px}
  .ev{color:#5d6570;margin:4px 0 2px;padding-left:6px;border-left:2px solid var(--line)}
  .tag{font-size:9.5px;font-weight:700;color:#33406b;background:#e7ecff;border-radius:4px;padding:1px 5px}
  .basi{margin-top:6px;font-size:10.5px;color:var(--muted)}
  .chip{display:inline-block;font-size:9.5px;background:#eef2f6;border:1px solid var(--line);border-radius:4px;padding:1px 5px;margin:1px}
</style></head><body>
<div class="top"><h1>Dialogo tra modelli — __TITOLO__</h1><div class="ev">Evento iniziale: __EVENTO__</div></div>
<div class="cols">__COLONNE__</div>
</body></html>"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Genera la vista 'dialogo' affiancata tra modelli.")
    ap.add_argument("--test", required=True)
    ap.add_argument("--scenario", default=None, help="uno scenario; se assente, tutti")
    a = ap.parse_args()
    if a.scenario:
        p = genera_dialogo(a.test, a.scenario)
        print("scritto:", p)
    else:
        n = genera_tutti(a.test)
        print(f"dialoghi generati: {n} (in {OUT / a.test}/<scenario>/dialogo.html)")
