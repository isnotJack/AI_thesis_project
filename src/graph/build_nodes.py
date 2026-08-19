"""
Blocco B - arricchimento dei nodi (parte numerica).

Ogni nodo (paese, trimestre) ha gia' la parte QUALITATIVA prodotta dal
Blocco A in data/processed/extracted_json/. Qui aggiungiamo la parte
NUMERICA presa direttamente dai CSV puliti (mai passati dall'LLM):

- conflitto  <- ACLED (eventi violenti e vittime nel trimestre)
- migrazione <- UNHCR (rifugiati, richiedenti asilo, sfollati - annuale)
- economia   <- World Bank (tasso di poverta' - annuale)
- cyber      <- CFR (numero di incidenti datati nel trimestre)
- carestia   <- nessun dato numerico esiste (solo qualitativo dall'LLM)

I due livelli restano affiancati come campi diversi dello stesso nodo:
il qualitativo (testo) descrive, il numerico misura. Non c'e' fusione ne'
conflitto perche' l'LLM per costruzione non produce numeri (regola del
prompt), quindi la verita' numerica viene solo dai CSV.

I valori annuali (migrazione, poverta') vengono ripetuti su tutti e 4 i
trimestri dell'anno. Un valore mancante nel CSV resta null (gap reale
della fonte, non un errore).

Output: data/processed/nodi/<ISO3>/<ISO3>_<periodo>.json (extracted_json
resta intatto come registro grezzo dell'LLM).
"""

import json
from pathlib import Path

import pandas as pd

from src.graph import eurepoc

BASE = Path(__file__).resolve().parents[2]
EXTRACTED = BASE / "data" / "processed" / "extracted_json"
RAW = BASE / "data" / "raw"
OUT = BASE / "data" / "processed" / "nodi"

# ACLED: "eventi di conflitto" = violenza politica (esclude proteste,
# rivolte, strategic developments). Coerente con il conteggio trimestrale
# ufficiale gia' raccolto.
EVENTI_VIOLENTI = {"Battles", "Explosions/Remote violence", "Violence against civilians"}


def _anno(periodo: str) -> int:
    return int(periodo.split("-Q")[0])


def _int_o_none(v):
    if pd.isna(v) or str(v).strip() in ("-", ""):
        return None
    return int(float(v))


def _acled(iso3: str, periodo: str):
    """(n_eventi_violenti, n_vittime) nel trimestre. None se manca il file."""
    f = RAW / "acled" / iso3 / f"{iso3}_eventi-dettagliati_2018-2024.csv"
    if not f.exists():
        return None, None
    df = pd.read_csv(f)
    q = df[(df["PERIODO"] == periodo) & (df["event_type"].isin(EVENTI_VIOLENTI))]
    return int(len(q)), int(q["fatalities"].fillna(0).sum())


def _unhcr(iso3: str, anno: int):
    """(rifugiati, richiedenti_asilo, sfollati_interni) in uscita, annuale."""
    f = RAW / "unhcr" / iso3 / f"{iso3}_flusso-uscita-annuale_2018-2024.csv"
    if not f.exists():
        return None, None, None
    df = pd.read_csv(f)
    r = df[df["year"] == anno]
    if r.empty:
        return None, None, None
    row = r.iloc[0]
    return _int_o_none(row.get("refugees")), _int_o_none(row.get("asylum_seekers")), _int_o_none(row.get("idps"))


def _poverta(iso3: str, anno: int):
    """tasso di poverta' % (annuale). None se assente (buco reale della fonte)."""
    f = RAW / "worldbank" / iso3 / f"{iso3}_poverta-annuale_2018-2024.csv"
    if not f.exists():
        return None
    df = pd.read_csv(f)
    r = df[df["anno"] == anno]
    if r.empty:
        return None
    v = r.iloc[0].get("tasso_poverta_pct")
    return float(v) if pd.notna(v) else None


def _cfr_n_incidenti(iso3: str, periodo: str) -> int:
    """quanti incidenti cyber CFR con data nota cadono nel trimestre."""
    f = RAW / "cyber_advisories" / iso3 / f"{iso3}_cfr-cyber-operations.csv"
    if not f.exists():
        return 0
    df = pd.read_csv(f)
    if "fonte_data_evento" in df.columns:
        df = df[df["fonte_data_evento"] != "da_estrarre_con_llm"]
    df = df.dropna(subset=["data_evento"])
    if df.empty:
        return 0
    dt = pd.to_datetime(df["data_evento"], errors="coerce")
    anno, q = periodo.split("-Q")
    mesi = [(int(q) - 1) * 3 + m for m in (1, 2, 3)]
    return int(((dt.dt.year == int(anno)) & (dt.dt.month.isin(mesi))).sum())


def _n_incidenti_datati(iso3: str, periodo: str) -> int:
    """Incidenti cyber datati nel trimestre in cui il paese compare (come
    attaccante o vittima). Fonte primaria EuRepoC (datato 2018-2024); fallback
    al CFR se EuRepoC non ha nulla per quel trimestre."""
    n = eurepoc.conteggi().get((iso3, periodo), 0)
    return n if n else _cfr_n_incidenti(iso3, periodo)


def arricchisci(iso3: str, periodo: str) -> dict:
    """Carica il profilo qualitativo e vi affianca i campi numerici dai CSV."""
    prof = json.loads((EXTRACTED / iso3 / f"{iso3}_{periodo}.json").read_text(encoding="utf-8"))
    anno = _anno(periodo)

    n_eventi, n_vittime = _acled(iso3, periodo)
    rifugiati, asilo, sfollati = _unhcr(iso3, anno)
    poverta = _poverta(iso3, anno)
    n_cyber = _n_incidenti_datati(iso3, periodo)

    prof["conflitto"]["n_eventi_violenti"] = n_eventi
    prof["conflitto"]["n_vittime"] = n_vittime
    prof["migrazione"]["rifugiati"] = rifugiati
    prof["migrazione"]["richiedenti_asilo"] = asilo
    prof["migrazione"]["sfollati_interni"] = sfollati
    prof["economia"]["tasso_poverta_pct"] = poverta
    prof["cyber"]["n_incidenti_datati"] = n_cyber
    return prof


def costruisci_tutti() -> int:
    n = 0
    for f in sorted(EXTRACTED.glob("*/*.json")):
        iso3 = f.parent.name
        periodo = f.stem.replace(f"{iso3}_", "")
        nodo = arricchisci(iso3, periodo)
        out = OUT / iso3 / f"{iso3}_{periodo}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(nodo, indent=2, ensure_ascii=False), encoding="utf-8")
        n += 1
    return n


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3:
        print(json.dumps(arricchisci(sys.argv[1], sys.argv[2]), indent=2, ensure_ascii=False))
    else:
        tot = costruisci_tutti()
        print(f"Nodi arricchiti scritti in {OUT}: {tot}")
