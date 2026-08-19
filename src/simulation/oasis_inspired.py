"""
Blocco C - Simulazione "OASIS-inspired" (motore).

Architettura a 3 componenti (i 5 di OASIS ridotti, vedi documento sez. 4.4):
  1. AMBIENTE   -> src/simulation/ambiente.py (il grafo, come stato condiviso)
  2. AGENTE     -> qui: prompt preciso -> LLM -> JSON validato (schemi.py)
  3. CICLO      -> qui: `simula()`, round discreti e sincroni

Idea: iniettiamo un evento su un Paese; l'agente ragiona sul PROPRIO stato/storia
e decide reazione + aggiornamenti di stato + modifiche agli archi + nuovi eventi
verso i vicini; si propaga per N round. Output = storico + snapshot del grafo per
round (per la visualizzazione e il confronto tra modelli). Si lavora su una COPIA
del grafo: i dati reali non si toccano.

L'LLM e' iniettabile (`responder`) cosi' il ciclo e' testabile in locale con un
mock, e in produzione gira su Ollama (HPC) con modelli diversi da confrontare.
"""

import json
import re

from src.simulation import schemi
from src.simulation.ambiente import Ambiente
from src.simulation.schemi import AZIONE_VUOTA, SCHEMA_AZIONE, Evento
from src.simulation.stato_agente import (costruisci_scheda, snapshot_stato,
                                         traiettoria, trimestre_riferimento)

try:
    import jsonschema
except Exception:  # validazione difensiva anche senza la libreria
    jsonschema = None


# --------------------------------------------------------------------------- #
# 2. AGENTE — prompt
# --------------------------------------------------------------------------- #
def _tronca(s, n):
    s = "" if s is None else str(s)
    return s if len(s) <= n else s[:n].rstrip() + "…"


def _render_stato(stato: dict) -> str:
    d = stato
    conf = d.get("conflitto") or {}
    car = d.get("carestia") or {}
    mig = d.get("migrazione") or {}
    eco = d.get("economia") or {}
    cy = d.get("cyber") or {}
    righe = [
        f"- contesto_generale: {_tronca(d.get('contesto_generale'), 700)}",
        f"- conflitto: n_eventi_violenti={conf.get('n_eventi_violenti')}, "
        f"n_vittime={conf.get('n_vittime')}. {_tronca(conf.get('descrizione'), 200)}",
        f"- carestia: livello_ipc={car.get('livello_ipc')}. {_tronca(car.get('descrizione'), 200)}",
        f"- migrazione: rifugiati={mig.get('rifugiati')}, richiedenti_asilo={mig.get('richiedenti_asilo')}, "
        f"sfollati_interni={mig.get('sfollati_interni')}. {_tronca(mig.get('descrizione'), 150)}",
        f"- economia: tasso_poverta_pct={eco.get('tasso_poverta_pct')}. {_tronca(eco.get('sintesi'), 150)}",
        f"- cyber: ruolo={cy.get('ruolo')}, n_incidenti_datati={cy.get('n_incidenti_datati')}, "
        f"gruppi={_tronca(', '.join(cy.get('gruppi_minaccia_associati') or []), 150)}",
    ]
    return "\n".join(righe)


def _render_traiettoria(tr: dict) -> str:
    if not tr:
        return "(nessun dato numerico storico)"
    return "\n".join(
        f"- {k}: {v['trend']} (ultimo={v['ultimo']}, min={v['min']}, max={v['max']})"
        for k, v in tr.items())


def _render_relazioni(rel: dict) -> str:
    def fmt(items, campo):
        if not items:
            return "  (nessuna)"
        return "\n".join(f"  - {r['tipo']}: {campo} {r.get('verso') or r.get('da')} (peso {r['peso']})"
                         for r in items[:12])
    return f"uscenti (tu -> altri):\n{fmt(rel['uscenti'], 'verso')}\n" \
           f"entranti (altri -> tu):\n{fmt(rel['entranti'], 'da')}"


def crea_prompt(scheda: dict, evento, relazione_mittente=None) -> str:
    ev = evento.as_dict() if isinstance(evento, Evento) else evento
    defs_dim = "\n".join(f"- {k}: {v}" for k, v in schemi.DIMENSIONI.items())
    defs_arco = "\n".join(f"- {t}: verso = {schemi.VERSI_ARCO[t]}; il peso indica l'intensita'."
                          for t in schemi.TIPI_ARCO)
    defs_op = "\n".join(f"- {o}: {schemi.SIGNIFICATO_OP[o]}" for o in schemi.OPERAZIONI_ARCO)

    if ev.get("mittente") and relazione_mittente:
        prov = (f"proviene da {ev['mittente']}, con cui hai una relazione "
                f"'{relazione_mittente['tipo']}' (peso {relazione_mittente['peso']}, "
                f"{relazione_mittente['verso']})")
    elif ev.get("mittente"):
        prov = f"proviene da {ev['mittente']}"
    else:
        prov = "iniettato dallo scenario (nessun mittente)"

    schema_esempio = (
        '{\n'
        '  "reazione_breve": "max 2-3 frasi su come reagisce il Paese",\n'
        '  "aggiornamenti_stato": {"carestia.livello_ipc": "fase4_emergenza", "migrazione.rifugiati": 120000},\n'
        '  "azioni_su_archi": [\n'
        '    {"op": "rafforza", "verso": "EGY", "tipo": "migrazione", "peso_delta": 50000, "motivo": "..."}\n'
        '  ],\n'
        '  "genera_eventi": [\n'
        '    {"verso": "EGY", "tipo": "migrazione", "testo": "aumento dei flussi verso il confine"}\n'
        '  ]\n'
        '}'
    )

    return f"""Sei l'agente che rappresenta il Paese {scheda['paese']} ({scheda['iso3']}).
Partecipi a una simulazione a round: un evento si propaga lungo una rete di relazioni tra Paesi. Ricevi un evento e decidi, in modo coerente con il TUO stato e la TUA storia, se e come reagire.

### DEFINIZIONI — LE DIMENSIONI DEL TUO STATO
{defs_dim}

### DEFINIZIONI — LE RELAZIONI (ARCHI, sempre DIRETTI)
{defs_arco}

### DEFINIZIONI — LE AZIONI CHE PUOI FARE SUGLI ARCHI
{defs_op}
Puoi anche creare una relazione verso un Paese non ancora presente sulla mappa (usa il suo codice ISO3).

### IL TUO STATO ATTUALE (trimestre di riferimento)
{_render_stato(scheda['stato'])}

### LA TUA TRAIETTORIA RECENTE (solo numeri, fino al trimestre di riferimento)
{_render_traiettoria(scheda['traiettoria'])}

### LE TUE RELAZIONI ATTUALI
{_render_relazioni(scheda['relazioni'])}

### EVENTO RICEVUTO
tipo: {ev.get('tipo')}
testo: "{ev.get('testo')}"
provenienza: {prov}

### IL TUO COMPITO
Valuta se e come l'evento influenza la tua situazione. Aggiorna SOLO i campi che cambiano davvero. Modifica gli archi solo se l'evento lo giustifica. Genera nuovi eventi solo verso Paesi con cui hai (o crei) una relazione, scegliendo tu i destinatari. Se l'evento non ti riguarda, rispondi con reazione neutra e liste vuote.

### REGOLE (rispettale tutte)
- Rispondi ESCLUSIVAMENTE con un oggetto JSON valido: nessun testo fuori dal JSON, niente markdown, niente commenti.
- Scrivi in italiano.
- Non inventare numeri o fatti non plausibili: resta coerente con lo stato e la storia mostrati sopra.
- I Paesi si indicano con il codice ISO3 (3 lettere maiuscole).
- In 'aggiornamenti_stato' le chiavi sono 'dimensione.campo' (es. "carestia.livello_ipc").
- In 'azioni_su_archi' 'op' ∈ {list(schemi.OPERAZIONI_ARCO)}, 'tipo' ∈ {list(schemi.TIPI_ARCO)}.

### SCHEMA ESATTO DELLA RISPOSTA
{schema_esempio}"""


# --------------------------------------------------------------------------- #
# 2b. AGENTE — parsing robusto della risposta
# --------------------------------------------------------------------------- #
def estrai_json(testo: str):
    """Estrae il primo oggetto JSON dalla risposta (tollerante a code-fence e
    testo attorno). Ritorna dict valido o None."""
    if not testo:
        return None
    t = re.sub(r"```(?:json)?", "", testo).strip()
    i = t.find("{")
    if i == -1:
        return None
    prof = 0
    for j in range(i, len(t)):
        if t[j] == "{":
            prof += 1
        elif t[j] == "}":
            prof -= 1
            if prof == 0:
                try:
                    return json.loads(t[i:j + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _valida(azione: dict) -> bool:
    if not isinstance(azione, dict) or "reazione_breve" not in azione:
        return False
    if jsonschema is not None:
        try:
            jsonschema.validate(azione, SCHEMA_AZIONE)
        except jsonschema.ValidationError:
            return False
    return True


def chiama_llm_e_parsa(prompt: str, responder, tentativi: int = 3) -> dict:
    """Chiama il modello (responder: prompt->testo) con retry finche' il JSON
    non e' valido; in caso di fallimento totale ritorna un'azione vuota."""
    for _ in range(tentativi):
        try:
            testo = responder(prompt)
        except Exception:
            continue
        azione = estrai_json(testo)
        if azione is not None and _valida(azione):
            azione.setdefault("aggiornamenti_stato", {})
            azione.setdefault("azioni_su_archi", [])
            azione.setdefault("genera_eventi", [])
            return azione
    return dict(AZIONE_VUOTA)


def responder_ollama(modello: str, host: str = None, num_ctx: int = 8192,
                     temperature: float = 0.2):
    """Responder di produzione: un modello di testo via Ollama (HPC)."""
    import ollama
    client = ollama.Client(host=host) if host else ollama

    def _resp(prompt: str) -> str:
        r = client.chat(model=modello, messages=[{"role": "user", "content": prompt}],
                        format="json", options={"temperature": temperature, "num_ctx": num_ctx})
        return r["message"]["content"]
    return _resp


# --------------------------------------------------------------------------- #
# 3. CICLO — la simulazione
# --------------------------------------------------------------------------- #
def _applica_stato(stato: dict, chiave: str, valore, log: list, paese: str, rnd: int):
    if "." not in chiave:
        return
    dim, campo = chiave.split(".", 1)
    if dim not in stato:
        return
    if not isinstance(stato[dim], dict):
        stato[dim] = {}
    prima = stato[dim].get(campo)
    stato[dim][campo] = valore
    log.append({"round": rnd, "paese": paese, "campo": chiave,
                "prima": prima, "dopo": valore})


def _relazione_tra(amb: Ambiente, mittente: str, target: str):
    """Descrittore compatto della relazione mittente<->target (se esiste)."""
    if not mittente:
        return None
    for _, b, k, d in amb.R.out_edges(mittente, keys=True, data=True):
        if b == target:
            return {"tipo": k, "peso": round(d["peso"], 1), "verso": f"{mittente} -> {target}"}
    for _, b, k, d in amb.R.out_edges(target, keys=True, data=True):
        if b == mittente:
            return {"tipo": k, "peso": round(d["peso"], 1), "verso": f"{target} -> {mittente}"}
    return None


def simula(evento_iniziale: Evento, responder, n_round: int = 5, verbose: bool = True) -> dict:
    amb = Ambiente()
    core = amb.core
    trim = trimestre_riferimento(evento_iniziale.data)

    stati = {iso: snapshot_stato(iso, trim) for iso in core}
    traiett = {iso: traiettoria(iso, trim) for iso in core}

    storico = []
    snapshots = [{"round": 0, "relazioni": amb.snapshot(),
                  "eventi": [evento_iniziale.as_dict()], "cambi_stato": [], "cambi_archi": []}]
    coda = [evento_iniziale]

    for r in range(1, n_round + 1):
        nuova, cambi_stato, cambi_archi = [], [], []
        for ev in coda:
            target = ev.paese
            if target not in core:
                storico.append({"round": r, "paese": target,
                                "nota": "nodo non-core: non reagisce (nessun profilo)"})
                continue
            rel_mitt = _relazione_tra(amb, ev.mittente, target)
            scheda = costruisci_scheda(amb, target, stati[target], traiett[target])
            azione = chiama_llm_e_parsa(crea_prompt(scheda, ev, rel_mitt), responder)

            for chiave, val in (azione.get("aggiornamenti_stato") or {}).items():
                _applica_stato(stati[target], chiave, val, cambi_stato, target, r)

            archi_ev = []
            for a in (azione.get("azioni_su_archi") or []):
                desc = amb.applica_arco(a.get("op"), target, a.get("verso"),
                                        a.get("tipo"), a.get("peso_delta"))
                desc.update({"motivo": a.get("motivo"), "round": r})
                cambi_archi.append(desc); archi_ev.append(desc)

            eventi_ev = []
            for g in (azione.get("genera_eventi") or []):
                e = Evento(testo=g.get("testo", ""), paese=g.get("verso"),
                           tipo=g.get("tipo", "generico"), mittente=target,
                           data=ev.data, round=r)
                if e.paese:
                    nuova.append(e); eventi_ev.append(e.as_dict())

            storico.append({"round": r, "paese": target,
                            "reazione": azione.get("reazione_breve", ""),
                            "aggiornamenti_stato": azione.get("aggiornamenti_stato", {}),
                            "archi": archi_ev, "eventi_generati": eventi_ev})
            if verbose:
                print(f"[round {r}] {target}: {_tronca(azione.get('reazione_breve',''), 90)}")

        snapshots.append({"round": r, "relazioni": amb.snapshot(),
                          "eventi": [e.as_dict() for e in nuova],
                          "cambi_stato": cambi_stato, "cambi_archi": cambi_archi})
        coda = nuova
        if not coda:
            if verbose:
                print(f"La catena si e' fermata al round {r} (nessun nuovo evento).")
            break

    return {"stati": stati, "storico": storico, "snapshots": snapshots,
            "evento_iniziale": evento_iniziale.as_dict(), "trimestre_rif": trim}


# --------------------------------------------------------------------------- #
# Auto-test locale con un responder MOCK (nessun HPC/LLM richiesto)
# --------------------------------------------------------------------------- #
def responder_mock(prompt: str) -> str:
    """Finto modello deterministico (nessun LLM): reagisce in base al TESTO
    dell'evento. Serve solo a validare la pipeline end-to-end senza HPC."""
    iso = re.search(r"\(([A-Z]{3})\)", prompt)
    iso = iso.group(1) if iso else "???"
    m = re.search(r'testo:\s*"([^"]*)"', prompt)
    ev = (m.group(1) if m else "").lower()
    if any(w in ev for w in ("siccit", "carestia", "emigra", "migrator", "profugh", "iperinflaz")):
        return json.dumps({
            "reazione_breve": f"{iso}: crisi umanitaria in peggioramento, aumentano i profughi.",
            "aggiornamenti_stato": {"carestia.livello_ipc": "fase4_emergenza"},
            "azioni_su_archi": [{"op": "rafforza", "verso": "EGY", "tipo": "migrazione",
                                 "peso_delta": 50000, "motivo": "aumento flussi"}],
            "genera_eventi": [{"verso": "EGY", "tipo": "migrazione",
                               "testo": "forte aumento dei flussi migratori al confine"}],
        })
    if any(w in ev for w in ("ransomware", "cyber", "spionaggio", "sanzioni")):
        return json.dumps({
            "reazione_breve": f"{iso}: pressione cyber, rafforza contromisure e allerta i partner.",
            "aggiornamenti_stato": {"cyber.ruolo": "vittima"},
            "azioni_su_archi": [{"op": "rafforza", "verso": "USA", "tipo": "cyber",
                                 "peso_delta": 2, "motivo": "ritorsione/allerta"}],
            "genera_eventi": [],
        })
    if any(w in ev for w in ("militar", "escalation", "guerra", "offensiva", "confine")):
        return json.dumps({
            "reazione_breve": f"{iso}: escalation del conflitto e nuovi sfollamenti.",
            "aggiornamenti_stato": {"conflitto.descrizione": "escalation improvvisa con nuovi sfollamenti"},
            "azioni_su_archi": [], "genera_eventi": [],
        })
    return json.dumps(dict(AZIONE_VUOTA, reazione_breve=f"{iso}: nessun impatto rilevante."))


if __name__ == "__main__":
    ev = Evento(testo="Grave siccita' colpisce il Darfur, aggravando la carestia.",
                paese="SDN", tipo="generico", data="2018-Q3")
    res = simula(ev, responder_mock, n_round=3)
    print("\n--- riepilogo ---")
    print("round eseguiti:", len(res["snapshots"]) - 1)
    print("voci storico:", len(res["storico"]))
    ultimo = res["snapshots"][-1]
    print("cambi archi (ultimo round):", ultimo["cambi_archi"])
    print("cambi stato (ultimo round):", ultimo["cambi_stato"])
