"""
Blocco C - test 4: giudice "con la soluzione in mano".

Nel backtest si sa che cosa e' accaduto davvero dopo l'evento iniettato. Il giudice
(stesso modello del test 3, command-r) non da' quindi un voto libero da 0 a 100, che
nel test 3 si era ridotto a tre soli valori, ma compila una LISTA DI CONTROLLO:
per ogni fatto reale (config/verita_backtest.json) dice se la simulazione lo contiene
("presente"), lo contiene in parte ("parziale") o no ("assente"), citando round e
Paese; poi elenca gli sviluppi della simulazione che non sono accaduti.

Il PUNTEGGIO non lo scrive il giudice: lo calcola il codice dalle etichette,
    punteggio_realta = 100 * (presenti + 0,5 * parziali) / fatti,
cosi' ogni punto e' riconducibile a un fatto e a un'evidenza. Il codice controlla
anche le evidenze: un'etichetta "presente" o "parziale" e' VERIFICATA solo se cita
un round in cui un Paese AUTORE di quel fatto (campo 'attori' della verita') ha
davvero agito nella simulazione. Una prova locale con un giudice piccolo aveva
segnato come presente l'attacco degli Stati Uniti in una simulazione in cui gli
Stati Uniti non compaiono mai.
    punteggio_realta_verificato = stessa formula, con le sole etichette verificate.

Dialoghi lunghi: il giudizio e' A BLOCCHI di risposte consecutive (come in judge.py),
ciascuno con l'elenco dei fatti e i criteri. Per ogni fatto si tiene l'etichetta migliore
fra i blocchi (presente > parziale > assente) e, a parte, la migliore fra quelle con
evidenza verificata nel blocco in cui compare.

Output: data/processed/giudizi/<test>/<scenario>/<modello>/giudizio_realta.json
        (giudizio_realta__<giudice>.json per un giudice diverso da command-r)

Uso (su HPC):
    python3 -m src.simulation.judge_realta --test test4_backtest_r1 --giudice command-r --host http://127.0.0.1:11434
Prova locale (giudice finto): python3 -m src.simulation.judge_realta --test mock --mock
"""

import argparse
import json
import re
from pathlib import Path

from src.simulation import oasis_inspired as oi
from src.simulation.judge import (GIUD, GIUDICE_DEFAULT, METODO, NUM_CTX_GIUDICE,
                                  _render_dialogo, blocchi_storico, gia_fatto, nome_file,
                                  nota_blocco)
from src.simulation.run_simulazione import _safe, carica, modelli_disponibili, scenari_disponibili

BASE = Path(__file__).resolve().parents[2]
VERITA = BASE / "config" / "verita_backtest.json"
ESITI = ("presente", "parziale", "assente")
RANGO = {"presente": 2, "parziale": 1, "assente": 0, None: -1}


def carica_verita(path: Path = VERITA) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))["scenari"]


def crea_prompt(res: dict, ver: dict) -> str:
    ev = res["evento_iniziale"]
    fatti = "\n".join(f"{f['id']} ({f['data']}): {f['testo']}"
                      + (f"\n   Criterio: {f['criterio']}" if f.get("criterio") else "")
                      for f in ver["fatti"])
    non_acc = "\n".join(f"- {x}" for x in ver.get("non_accaduto", [])) or "- (nessuno)"
    esempio = (
        '{\n'
        '  "fatti": [\n'
        '    {"id": "F1", "esito": "<presente | parziale | assente>", "evidenza": "<round N, ISO3: che cosa fa la simulazione; oppure nessuna>"}\n'
        '  ],\n'
        '  "sviluppi_non_accaduti": [\n'
        '    {"descrizione": "<sviluppo della simulazione che non e\' accaduto>", "riferimento": "<round e Paese>"}\n'
        '  ],\n'
        '  "motivazione": "<2-4 frasi>"\n'
        '}'
    )
    return f"""Sei un VALUTATORE indipendente ed esigente. Confronti una SIMULAZIONE, in cui degli agenti che rappresentano Paesi reagiscono a un evento, con cio' che e' DAVVERO accaduto dopo quell'evento.

## EVENTO INIZIALE (ricevuto da {ev.get('paese')}, proveniente da {ev.get('mittente') or 'nessun mittente'})
"{ev.get('testo')}"

## CIO' CHE E' ACCADUTO DAVVERO ({ver.get('periodo_reale')})
{fatti}

## SVILUPPI PLAUSIBILI CHE INVECE NON SONO ACCADUTI
{non_acc}

## LA SIMULAZIONE
{nota_blocco(res.get('blocco'))}{_nota_assenti(res.get('blocco'))}Ogni riga 'azione' modifica una relazione (cyber = attacco dall'attaccante alla vittima; militare = forze dell'interventore che operano nel teatro; migrazione = flussi di persone; cooperazione = sostegno da chi lo offre a chi lo riceve). Ogni riga 'evento->' e' un messaggio inviato a un altro Paese.
{_render_dialogo(res)}

## IL TUO COMPITO
1. Per OGNI fatto ({', '.join(f['id'] for f in ver['fatti'])}) decidi se la simulazione lo ha previsto, applicando il CRITERIO scritto sotto quel fatto:
   - "presente": la simulazione soddisfa la condizione di "Presente" del criterio;
   - "parziale": soddisfa solo la condizione di "Parziale";
   - "assente": non soddisfa nessuna delle due.
   Se un fatto non ha criterio: "presente" = stessi Paesi e stesso contenuto; "parziale" = qualcosa di simile ma con un Paese, un tipo di azione o un'intensita' diversi; "assente" = non c'e'.
   In 'evidenza' scrivi SEMPRE "round N, ISO3: ..." con il round e il codice del Paese della simulazione in cui il fatto compare (come nelle intestazioni [round N] ISO3 della simulazione), oppure "nessuna" se e' assente.
2. In 'sviluppi_non_accaduti' elenca (al massimo 8) gli sviluppi della simulazione che contraddicono cio' che e' accaduto o che compaiono fra gli sviluppi non accaduti, ciascuno con round e Paese.
3. In 'motivazione' riassumi in 2-4 frasi quanto la simulazione si avvicina alla realta'.
Giudica SOLO confrontando la simulazione con l'elenco dei fatti: non aggiungere tue conoscenze.

## REGOLE
- Rispondi ESCLUSIVAMENTE con un oggetto JSON valido, in italiano, niente altro.
- Nella lista 'fatti' deve comparire ogni fatto, una volta sola; 'esito' e' esattamente una delle parole presente, parziale, assente.

## SCHEMA DELLA RISPOSTA (i valori tra < > sono segnaposto)
{esempio}"""


def _nota_assenti(b: dict) -> str:
    if not b or b["n"] == 1:
        return ""
    return ("Se un fatto non compare in questa parte segnalalo come assente: le altre parti "
            "vengono valutate separatamente.\n")


def _esito(v) -> str:
    t = str(v or "").strip().lower()
    trovati = [e for e in ESITI if e in t]
    return trovati[0] if len(trovati) == 1 else None


_RE_FATTO = re.compile(r'"id"\s*:\s*"(F\d+)"\s*,\s*"esito"\s*:\s*"([^"]*)"'
                       r'(?:\s*,\s*"evidenza"\s*:\s*"([^"\n]*)")?')


def _recupera_dal_testo(testo: str) -> dict:
    """Se il JSON e' rotto (es. generazione degenerata a meta' risposta), recupera le
    voci {id, esito, evidenza} gia' scritte per intero prima del guasto."""
    fatti = [{"id": i, "esito": e, "evidenza": ev or ""} for i, e, ev in _RE_FATTO.findall(testo or "")]
    return {"fatti": fatti, "recuperato_dal_testo": True} if fatti else None


def parsa(prompt: str, responder, ver: dict, tentativi: int = 3) -> dict:
    """Ritorna le etichette per fatto, gli sviluppi non accaduti e la motivazione.
    Un fatto senza etichetta valida resta 'non valutato' (None). Se dopo tutti i
    tentativi il JSON resta invalido, si usano le voci intere recuperate dal testo."""
    ids = [f["id"] for f in ver["fatti"]]
    recuperato, errori = None, []
    for k in range(tentativi):
        testo = oi.chiama(responder, prompt, errori, k)
        if testo is None:
            continue
        g = oi.estrai_json(testo)
        if g is None and recuperato is None:
            recuperato = _recupera_dal_testo(testo)
        if not isinstance(g, dict) or not isinstance(g.get("fatti"), list):
            continue
        etich = {}
        for x in g["fatti"]:
            if isinstance(x, dict):
                fid = str(x.get("id", "")).strip().upper()
                if fid in ids and fid not in etich:
                    etich[fid] = {"esito": _esito(x.get("esito")), "evidenza": x.get("evidenza", "")}
        if not etich:
            continue
        sv = [x for x in (g.get("sviluppi_non_accaduti") or []) if isinstance(x, dict)]
        return {"etichette": etich, "sviluppi_non_accaduti": sv[:8],
                "motivazione": g.get("motivazione", "")}
    if len(errori) == tentativi:
        raise oi.ServerNonDisponibile(str(errori[-1])[:300])
    if recuperato:
        etich = {}
        for x in recuperato["fatti"]:
            if x["id"] in ids and x["id"] not in etich:
                etich[x["id"]] = {"esito": _esito(x["esito"]), "evidenza": x["evidenza"]}
        return {"etichette": etich, "sviluppi_non_accaduti": [], "motivazione": "",
                "errore": "JSON del giudice non valido: etichette recuperate dal testo"}
    return {"etichette": {}, "sviluppi_non_accaduti": [], "motivazione": "",
            "errore": "risposta del giudice non interpretabile"}


def evidenza_verificata(evidenza, res: dict, attori=None) -> bool:
    """True se l'evidenza cita almeno una coppia (round, Paese) in cui quel Paese ha
    davvero risposto nella simulazione e, se `attori` e' dato, e' fra gli autori del fatto."""
    t = str(evidenza or "")
    rounds = {int(x) for x in re.findall(r"round\s*(\d+)", t, flags=re.I)}
    paesi = set(re.findall(r"\b[A-Z]{3}\b", t))
    if attori:
        paesi &= set(attori)
    attivi = {(h.get("round"), h.get("paese")) for h in res["storico"] if "reazione" in h}
    return any((r, p) in attivi for r in rounds for p in paesi)


def punteggio(fatti: list) -> dict:
    """`fatti`: lista di {id, esito, esito_verificato}. Punteggi calcolati dal codice."""
    n = len(fatti)
    es = [f["esito"] for f in fatti]
    c = {e: es.count(e) for e in ESITI}
    c["non_valutati"] = sum(1 for e in es if e is None)
    c["presente_verificati"] = sum(1 for f in fatti if f.get("esito_verificato") == "presente")
    c["parziale_verificati"] = sum(1 for f in fatti if f.get("esito_verificato") == "parziale")
    ok = n and c["non_valutati"] < n
    p = round(100 * (c["presente"] + 0.5 * c["parziale"]) / n, 1) if ok else None
    pv = round(100 * (c["presente_verificati"] + 0.5 * c["parziale_verificati"]) / n, 1) if ok else None
    return {"conteggi": c, "punteggio_realta": p, "punteggio_realta_verificato": pv}


def aggrega_fatti(ver: dict, parti: list) -> list:
    """`parti`: [(blocco_res, giudizio_del_blocco)]. Per ogni fatto: l'etichetta migliore
    fra i blocchi e, a parte, la migliore con evidenza verificata NEL proprio blocco."""
    fatti = []
    for f in ver["fatti"]:
        best, best_v = None, None
        for b, g in parti:
            e = g["etichette"].get(f["id"]) or {}
            es = e.get("esito")
            ok = es in ("presente", "parziale") and evidenza_verificata(e.get("evidenza"), b,
                                                                         f.get("attori"))
            cand = {"esito": es, "evidenza": e.get("evidenza", ""), "verificata": ok,
                    "blocco": b["blocco"]["k"]}
            if best is None or RANGO[es] > RANGO[best["esito"]]:
                best = cand
            if ok and (best_v is None or RANGO[es] > RANGO[best_v["esito"]]):
                best_v = cand
        fatti.append({"id": f["id"], "testo": f["testo"], **best,
                      "esito_verificato": best_v["esito"] if best_v else None,
                      "evidenza_verificata": best_v["evidenza"] if best_v else ""})
    return fatti


def valuta(test: str, scenario: str, modello: str, responder, giudice: str, verita: dict,
           forza: bool = False):
    if scenario not in verita:
        return
    d = GIUD / test / scenario / _safe(modello)
    fout = d / nome_file("giudizio_realta", giudice)
    if gia_fatto(fout, forza):
        print(f"[skip] realta' {test} / {scenario} / {modello} ({giudice})")
        return
    res = carica(test, scenario, modello)
    if not res:
        return
    ver = verita[scenario]
    blocchi = blocchi_storico(res)
    print(f"[judge] realta' {test} / {scenario} / {modello} ({giudice}, {len(blocchi)} blocchi) ...")
    parti, info = [], []
    for b in blocchi:
        prompt = crea_prompt(b, ver)
        token_stimati = len(prompt) // 3
        if token_stimati > NUM_CTX_GIUDICE - 2048:
            print(f"[warn]  blocco di ~{token_stimati} token: rischio di troncamento")
        g = parsa(prompt, responder, ver)
        parti.append((b, g))
        info.append({**b["blocco"], "token_stimati": token_stimati,
                     **({"errore": g["errore"]} if g.get("errore") else {})})
    fatti = aggrega_fatti(ver, parti)
    multi = len(parti) > 1
    sviluppi = [{**x, "blocco": b["blocco"]["k"]} for b, g in parti
                for x in g["sviluppi_non_accaduti"]][:12]
    motiv = " ".join((f"[round {b['blocco']['round_da']}-{b['blocco']['round_a']}] " if multi else "")
                     + (g.get("motivazione") or "") for b, g in parti).strip()
    out = {"test": test, "scenario": scenario, "modello": modello, "giudice": giudice,
           "metodo": METODO, "token_stimati": max(x["token_stimati"] for x in info),
           "blocchi": info, "fatti": fatti, "sviluppi_non_accaduti": sviluppi,
           "motivazione": motiv, **punteggio(fatti)}
    errori = [x["errore"] for x in info if x.get("errore")]
    if errori:
        out["errore"] = f"{len(errori)} blocchi su {len(info)}: " + errori[0]
    d.mkdir(parents=True, exist_ok=True)
    fout.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok]    {scenario} / {modello} -> punteggio_realta={out['punteggio_realta']} "
          f"(verificato {out['punteggio_realta_verificato']}) {out['conteggi']}")


def carica_giudizio_realta(test: str, scenario: str, modello: str, giudice: str = None) -> dict:
    f = GIUD / test / scenario / _safe(modello) / nome_file("giudizio_realta", giudice)
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def giudizi_realta_disponibili(test: str, scenario: str, modello: str) -> dict:
    """{giudice: giudizio} per tutti i giudici che hanno valutato questa esecuzione con
    il metodo a blocchi (i giudizi troncati della prima versione si ignorano)."""
    out = {}
    for f in sorted((GIUD / test / scenario / _safe(modello)).glob("giudizio_realta*.json")):
        g = json.loads(f.read_text(encoding="utf-8"))
        if g.get("metodo") == METODO:
            out[g.get("giudice") or GIUDICE_DEFAULT] = g
    return out


def _mock(prompt: str) -> str:
    """Giudice finto: marca ogni fatto come 'parziale' (serve solo a provare la pipeline)."""
    import re
    fatti = re.findall(r"^(F\d+) \(", prompt, flags=re.M)
    return json.dumps({"fatti": [{"id": f, "esito": "parziale", "evidenza": "round 1, IRN: mock"}
                                 for f in fatti],
                       "sviluppi_non_accaduti": [], "motivazione": "giudizio simulato (mock)"})


def main():
    ap = argparse.ArgumentParser(description="Giudice con la verita' di riferimento (test 4).")
    ap.add_argument("--test", required=True)
    ap.add_argument("--giudice", default=GIUDICE_DEFAULT)
    ap.add_argument("--host", default=None)
    ap.add_argument("--verita", default=str(VERITA))
    ap.add_argument("--forza", action="store_true")
    ap.add_argument("--mock", action="store_true")
    a = ap.parse_args()
    verita = carica_verita(Path(a.verita))
    if a.mock:
        giudice, responder = "mock", _mock
    else:
        giudice = a.giudice
        # num_predict esplicito: la lista di controllo (un esito e un'evidenza per fatto)
        # e' lunga; un tetto basso di default la troncherebbe, rendendo il JSON invalido
        responder = oi.responder_ollama(a.giudice, host=a.host, num_ctx=NUM_CTX_GIUDICE,
                                        temperature=0.0, seed=0, num_predict=4096)
    for s in scenari_disponibili(a.test):
        for m in modelli_disponibili(a.test, s):
            try:
                valuta(a.test, s, m, responder, giudice, verita, forza=a.forza)
            except oi.ServerNonDisponibile as e:   # nulla viene salvato
                print(f"[ERRORE] giudizio di realta' {a.test} / {s} / {m}: il server non "
                      f"risponde ({e}). NON salvato.")
    print(f"\nGiudizi di realta' in {GIUD / a.test}/")


if __name__ == "__main__":
    main()
