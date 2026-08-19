"""
Blocco C - Stato dell'agente ("scheda-paese").

Lo stato con cui ragiona un agente-Paese e' costruito dai profili arricchiti del
Blocco B (data/processed/nodi/<ISO3>/), SENZA nuove chiamate LLM:

- SNAPSHOT del trimestre di riferimento (tutte le 6 dimensioni, qual + quant);
  e' la parte che poi la simulazione fa evolvere.
- TRAIETTORIA programmatica: come si sono mossi i numeri chiave nei trimestri
  FINO al trimestre di riferimento (niente futuro). Calcolata dai dati, non
  dall'LLM (coerente con la regola del progetto: i numeri non li inventa il modello).
- RELAZIONI correnti del Paese (dal grafo/ambiente).

Trimestre di riferimento = quello dell'evento se datato, altrimenti l'ultimo (2024-Q4).
"""

import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
NODI = BASE / "data" / "processed" / "nodi"
ULTIMO_TRIMESTRE = "2024-Q4"

# campi numerici per dimensione (per la traiettoria)
NUMERICI = {
    "conflitto": ["n_eventi_violenti", "n_vittime"],
    "migrazione": ["rifugiati", "richiedenti_asilo", "sfollati_interni"],
    "economia": ["tasso_poverta_pct"],
    "cyber": ["n_incidenti_datati"],
}


def _trimestri(iso3: str) -> list:
    return sorted(p.stem.replace(f"{iso3}_", "") for p in (NODI / iso3).glob(f"{iso3}_*.json"))


def _carica(iso3: str, trimestre: str) -> dict:
    return json.loads((NODI / iso3 / f"{iso3}_{trimestre}.json").read_text(encoding="utf-8"))


def trimestre_riferimento(data_evento) -> str:
    """'AAAA-Qn' se l'evento e' datato ed esiste, altrimenti l'ultimo trimestre."""
    if isinstance(data_evento, str) and len(data_evento) >= 6 and "-Q" in data_evento:
        return data_evento
    return ULTIMO_TRIMESTRE


def snapshot_stato(iso3: str, trimestre: str) -> dict:
    """Le 6 dimensioni del trimestre di riferimento (dizionario mutabile: e' lo
    stato che la simulazione aggiorna)."""
    prof = _carica(iso3, trimestre)
    return {k: prof.get(k) for k in
            ("contesto_generale", "conflitto", "carestia", "migrazione", "economia", "cyber")}


def _trend(serie: list) -> str:
    vals = [v for v in serie if isinstance(v, (int, float))]
    if len(vals) < 2:
        return "n/d"
    inizio = sum(vals[:2]) / len(vals[:2])
    fine = sum(vals[-2:]) / len(vals[-2:])
    if fine > inizio * 1.2:
        return "in aumento"
    if fine < inizio * 0.8:
        return "in calo"
    return "stabile"


def traiettoria(iso3: str, trimestre_rif: str) -> dict:
    """Andamento dei numeri chiave nei trimestri <= trimestre_rif."""
    tt = [t for t in _trimestri(iso3) if t <= trimestre_rif]
    out = {}
    for dim, campi in NUMERICI.items():
        for campo in campi:
            serie = []
            for t in tt:
                v = (_carica(iso3, t).get(dim) or {}).get(campo)
                serie.append(v)
            noti = [v for v in serie if isinstance(v, (int, float))]
            if not noti:
                continue
            out[f"{dim}.{campo}"] = {
                "trend": _trend(serie),
                "ultimo": serie[-1],
                "min": min(noti), "max": max(noti),
            }
    return out


def costruisci_scheda(amb, iso3: str, stato_corrente: dict, traiett: dict) -> dict:
    """Assembla la scheda passata all'agente. `stato_corrente` e `traiett`
    vengono forniti dal motore (lo stato puo' essere gia' stato modificato nei
    round precedenti; la traiettoria e' statica)."""
    return {
        "paese": amb.nomi.get(iso3, iso3),
        "iso3": iso3,
        "gruppo": amb.gruppi.get(iso3),
        "stato": stato_corrente,
        "traiettoria": traiett,
        "relazioni": amb.relazioni(iso3),
    }
