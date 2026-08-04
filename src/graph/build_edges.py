"""
Blocco B (parte 2) - costruzione degli ARCHI del grafo.

Tre tipi di arco, tutti diretti, datati e da dati strutturati (zero LLM):

  1. cyber                 attaccante -> vittima   (CFR: sponsor_stato -> paesi_vittima)
  2. migrazione            origine -> destinazione  (UNHCR: coo -> coa, volume rifugiati)
  3. coinvolgimento_militare interventore -> teatro (ACLED: "Military Forces of X"
                                                     straniero attivo nel paese)

Ogni funzione ritorna una lista di tuple (a_iso3, b_iso3, attributi).
I nomi paese vengono normalizzati a ISO3 con `to_iso3` (pycountry + override).
Le destinazioni/vittime/interventori possono essere paesi fuori dai 17: verranno
aggiunti come nodi "periferici" in build_graph.
"""

import glob
import re
from pathlib import Path

import pandas as pd
import pycountry

RAW = Path(__file__).resolve().parents[2] / "data" / "raw"

# override per i nomi che pycountry gestisce male o per le forme brevi comuni
_OVERRIDE = {
    "United States": "USA", "United States of America": "USA",
    "Russia": "RUS", "Russian Federation": "RUS",
    "Korea (Democratic People's Republic of)": "PRK", "North Korea": "PRK",
    "Korea (Republic of)": "KOR", "South Korea": "KOR",
    "Iran": "IRN", "Iran (Islamic Republic of)": "IRN",
    "Syria": "SYR", "Syrian Arab Republic": "SYR",
    "Venezuela": "VEN", "Turkey": "TUR", "Turkiye": "TUR",
    "Bolivia": "BOL", "Moldova": "MDA", "Tanzania": "TZA",
    "Vietnam": "VNM", "Laos": "LAO", "Czechia": "CZE", "Czech Republic": "CZE",
}
_cache: dict = {}


def to_iso3(nome: str):
    """Nome paese (in qualunque forma) -> codice ISO3, o None se non mappabile."""
    if not isinstance(nome, str):
        return None
    nome = nome.strip()
    if not nome:
        return None
    if nome in _cache:
        return _cache[nome]
    iso = _OVERRIDE.get(nome)
    if iso is None:
        try:
            iso = pycountry.countries.lookup(nome).alpha_3
        except LookupError:
            try:
                iso = pycountry.countries.search_fuzzy(nome)[0].alpha_3
            except LookupError:
                iso = None
    _cache[nome] = iso
    return iso


def _trimestre(data_iso: str):
    try:
        y, m, _ = str(data_iso).split("-")[:3]
        return f"{y}-Q{(int(m) - 1) // 3 + 1}"
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# 1. CYBER  (CFR: sponsor -> vittima)
# --------------------------------------------------------------------------- #
def archi_cyber() -> list:
    """Un arco per incidente cyber datato/non-datato. Gli incidenti vengono
    deduplicati per link (lo stesso incidente compare nel file CFR di piu'
    paesi)."""
    righe = []
    for f in glob.glob(str(RAW / "cyber_advisories" / "*" / "*.csv")):
        righe.append(pd.read_csv(f))
    if not righe:
        return []
    df = pd.concat(righe, ignore_index=True)
    df = df.dropna(subset=["sponsor_stato", "paesi_vittima"])
    chiave = "link" if "link" in df.columns else "titolo"
    df = df.drop_duplicates(subset=[chiave])

    archi = []
    for _, r in df.iterrows():
        a = to_iso3(r["sponsor_stato"])
        if a is None:
            continue
        datato = r.get("fonte_data_evento") != "da_estrarre_con_llm" and pd.notna(r.get("data_evento"))
        periodo = _trimestre(r["data_evento"]) if datato else None
        for v in str(r["paesi_vittima"]).split(","):
            b = to_iso3(v)
            if b is None or b == a:
                continue
            archi.append((a, b, {
                "tipo": "cyber",
                "periodo": periodo,
                "categoria": r.get("categoria") if pd.notna(r.get("categoria")) else None,
                "titolo": r.get("titolo"),
            }))
    return archi


# --------------------------------------------------------------------------- #
# 2. MIGRAZIONE  (UNHCR: origine -> destinazione)
# --------------------------------------------------------------------------- #
def archi_migrazione() -> list:
    """Un arco per (origine, destinazione, anno) con peso = rifugiati."""
    archi = []
    for f in glob.glob(str(RAW / "unhcr" / "*" / "*_destinazioni-dettaglio_*.csv")):
        df = pd.read_csv(f)
        d = df[(df["coa_iso"] != "-") & (df["refugees"].fillna(0) > 0)]
        for _, r in d.iterrows():
            a, b = r.get("coo_iso"), r.get("coa_iso")
            if not isinstance(a, str) or not isinstance(b, str) or a == b:
                continue
            anno = int(r["year"])
            archi.append((a, b, {
                "tipo": "migrazione",
                "periodo": str(anno),
                "anno": anno,
                "peso": int(r["refugees"]),
            }))
    return archi


# --------------------------------------------------------------------------- #
# 3. COINVOLGIMENTO MILITARE  (ACLED: "Military Forces of X" straniero -> teatro)
# --------------------------------------------------------------------------- #
_MIL = re.compile(r"Military Forces of (?:the )?(.+?)(?:\s*\(|$)")


def _paese_militare(actor: str):
    if not isinstance(actor, str):
        return None
    m = _MIL.match(actor)
    return to_iso3(m.group(1)) if m else None


def archi_militari() -> list:
    """Un arco per (interventore straniero, teatro, trimestre), peso = n. eventi
    in cui le forze militari del paese straniero sono attore."""
    from collections import Counter
    conteggi = Counter()  # (x_iso, b_iso, periodo) -> n eventi
    for f in glob.glob(str(RAW / "acled" / "*" / "*_eventi-dettagliati_*.csv")):
        b = Path(f).parent.name  # teatro = paese della cartella
        df = pd.read_csv(f)
        for _, r in df.iterrows():
            periodo = r.get("PERIODO")
            for col in ("actor1", "actor2"):
                x = _paese_militare(r.get(col))
                if x and x != b:
                    conteggi[(x, b, periodo)] += 1
    archi = []
    for (x, b, periodo), n in conteggi.items():
        archi.append((x, b, {"tipo": "coinvolgimento_militare", "periodo": periodo, "peso": n}))
    return archi


if __name__ == "__main__":
    c = archi_cyber()
    m = archi_migrazione()
    mi = archi_militari()
    print(f"cyber: {len(c)} archi | migrazione: {len(m)} archi | militari: {len(mi)} archi")
    print("esempi cyber:", c[:2])
    print("esempi migrazione:", m[:2])
    print("esempi militari:", sorted(mi, key=lambda a: -a[2]['peso'])[:3])
