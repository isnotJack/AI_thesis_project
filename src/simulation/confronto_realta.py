"""
Blocco C - test 4: CONFRONTO CON LA REALTA' (metriche deterministiche, senza LLM).

Per ogni esecuzione del backtest (scenario x modello x ripetizione) confronta cio'
che la simulazione ha fatto con la verita' di riferimento (config/verita_backtest.json):

- RELAZIONI: ogni operazione sugli archi diventa una chiave (da, a, tipo, segno),
  con segno '+' per rafforza/crea e '-' per indebolisci/taglia.
    richiamo   = fatti reali previsti / fatti reali;
    precisione = operazioni che corrispondono a un fatto reale / operazioni valutabili
                 (gli sviluppi 'accettabili' non contano ne' a favore ne' contro);
    richiamo esteso = come il richiamo, contando anche gli EVENTI inviati
                 (mittente -> destinatario dello stesso tipo).
- ATTORI: Paesi del campione che hanno reagito, contro quelli che hanno reagito davvero.
- PRIMO PASSO: il Paese colpito, al round 1, sceglie il canale reale (l'arco chiave)?
- ESCALATION INVENTATE: archi militari creati o rafforzati senza riscontro nella realta'.
- DE-ESCALATION: operazioni di indebolimento o taglio, e quante corrispondono a fatti reali.
- CYBER COME COOPERAZIONE: quota degli archi cyber creati/rafforzati motivati come
  cooperazione (stessa classificazione per parole chiave del test 3), per verificare
  la correzione introdotta con il tipo 'cooperazione'.
- STATO: variazioni di stato attese (es. sfollati interni in aumento).
- piu' ancoraggio (tag base_kb), punteggio del giudice con la verita' (se presente),
  risposte, round e durata.

Le stesse metriche si applicano a PREVISIONI esterne nello stesso formato:
- la BASELINE dai dati, sempre calcolata: un "analista a regole" che si limita a
  prolungare le relazioni OSTILI (cyber e militari) gia' presenti nei dati fra il Paese
  colpito e il mittente, in entrambi i versi;
- eventuali previsioni di un analista umano (--previsione file.json, vedi sotto).

Output: data/processed/backtest/confronto_realta.json e confronto_realta.html

Uso: python3 -m src.simulation.confronto_realta --prefisso test4_backtest
Formato di una previsione esterna:
    {"nome": "Analista", "scenari": {"<scenario>": {"attori": ["RUS", "ITA"],
        "archi": [{"da": "RUS", "a": "ITA", "tipo": "cyber", "segno": "+"}]}}}
"""

import argparse
import html
import json
import re
import statistics as st
from pathlib import Path

from src.simulation.ambiente import Ambiente
from src.simulation.judge import metriche_grounding
from src.simulation.judge_realta import VERITA, carica_giudizio_realta, carica_verita
from src.simulation.run_simulazione import OUT, carica, modelli_disponibili
from src.simulation.scenari import SCENARI_BACKTEST

BASE = Path(__file__).resolve().parents[2]
OUT_BT = BASE / "data" / "processed" / "backtest"
SEGNO = {"rafforza": "+", "crea": "+", "indebolisci": "-", "taglia": "-"}
_COOP = re.compile(r"cooper|collabor|allean|alleat|partner|accordo|patto|condivi", re.I)


# --------------------------------------------------------------------------- #
# Estrazione delle scelte dalla simulazione
# --------------------------------------------------------------------------- #
def archi_simulati(res: dict) -> list:
    out = []
    for h in res["storico"]:
        for a in h.get("archi", []):
            if a.get("da") and a.get("verso") and a.get("op") in SEGNO:
                out.append({"da": a["da"], "a": a["verso"], "tipo": a.get("tipo"),
                            "segno": SEGNO[a["op"]], "op": a["op"], "round": h.get("round"),
                            "motivo": a.get("motivo") or ""})
    return out


def eventi_simulati(res: dict) -> list:
    return [{"da": e.get("mittente"), "a": e.get("paese"), "tipo": e.get("tipo"),
             "round": h.get("round")}
            for h in res["storico"] for e in h.get("eventi_generati", [])]


def _k(x: dict, segno: str = None) -> tuple:
    return (x["da"], x["a"], x["tipo"], segno or x["segno"])


def indice_verita(ver: dict):
    """chiave -> id del fatto (incluse le alternative) e insieme degli accettabili."""
    vere = {}
    for a in ver["archi"]:
        vere[_k(a)] = a["id"]
        for alt in a.get("alternative", []):
            vere[_k(alt, a["segno"])] = a["id"]
    acc = {_k(a) for a in ver.get("accettabili", [])}
    return vere, acc


# --------------------------------------------------------------------------- #
# Metriche su una previsione (simulazione, baseline o analista)
# --------------------------------------------------------------------------- #
def _pr(tp, fp, fn):
    p = tp / (tp + fp) if (tp + fp) else None
    r = tp / (tp + fn) if (tp + fn) else None
    f = 2 * p * r / (p + r) if p and r else (0.0 if p is not None and r is not None else None)
    return p, r, f


def valuta_previsione(chiavi: set, attori: set, ver: dict, chiavi_eventi: set = None) -> dict:
    vere, acc = indice_verita(ver)
    ids_tutti = [a["id"] for a in ver["archi"]]
    centrati = sorted({vere[k] for k in chiavi if k in vere}, key=ids_tutti.index)
    giuste = [k for k in chiavi if k in vere]
    sbagliate = sorted(k for k in chiavi if k not in vere and k not in acc)
    precisione = len(giuste) / (len(giuste) + len(sbagliate)) if (giuste or sbagliate) else None
    richiamo = len(centrati) / len(ids_tutti) if ids_tutti else None
    f1 = (2 * precisione * richiamo / (precisione + richiamo)
          if precisione and richiamo else (0.0 if precisione is not None else None))
    out = {"richiamo_archi": richiamo, "precisione_archi": precisione, "f1_archi": f1,
           "fatti_previsti": centrati, "archi_senza_riscontro": [list(k) for k in sbagliate],
           "escalation_inventate": sum(1 for k in sbagliate if k[2] == "militare" and k[3] == "+")}
    if chiavi_eventi is not None:
        estesi = set(centrati) | {vere[k] for k in chiavi_eventi if k in vere}
        out["richiamo_esteso"] = len(estesi) / len(ids_tutti) if ids_tutti else None
        out["fatti_previsti_estesi"] = sorted(estesi, key=ids_tutti.index)
    veri = set(ver["attori"])
    pa, ra, fa = _pr(len(attori & veri), len(attori - veri), len(veri - attori))
    out.update({"precisione_attori": pa, "richiamo_attori": ra, "f1_attori": fa,
                "attori_previsti": sorted(attori), "attori_in_piu": sorted(attori - veri),
                "attori_mancanti": sorted(veri - attori)})
    return out


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def valuta_esecuzione(res: dict, ver: dict, giud_realta: dict = None) -> dict:
    archi = archi_simulati(res)
    chiavi = {_k(a) for a in archi}
    chiavi_ev = {(e["da"], e["a"], e["tipo"], "+") for e in eventi_simulati(res) if e["da"] and e["a"]}
    attori = {h["paese"] for h in res["storico"] if "reazione" in h}
    m = valuta_previsione(chiavi, attori, ver, chiavi_ev)

    ev0 = res["evento_iniziale"]
    chiave = _k(ver["arco_chiave"])
    m["primo_passo"] = any(_k(a) == chiave for a in archi
                           if a["round"] == 1 and a["da"] == ev0["paese"])
    vere, _ = indice_verita(ver)
    neg = [a for a in archi if a["segno"] == "-"]
    m["operazioni_distensive"] = len(neg)
    m["distensione_reale_prevista"] = sorted({vere[_k(a)] for a in neg if _k(a) in vere})

    cyb = [a for a in archi if a["tipo"] == "cyber" and a["segno"] == "+"]
    ncoop = sum(1 for a in cyb if _COOP.search(a["motivo"]))
    m["archi_cyber_creati_rafforzati"] = len(cyb)
    m["cyber_come_cooperazione"] = ncoop / len(cyb) if cyb else None
    m["archi_cooperazione"] = sum(1 for a in archi if a["tipo"] == "cooperazione")

    stato_ok = []
    for s in ver.get("stato", []):
        for snap in res["snapshots"]:
            for c in snap.get("cambi_stato", []):
                if c.get("paese") == s["paese"] and c.get("campo") == s["campo"]:
                    pr, do = _num(c.get("prima")) or 0.0, _num(c.get("dopo"))
                    if do is not None and ((do > pr) if s["direzione"] == "+" else (do < pr)):
                        stato_ok.append(f"{s['paese']}.{s['campo']}")
    m["stato_atteso"] = len(ver.get("stato", []))
    m["stato_previsto"] = sorted(set(stato_ok))

    g = metriche_grounding(res)
    m["ancoraggio"] = g["perc_grounded"] / 100 if g["perc_grounded"] is not None else None
    m["tag_irregolari"] = g["perc_irregolari"] / 100 if g["perc_irregolari"] is not None else None
    m["scelte_scartate"] = sum(len(h.get("scartate", [])) for h in res["storico"])
    m["risposte"] = sum(1 for h in res["storico"] if "reazione" in h)
    m["round"] = len(res["snapshots"]) - 1
    m["durata_s"] = res.get("durata_s")
    m["seed"] = res.get("seed")
    if giud_realta:
        m["punteggio_giudice_realta"] = giud_realta.get("punteggio_realta")
        m["punteggio_giudice_verificato"] = giud_realta.get("punteggio_realta_verificato")
        m["fatti_giudice"] = {f["id"]: f["esito"] for f in giud_realta.get("fatti", [])}
        m["fatti_giudice_verificati"] = {f["id"]: f["esito"] for f in giud_realta.get("fatti", [])
                                         if f.get("verificata")}
    return m


OSTILI = ("cyber", "militare")


def baseline_dati(scenario: str, ver: dict) -> dict:
    """'Analista a regole': il Paese colpito e il mittente proseguono, con segno '+',
    le relazioni ostili (cyber, militari) che i dati gia' mostrano fra loro nel
    trimestre di riferimento. Non usa alcun modello: misura quanto della realta' si
    poteva prevedere solo prolungando i dati, cioe' il valore aggiunto della simulazione."""
    ev = SCENARI_BACKTEST[scenario]
    amb = Ambiente(trimestre_rif=ev.data)
    T, S = ev.paese, ev.mittente
    chiavi = set()
    for a, b in ((T, S), (S, T)):
        if a in amb.R and b in amb.R:
            for tipo in amb.R[a].get(b, {}):
                if tipo in OSTILI:
                    chiavi.add((a, b, tipo, "+"))
    m = valuta_previsione(chiavi, {T, S}, ver)
    m["archi_previsti"] = [list(k) for k in sorted(chiavi)]
    return m


def valuta_file_previsione(path: Path, verita: dict) -> dict:
    p = json.loads(Path(path).read_text(encoding="utf-8"))
    out = {"nome": p.get("nome", Path(path).stem), "scenari": {}}
    for scen, x in p.get("scenari", {}).items():
        if scen in verita:
            chiavi = {_k(a) for a in x.get("archi", [])}
            out["scenari"][scen] = valuta_previsione(chiavi, set(x.get("attori", [])), verita[scen])
    return out


# --------------------------------------------------------------------------- #
# Aggregazione sulle ripetizioni
# --------------------------------------------------------------------------- #
NUMERICHE = ["richiamo_archi", "precisione_archi", "f1_archi", "richiamo_esteso",
             "precisione_attori", "richiamo_attori", "escalation_inventate",
             "operazioni_distensive", "cyber_come_cooperazione", "archi_cooperazione",
             "punteggio_giudice_realta", "punteggio_giudice_verificato", "ancoraggio", "tag_irregolari", "scelte_scartate",
             "risposte", "round", "durata_s"]


def aggrega(esecuzioni: list, ver: dict) -> dict:
    agg = {"n": len(esecuzioni)}
    for k in NUMERICHE:
        vals = [e[k] for e in esecuzioni if isinstance(e.get(k), (int, float))]
        agg[k] = ({"media": round(st.mean(vals), 3), "min": round(min(vals), 3),
                   "max": round(max(vals), 3)} if vals else None)
    agg["primo_passo"] = sum(1 for e in esecuzioni if e.get("primo_passo"))
    agg["copertura_fatti"] = {a["id"]: sum(1 for e in esecuzioni if a["id"] in e["fatti_previsti"])
                              for a in ver["archi"]}
    agg["copertura_fatti_estesa"] = {a["id"]: sum(1 for e in esecuzioni
                                                  if a["id"] in e.get("fatti_previsti_estesi", []))
                                     for a in ver["archi"]}
    agg["copertura_giudice"] = {}
    for f in ver["fatti"]:
        es = [(e.get("fatti_giudice") or {}).get(f["id"]) for e in esecuzioni]
        agg["copertura_giudice"][f["id"]] = {"presente": es.count("presente"),
                                             "parziale": es.count("parziale")}
    return agg


def confronta(prefisso: str, verita: dict, previsioni: list = ()) -> dict:
    tests = sorted(p.name for p in OUT.iterdir()
                   if p.is_dir() and p.name.startswith(prefisso + "_r")) if OUT.exists() else []
    out = {"prefisso": prefisso, "ripetizioni": tests, "scenari": {}}
    for scen, ver in verita.items():
        per_modello = {}
        for t in tests:
            for m in modelli_disponibili(t, scen):
                res = carica(t, scen, m)
                if not res:
                    continue
                e = valuta_esecuzione(res, ver, carica_giudizio_realta(t, scen, m))
                e["test"] = t
                per_modello.setdefault(m, []).append(e)
        out["scenari"][scen] = {
            "titolo": ver["titolo"], "periodo_reale": ver["periodo_reale"],
            "modelli": {m: {"aggregato": aggrega(es, ver), "esecuzioni": es}
                        for m, es in sorted(per_modello.items())},
            "baseline_dati": baseline_dati(scen, ver),
            "previsioni": {p["nome"]: p["scenari"][scen] for p in previsioni if scen in p["scenari"]},
        }
    return out


# --------------------------------------------------------------------------- #
# Report HTML
# --------------------------------------------------------------------------- #
def _e(s):
    return html.escape(str(s if s is not None else ""))


def _pc(x):
    return "–" if x is None else f"{100 * x:.0f}%"


def _fmt(v, dec=1) -> str:
    t = f"{v:.{dec}f}"
    return t.rstrip("0").rstrip(".") if "." in t else t      # 2.50 -> 2.5, 50 -> 50


def _rng(a, perc=True, dec=1):
    if not a:
        return "–"
    f = (lambda v: f"{100 * v:.0f}%") if perc else (lambda v: _fmt(v, dec))
    return f"{f(a['media'])}" + ("" if a["min"] == a["max"] else
                                 f" <span class='r'>({f(a['min'])}–{f(a['max'])})</span>")


def report_html(conf: dict, verita: dict) -> str:
    blocchi = []
    for scen, d in conf["scenari"].items():
        ver = verita[scen]
        ev = SCENARI_BACKTEST[scen]
        righe = ""
        for m, x in d["modelli"].items():
            a = x["aggregato"]
            minuti = "–" if not a["durata_s"] else f"{a['durata_s']['media'] / 60:.1f}"
            giud = (_rng(a["punteggio_giudice_realta"], perc=False, dec=0)
                    if a["punteggio_giudice_realta"] else "–")
            if a.get("punteggio_giudice_verificato"):
                giud += " / " + _rng(a["punteggio_giudice_verificato"], perc=False, dec=0)
            righe += (f"<tr><th>{_e(m)}</th><td>{a['n']}</td><td>{_rng(a['richiamo_archi'])}</td>"
                      f"<td>{_rng(a['precisione_archi'])}</td><td>{_rng(a['richiamo_esteso'])}</td>"
                      f"<td>{_rng(a['richiamo_attori'])} / {_rng(a['precisione_attori'])}</td>"
                      f"<td>{a['primo_passo']}/{a['n']}</td>"
                      f"<td>{_rng(a['escalation_inventate'], perc=False)}</td>"
                      f"<td>{_rng(a['operazioni_distensive'], perc=False)}</td>"
                      f"<td>{giud}</td>"
                      f"<td>{_rng(a['ancoraggio'])}</td><td>{_rng(a['cyber_come_cooperazione'])}</td>"
                      f"<td>{_rng(a['risposte'], perc=False)}</td>"
                      f"<td>{minuti}</td></tr>")
        b = d["baseline_dati"]
        righe += (f"<tr class='bl'><th>baseline dai dati</th><td>–</td><td>{_pc(b['richiamo_archi'])}</td>"
                  f"<td>{_pc(b['precisione_archi'])}</td><td>–</td>"
                  f"<td>{_pc(b['richiamo_attori'])} / {_pc(b['precisione_attori'])}</td>"
                  f"<td colspan='8'>prolunga le relazioni ostili già nei dati: "
                  f"{_e(', '.join('→'.join(k[:2]) + ' ' + k[2] for k in b['archi_previsti'])) or 'nessuna'}</td></tr>")
        for nome, p in d["previsioni"].items():
            righe += (f"<tr class='bl'><th>{_e(nome)}</th><td>–</td><td>{_pc(p['richiamo_archi'])}</td>"
                      f"<td>{_pc(p['precisione_archi'])}</td><td>–</td>"
                      f"<td>{_pc(p['richiamo_attori'])} / {_pc(p['precisione_attori'])}</td><td colspan='8'></td></tr>")
        mods = list(d["modelli"])
        cop = ""
        for a in ver["archi"]:
            celle = "".join(
                f"<td class='c' style='--v:{d['modelli'][m]['aggregato']['copertura_fatti'][a['id']] / max(1, d['modelli'][m]['aggregato']['n'])}'>"
                f"{d['modelli'][m]['aggregato']['copertura_fatti'][a['id']]}/{d['modelli'][m]['aggregato']['n']}</td>"
                for m in mods)
            bl = "sì" if a["id"] in d["baseline_dati"]["fatti_previsti"] else "–"
            cop += (f"<tr><th class='f'><b>{_e(a['id'])}</b> {_e(a['da'])}→{_e(a['a'])} {_e(a['tipo'])} "
                    f"{_e(a['segno'])}<div class='n'>{_e(a['fatto'])} ({_e(a['data'])})</div></th>"
                    f"{celle}<td class='c'>{bl}</td></tr>")
        giu = ""
        if any(d["modelli"][m]["aggregato"]["punteggio_giudice_realta"] for m in mods):
            for f in ver["fatti"]:
                celle = "".join(
                    f"<td class='c'>{d['modelli'][m]['aggregato']['copertura_giudice'][f['id']]['presente']}"
                    f" · {d['modelli'][m]['aggregato']['copertura_giudice'][f['id']]['parziale']}</td>"
                    for m in mods)
                giu += f"<tr><th class='f'><b>{_e(f['id'])}</b> <div class='n'>{_e(f['testo'])}</div></th>{celle}</tr>"
            giu = (f"<h3>Fatti secondo il giudice: esecuzioni in cui il fatto è presente · parziale</h3>"
                   f"<table><tr><th>fatto</th>{''.join(f'<th>{_e(m)}</th>' for m in mods)}</tr>{giu}</table>")
        blocchi.append(
            f"<section><h2>{_e(d['titolo'])}</h2>"
            f"<p class='ev'>Evento iniettato su <b>{_e(ev.paese)}</b> da <b>{_e(ev.mittente)}</b> "
            f"(stato di partenza {_e(ev.data)}): {_e(ev.testo)}<br>Periodo reale: {_e(d['periodo_reale'])}.</p>"
            f"<table><tr><th>modello</th><th>esec.</th><th>richiamo archi</th><th>precisione archi</th>"
            f"<th>richiamo con eventi</th><th>attori R / P</th><th>primo passo</th><th>escalation inventate</th>"
            f"<th>operazioni distensive</th><th>giudice: tutte / verificate</th><th>ancoraggio</th>"
            f"<th>cyber come cooperazione</th><th>risposte</th><th>minuti</th></tr>{righe}</table>"
            f"<h3>Quali fatti reali sono stati previsti (archi, esecuzioni su ripetizioni)</h3>"
            f"<table><tr><th>fatto reale</th>{''.join(f'<th>{_e(m)}</th>' for m in mods)}"
            f"<th>baseline</th></tr>{cop}</table>{giu}</section>")
    return _TEMPLATE.replace("__PREF__", _e(conf["prefisso"])) \
        .replace("__RIP__", _e(", ".join(conf["ripetizioni"]) or "nessuna")) \
        .replace("__BLOCCHI__", "".join(blocchi))


_TEMPLATE = """<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Confronto con la realtà</title>
<style>
 :root{--bg:#f4f1ea;--card:#fff;--ink:#20242b;--muted:#5d6570;--line:#e2e5ea}
 body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
 header{padding:16px 20px;background:var(--card);border-bottom:1px solid var(--line)}
 h1{font-size:18px;margin:0 0 4px} h2{font-size:16px;margin:0 0 6px} h3{font-size:13px;margin:16px 0 6px;color:var(--muted)}
 section{background:var(--card);border:1px solid var(--line);border-radius:12px;margin:16px;padding:14px 16px;overflow-x:auto}
 .ev{font-size:12.5px;color:var(--muted)} table{border-collapse:collapse;font-size:12px;width:100%}
 th,td{border-bottom:1px solid var(--line);padding:5px 7px;text-align:left;vertical-align:top}
 td{white-space:nowrap} .r{color:var(--muted);font-size:11px} tr.bl th,tr.bl td{background:#f7f8fa;color:#333}
 th.f{font-weight:400;max-width:520px} .n{color:var(--muted);font-size:11px}
 td.c{text-align:center;background:color-mix(in srgb,#2a9d8f calc(var(--v,0)*55%),transparent)}
 .sub{font-size:12px;color:var(--muted)}
</style></head><body>
<header><h1>Test 4 — confronto della simulazione con ciò che è accaduto</h1>
<div class="sub">Esperimento __PREF__ · ripetizioni: __RIP__. Valori: media sulle ripetizioni (min–max).
Richiamo = fatti reali previsti / fatti reali; precisione = operazioni con riscontro / operazioni valutabili.</div></header>
__BLOCCHI__
</body></html>"""


def main():
    ap = argparse.ArgumentParser(description="Confronto deterministico fra simulazione e realta' (test 4).")
    ap.add_argument("--prefisso", default="test4_backtest")
    ap.add_argument("--verita", default=str(VERITA))
    ap.add_argument("--previsione", action="append", default=[],
                    help="file JSON di una previsione esterna (ripetibile)")
    a = ap.parse_args()
    verita = carica_verita(Path(a.verita))
    previsioni = [valuta_file_previsione(Path(p), verita) for p in a.previsione]
    conf = confronta(a.prefisso, verita, previsioni)
    OUT_BT.mkdir(parents=True, exist_ok=True)
    (OUT_BT / "confronto_realta.json").write_text(json.dumps(conf, ensure_ascii=False, indent=2),
                                                  encoding="utf-8")
    (OUT_BT / "confronto_realta.html").write_text(report_html(conf, verita), encoding="utf-8")
    for scen, d in conf["scenari"].items():
        print(f"== {scen}")
        for m, x in d["modelli"].items():
            ag = x["aggregato"]
            print(f"   {m:16s} n={ag['n']} richiamo={ag['richiamo_archi']} precisione={ag['precisione_archi']} "
                  f"primo_passo={ag['primo_passo']}/{ag['n']}")
        b = d["baseline_dati"]
        print(f"   baseline dati    richiamo={b['richiamo_archi']} precisione={b['precisione_archi']} "
              f"archi={b['archi_previsti']}")
    print(f"\nScritto {OUT_BT / 'confronto_realta.json'} e .html")


if __name__ == "__main__":
    main()
