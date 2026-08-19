"""
Sorgente cyber EuRepoC (European Repository of Cyber Incidents).

Dataset "Global Dataset of Cyber Incidents" v1.3 (Zenodo 14965395,
licenza CC-BY-NC-4.0): 3.414 incidenti datati 2000-2024, con paese
attaccante (initiator) e paese/i vittima (receiver) via codici ISO alpha-2.

Serve a colmare il buco temporale del CFR (le cui date si fermano al 2019):
EuRepoC copre 2018-2024 con densita' crescente (picco 2022-2024).

Qui leggiamo il CSV una volta e produciamo:
- `archi(core)`  -> archi cyber datati attaccante->vittima (trimestre) che
  toccano almeno uno dei paesi `core`, con fonte='eurepoc';
- `conteggi()`   -> dict {(iso3, periodo): n_incidenti} per il campo
  numerico `n_incidenti_datati` dei nodi (incidente contato se il paese
  compare come attaccante o vittima nel trimestre).

Scelte:
- finestra 2018-2024 (coerente col progetto); incidenti fuori finestra o
  senza data valida vengono ignorati;
- i token non-paese del campo receiver (EUROPE, NATO, MENA, #N/A, ...) e
  gli initiator "Unknown" vengono scartati (teniamo solo codici a 2 lettere
  che mappano a un Paese reale);
- un incidente con piu' vittime genera un arco per ogni vittima-paese
  distinta (stesso principio del CFR sponsor->vittime).
"""

import re
from functools import lru_cache
from pathlib import Path

import pandas as pd
import pycountry

CSV = Path(__file__).resolve().parents[2] / "data" / "raw" / "eurepoc" / "eurepoc_global_1_3.csv"
ANNI = (2018, 2024)

_iso3_cache: dict = {}


def _a2_iso3(tok):
    """Codice alpha-2 -> ISO3, solo se e' un vero Paese (scarta EUROPE, NATO, #N/A...)."""
    if not isinstance(tok, str):
        return None
    t = tok.strip().upper()
    if len(t) != 2 or not t.isalpha():
        return None
    if t in _iso3_cache:
        return _iso3_cache[t]
    try:
        v = pycountry.countries.get(alpha_2=t).alpha_3
    except Exception:
        v = None
    _iso3_cache[t] = v
    return v


def _lista_iso3(val):
    """Campo 'A;B;A' -> lista ISO3 unica, scartando i token non-paese."""
    if not isinstance(val, str):
        return []
    out = []
    for tok in val.split(";"):
        iso = _a2_iso3(tok)
        if iso and iso not in out:
            out.append(iso)
    return out


def _trimestre(dt) -> str:
    return f"{dt.year}-Q{(dt.month - 1) // 3 + 1}"


@lru_cache(maxsize=1)
def _incidenti() -> list:
    """Lista di incidenti nella finestra, gia' normalizzati.
    Ogni voce: {id, periodo, ini:[iso3], rec:[iso3], tipo, nome, paesi:set}."""
    df = pd.read_csv(CSV, low_memory=False)
    df["dt"] = pd.to_datetime(df["start_date"], format="%d.%m.%Y", errors="coerce")
    df = df.dropna(subset=["dt"])
    df = df[(df["dt"].dt.year >= ANNI[0]) & (df["dt"].dt.year <= ANNI[1])]

    out = []
    for _, r in df.iterrows():
        ini = _lista_iso3(r.get("initiator_alpha_2"))
        rec = _lista_iso3(r.get("receiver_country_alpha_2_code"))
        if not (ini or rec):
            continue
        out.append({
            "id": r.get("incident_id"),
            "periodo": _trimestre(r["dt"]),
            "ini": ini, "rec": rec,
            "tipo": r.get("incident_type") if pd.notna(r.get("incident_type")) else None,
            "nome": r.get("name") if pd.notna(r.get("name")) else None,
            "paesi": set(ini) | set(rec),
        })
    return out


def archi(core: set) -> list:
    """Archi cyber datati attaccante->vittima che toccano almeno un paese core."""
    archi = []
    for inc in _incidenti():
        for a in inc["ini"]:
            for b in inc["rec"]:
                if a == b:
                    continue
                if a in core or b in core:
                    archi.append((a, b, {
                        "tipo": "cyber", "periodo": inc["periodo"],
                        "categoria": inc["tipo"], "titolo": inc["nome"],
                        "fonte": "eurepoc",
                    }))
    return archi


@lru_cache(maxsize=1)
def conteggi() -> dict:
    """{(iso3, periodo): n_incidenti} - incidente contato per ogni paese
    coinvolto (attaccante o vittima) nel trimestre, senza doppioni per id."""
    acc: dict = {}
    for inc in _incidenti():
        for iso in inc["paesi"]:
            acc.setdefault((iso, inc["periodo"]), set()).add(inc["id"])
    return {k: len(v) for k, v in acc.items()}


if __name__ == "__main__":
    inc = _incidenti()
    print(f"EuRepoC: {len(inc)} incidenti 2018-2024 con data valida")
    core = {"RUS", "CHN", "PRK", "IRN", "UKR", "SDN", "SSD", "YEM", "SYR",
            "ETH", "VEN", "USA", "ISR", "KOR", "SAU", "ITA", "EST"}
    a = archi(core)
    print(f"archi cyber (toccano i 17): {len(a)}")
    from collections import Counter
    top = Counter((x[0], x[1]) for x in a).most_common(8)
    print("top coppie:", top)
