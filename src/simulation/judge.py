"""
Blocco C - modello "as a judge".

Un modello di famiglia DIVERSA da quelli valutati (default: command-r, Cohere,
addestrato per grounding/citazioni) legge, per ogni (scenario, modello):
- la KNOWLEDGE BASE (i profili-Paese estratti, cioe' i dati su cui l'agente
  DOVEVA basarsi),
- il DIALOGO prodotto (ragionamento + reazioni + azioni con i tag `base_kb`),
e restituisce una valutazione QUANTITATIVA (0-100) di coerenza col dato,
fedelta' del grounding e plausibilita', con motivazione ed evidenze (dove ha
dedotto il giudizio).

Oltre al giudizio LLM salviamo una METRICA OGGETTIVA di grounding calcolata
direttamente dai tag `base_kb` (indipendente dal giudice): quante scelte sono
ancorate alla KB, quante dichiarano `conoscenza_generale` e quante portano un tag
IRREGOLARE (fuori dal vocabolario `TAG_KB`), che non vale come ancoraggio.

Output (cartella SEPARATA dalle simulazioni):
    data/processed/giudizi/<test>/<scenario>/<modello>/giudizio.json

Uso (su HPC, con un server Ollama attivo):
    python3 -m src.simulation.judge --test test3_tag_kb --giudice command-r --host http://127.0.0.1:11434
Prova locale (giudice finto): python3 -m src.simulation.judge --test test1_baseline --mock
"""

import argparse
import json
from pathlib import Path

from src.simulation import oasis_inspired as oi
from src.simulation.run_simulazione import (_safe, carica, modelli_disponibili,
                                            scenari_disponibili)
from src.simulation.schemi import GIUDIZIO_VUOTO, SCHEMA_GIUDIZIO, TAG_KB
from src.simulation.stato_agente import snapshot_stato

try:
    import jsonschema
except Exception:
    jsonschema = None

BASE = Path(__file__).resolve().parents[2]
GIUD = BASE / "data" / "processed" / "giudizi"
GIUDICE_DEFAULT = "command-r"
# Finestra del giudice: il suo prompt contiene KB + dialogo INTERO e sui dialoghi lunghi
# supera gli 8192 token degli agenti (test 3: fino a ~16.800 token). Ollama tronca senza
# errore tenendo la coda, quindi il giudice perderebbe la KB. Command R arriva a 128k.
NUM_CTX_GIUDICE = 32768

_NON_KB = {"conoscenza_generale", "nessuna", "none", ""}
_TAG_VALIDI = {t.strip().lower() for t in TAG_KB}       # i soli tag ammessi
_TAG_ANCORE = _TAG_VALIDI - _NON_KB                     # quelli che valgono come ancoraggio


def _pezzi_tag(raw) -> list:
    """Normalizza un tag grezzo nei suoi componenti.

    'cyber.ruolo'    -> ['cyber']        (si tiene la dimensione, non il campo)
    'evento, cyber'  -> ['evento','cyber'](il modello ne ha dichiarati piu' di uno)
    """
    out = []
    for pezzo in str(raw or "").replace(";", ",").split(","):
        base = pezzo.split(".")[0].strip().lower()
        if base:
            out.append(base)
    return out


# --------------------------------------------------------------------------- #
# Metrica OGGETTIVA di grounding (dai tag base_kb, senza LLM)
# --------------------------------------------------------------------------- #
def metriche_grounding(res: dict) -> dict:
    """Classifica ogni scelta in TRE esiti, validando il tag contro il vocabolario.

    - ancorata     : dichiara almeno un elemento VALIDO della KB;
    - non ancorata : dichiara 'conoscenza_generale' (o non dichiara nulla);
    - irregolare   : dichiara qualcosa che NON esiste nel vocabolario (es. il nome
                     di un campo dello schema) -> NON vale come ancoraggio.

    La distinzione e' necessaria: contare come ancorata una stringa qualunque
    purche' non vuota sovrastima il grounding dei modelli che compilano male il
    campo (e' l'errore della prima versione di questa metrica).
    """
    tot = ancorate = non_ancorate = irregolari = multi = 0
    dist, dist_irr = {}, {}
    for h in res["storico"]:
        scelte = list(h.get("archi", [])) + list(h.get("eventi_generati", []))
        for a in scelte:
            tot += 1
            pezzi = _pezzi_tag(a.get("base_kb"))
            if len(pezzi) > 1:
                multi += 1
            validi = [x for x in pezzi if x in _TAG_ANCORE]
            if validi:
                ancorate += 1
                for x in validi:
                    dist[x] = dist.get(x, 0) + 1
            elif not pezzi:
                non_ancorate += 1
                dist["(nessun tag)"] = dist.get("(nessun tag)", 0) + 1
            elif any(x in _NON_KB for x in pezzi):
                non_ancorate += 1
                dist["conoscenza_generale"] = dist.get("conoscenza_generale", 0) + 1
            else:
                irregolari += 1
                for x in pezzi:
                    dist_irr[x] = dist_irr.get(x, 0) + 1
    pc = lambda n: round(100 * n / tot, 1) if tot else None
    return {"scelte_taggate": tot, "grounded": ancorate,
            "non_ancorate": non_ancorate, "irregolari": irregolari,
            "multi_tag": multi,
            "perc_grounded": pc(ancorate), "perc_irregolari": pc(irregolari),
            "distribuzione": dist, "distribuzione_irregolari": dist_irr}


# --------------------------------------------------------------------------- #
# Prompt del giudice
# --------------------------------------------------------------------------- #
def _kb_paesi(res: dict) -> list:
    trim = res.get("trimestre_rif") or "2024-Q4"
    visti, out = set(), []
    for h in res["storico"]:
        if "reazione" in h and h["paese"] not in visti:
            visti.add(h["paese"])
            try:
                out.append((h["paese"], snapshot_stato(h["paese"], trim)))
            except Exception:
                pass
    return out


def _render_dialogo(res: dict) -> str:
    r = []
    for h in res["storico"]:
        if "reazione" not in h:
            r.append(f"[round {h.get('round')}] {h.get('paese')}: (non reagisce)")
            continue
        r.append(f"[round {h['round']}] {h['paese']}")
        if h.get("ragionamento"):
            r.append(f"  ragionamento: {h['ragionamento']}")
        r.append(f"  reazione: {h.get('reazione','')}")
        if h.get("aggiornamenti_stato"):
            r.append("  aggiornamenti: " + ", ".join(f"{k}={v}" for k, v in h["aggiornamenti_stato"].items()))
        for a in h.get("archi", []):
            r.append(f"  azione: {a.get('op')} {a.get('da')}->{a.get('verso')} [{a.get('tipo')}] "
                     f"base_kb={a.get('base_kb')} · {a.get('motivo','')}")
        for e in h.get("eventi_generati", []):
            r.append(f"  evento-> {e.get('paese')} [{e.get('tipo')}] base_kb={e.get('base_kb')}: {e.get('testo')}")
        if h.get("basi_kb"):
            r.append(f"  basi_kb: {', '.join(h['basi_kb'])}")
    return "\n".join(r)


def crea_prompt_giudice(res: dict) -> str:
    ev = res["evento_iniziale"]
    kb = "\n\n".join(f"### {iso} (trimestre {res.get('trimestre_rif')})\n" + oi._render_stato(st)
                     for iso, st in _kb_paesi(res)) or "(nessun profilo disponibile)"
    esempio = (
        '{\n'
        '  "punteggio": 0-100,\n'
        '  "coerenza_kb": 0-100,\n'
        '  "plausibilita": 0-100,\n'
        '  "fedelta_grounding": 0-100,\n'
        '  "motivazione": "perche\' questi punteggi (2-4 frasi)",\n'
        '  "evidenze": [{"osservazione": "...", "riferimento": "round/Paese o campo KB"}]\n'
        '}'
    )
    return f"""Sei un VALUTATORE indipendente ed esigente. Giudichi una simulazione ad agenti in cui dei Paesi (agenti LLM) reagiscono a un evento, dovendo basarsi su una knowledge base (KB) di dati estratti da fonti reali.

## SCENARIO
Evento iniziale su {ev.get('paese')} ({ev.get('data')}): "{ev.get('testo')}"

## KNOWLEDGE BASE (i dati reali su cui gli agenti DOVEVANO basarsi)
{kb}

## DIALOGO PRODOTTO DAL MODELLO SOTTO ESAME
Ogni azione/evento ha un tag `base_kb` = l'elemento della KB da cui l'agente dice di aver tratto la scelta ('conoscenza_generale' = non dalla KB).
{_render_dialogo(res)}

## IL TUO COMPITO
Valuta, con punteggi 0-100:
- coerenza_kb: reazioni, aggiornamenti di stato e azioni sono COERENTI con i dati della KB (numeri, contesto, ruolo cyber, livello di carestia, relazioni)?
- fedelta_grounding: i tag `base_kb` sono CORRETTI? La scelta deriva davvero da quell'elemento? Penalizza se usa 'conoscenza_generale' dove il dato c'era, o se cita una base che non supporta la scelta.
- plausibilita: la catena di propagazione e' geopoliticamente sensata (niente escalation assurde o incoerenti)?
- punteggio: valutazione complessiva.
Spiega in 'motivazione' il PERCHE'. In 'evidenze' cita punti precisi (round/Paese del dialogo o campo della KB) da cui hai dedotto il giudizio.

## REGOLE
- Rispondi ESCLUSIVAMENTE con un oggetto JSON valido, in italiano, niente altro.
- I punteggi sono numeri interi 0-100.

## SCHEMA ESATTO DELLA RISPOSTA
{esempio}"""


# --------------------------------------------------------------------------- #
# Parsing robusto del giudizio
# --------------------------------------------------------------------------- #
def _num(v):
    try:
        return float(str(v).strip().rstrip("%"))
    except Exception:
        return None


def parsa_giudizio(prompt: str, responder, tentativi: int = 3) -> dict:
    for _ in range(tentativi):
        try:
            testo = responder(prompt)
        except Exception:
            continue
        g = oi.estrai_json(testo)
        if isinstance(g, dict) and "punteggio" in g:
            for k in ("punteggio", "coerenza_kb", "plausibilita", "fedelta_grounding"):
                if k in g:
                    g[k] = _num(g[k])
            g.setdefault("motivazione", "")
            g.setdefault("evidenze", [])
            if jsonschema is not None:
                try:
                    jsonschema.validate(g, SCHEMA_GIUDIZIO)
                except jsonschema.ValidationError:
                    pass
            return g
    return dict(GIUDIZIO_VUOTO)


# --------------------------------------------------------------------------- #
# Valutazione
# --------------------------------------------------------------------------- #
def valuta(test: str, scenario: str, modello: str, responder, giudice: str,
           forza: bool = False):
    d = GIUD / test / scenario / _safe(modello)
    fout = d / "giudizio.json"
    if fout.exists() and not forza:
        print(f"[skip] {test} / {scenario} / {modello}")
        return
    res = carica(test, scenario, modello)
    if not res:
        return
    print(f"[judge] {test} / {scenario} / {modello} ...")
    prompt = crea_prompt_giudice(res)
    token_stimati = len(prompt) // 3        # stima prudente (~3,5-4 caratteri per token)
    if token_stimati > NUM_CTX_GIUDICE - 2048:
        print(f"[warn]  prompt del giudice di ~{token_stimati} token: rischio di troncamento "
              f"(finestra {NUM_CTX_GIUDICE})")
    giudizio = parsa_giudizio(prompt, responder)
    out = {"test": test, "scenario": scenario, "modello": modello, "giudice": giudice,
           "token_stimati": token_stimati,
           "giudizio": giudizio, "metriche_grounding": metriche_grounding(res)}
    d.mkdir(parents=True, exist_ok=True)
    fout.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    p = giudizio.get("punteggio")
    print(f"[ok]    {scenario} / {modello} -> punteggio={p}")


def valuta_tutti(test: str, responder, giudice: str, forza: bool = False):
    for s in scenari_disponibili(test):
        for m in modelli_disponibili(test, s):
            valuta(test, s, m, responder, giudice, forza=forza)


# --------------------------------------------------------------------------- #
# Helper per report / notebook
# --------------------------------------------------------------------------- #
def carica_giudizio(test: str, scenario: str, modello: str) -> dict:
    f = GIUD / test / scenario / _safe(modello) / "giudizio.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


# --------------------------------------------------------------------------- #
# Giudice finto (per validare la pipeline in locale, senza modello)
# --------------------------------------------------------------------------- #
def responder_giudice_mock(prompt: str) -> str:
    # punteggio deterministico "sensato": piu' alto se il dialogo cita spesso la KB
    n_kb = prompt.count("base_kb=") - prompt.count("base_kb=conoscenza_generale")
    base = max(35, min(92, 55 + n_kb))
    return json.dumps({
        "punteggio": base, "coerenza_kb": base, "plausibilita": max(40, base - 5),
        "fedelta_grounding": min(95, base + 3),
        "motivazione": "Giudizio simulato (mock): coerenza stimata dalla frequenza di ancoraggio alla KB.",
        "evidenze": [{"osservazione": "uso dei tag base_kb", "riferimento": "dialogo"}],
    })


def main():
    ap = argparse.ArgumentParser(description="Modello-as-a-judge per il Blocco C.")
    ap.add_argument("--test", required=True)
    ap.add_argument("--giudice", default=GIUDICE_DEFAULT, help="tag Ollama del modello giudice")
    ap.add_argument("--scenario", default=None)
    ap.add_argument("--host", default=None)
    ap.add_argument("--forza", action="store_true")
    ap.add_argument("--mock", action="store_true", help="giudice finto (nessun modello)")
    a = ap.parse_args()

    if a.mock:
        giudice, responder = "mock", responder_giudice_mock
    else:
        giudice, responder = a.giudice, oi.responder_ollama(a.giudice, host=a.host,
                                                            num_ctx=NUM_CTX_GIUDICE)

    if a.scenario:
        for m in modelli_disponibili(a.test, a.scenario):
            valuta(a.test, a.scenario, m, responder, giudice, forza=a.forza)
    else:
        valuta_tutti(a.test, responder, giudice, forza=a.forza)
    print(f"\nGiudizi in {GIUD / a.test}/")


if __name__ == "__main__":
    main()
