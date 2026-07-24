"""
Indice documenti multimodali (Blocco A).

Per ogni paese, mappa il periodo trimestrale (YYYY-Qn) ai documenti PDF
grezzi rilevanti per quel trimestre, raccolti dalle fonti non strutturate
(ACAPS, FEWS NET, UNHCR/ReliefWeb, CISA, World Bank MPO).

Ogni fonte codifica la data nel nome file in modo diverso:
- acaps: data esatta nel nome (<ISO3>_<YYYY-MM-DD>_...)
- fews_net: anno+mese in inglese (<ISO3>_<YYYY-monthname>_...)
- unhcr_reports: trimestre gia' esplicito nel nome (<ISO3>_<YYYY>Q<n>_...)
- cisa: solo l'anno, ricavato dall'id advisory nel nome (es. AA21-077A ->
  2021); senza mese preciso, il documento viene reso disponibile a tutti
  e 4 i trimestri di quell'anno (approssimazione nota, il volume per
  paese e' comunque basso - poche unita' all'anno)
- worldbank MPO: edizione semestrale (am<YY> ~ Spring Meetings/aprile,
  sm<YY> ~ Annual Meetings/ottobre); l'edizione resta "l'outlook piu'
  aggiornato" finche' non esce la successiva, quindi viene trascinata
  in avanti sui trimestri successivi fino alla prossima edizione

Nota di scope: ENISA Threat Landscape e Microsoft Digital Defense Report
(data/raw/enisa/, data/raw/microsoft_mddr/) NON sono in questo indice.
Sono report globali multi-paese senza split per ISO3: attribuire le
pagine giuste a un singolo paese richiederebbe una ricerca testuale
preliminare (in che pagine viene nominato il paese) invece di un
semplice indice per nome file. Lasciato come miglioramento futuro,
non blocca la pipeline.
"""

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

DATA_RAW = Path(__file__).resolve().parents[2] / "data" / "raw"

MESI_EN = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


@dataclass
class Documento:
    path: Path
    fonte: str  # "acaps" | "fews_net" | "unhcr_reports" | "cisa" | "worldbank_mpo"
    data: "date | None"  # None se non ricavabile con precisione (es. cisa)


def _trimestre(d: date) -> str:
    return f"{d.year}-Q{(d.month - 1) // 3 + 1}"


def _trimestri_anno(anno: int) -> list:
    return [f"{anno}-Q{q}" for q in range(1, 5)]


def _indicizza_acaps(iso3: str) -> dict:
    out: dict = {}
    cartella = DATA_RAW / "acaps" / iso3
    if not cartella.exists():
        return out
    for f in cartella.glob("*.pdf"):
        m = re.match(rf"{iso3}_(\d{{4}}-\d{{2}}-\d{{2}})_", f.name)
        if not m:
            continue
        d = date.fromisoformat(m.group(1))
        out.setdefault(_trimestre(d), []).append(Documento(f, "acaps", d))
    return out


def _indicizza_fews_net(iso3: str) -> dict:
    out: dict = {}
    cartella = DATA_RAW / "fews_net" / iso3
    if not cartella.exists():
        return out
    for f in cartella.glob("*.pdf"):
        m = re.match(rf"{iso3}_(\d{{4}})-([a-z]+)_", f.name)
        if not m:
            continue
        anno, mese_nome = m.group(1), m.group(2)
        mese = MESI_EN.get(mese_nome)
        if mese is None:
            continue
        d = date(int(anno), mese, 1)
        out.setdefault(_trimestre(d), []).append(Documento(f, "fews_net", d))
    return out


def _indicizza_unhcr_reports(iso3: str) -> dict:
    out: dict = {}
    cartella = DATA_RAW / "unhcr_reports" / iso3
    if not cartella.exists():
        return out
    for f in cartella.glob("*.pdf"):
        m = re.match(rf"{iso3}_(\d{{4}})Q(\d)_(\d{{4}}-\d{{2}}-\d{{2}})_", f.name)
        if not m:
            continue
        periodo = f"{m.group(1)}-Q{m.group(2)}"
        d = date.fromisoformat(m.group(3))
        out.setdefault(periodo, []).append(Documento(f, "unhcr_reports", d))
    return out


def _indicizza_cisa(iso3: str) -> dict:
    out: dict = {}
    cartella = DATA_RAW / "cisa" / iso3
    if not cartella.exists():
        return out
    for f in cartella.glob("*.pdf"):
        m = re.search(r"AA(\d{2})-", f.name, re.IGNORECASE)
        if not m:
            continue
        anno = 2000 + int(m.group(1))
        if not (2018 <= anno <= 2024):
            continue
        doc = Documento(f, "cisa", None)
        for periodo in _trimestri_anno(anno):
            out.setdefault(periodo, []).append(doc)
    return out


def _indicizza_mpo(iso3: str) -> dict:
    cartella = DATA_RAW / "worldbank" / iso3
    if not cartella.exists():
        return {}
    edizioni = []
    for f in cartella.glob(f"{iso3}_mpo_*.pdf"):
        m = re.match(rf"{iso3}_mpo_(am|sm)(\d{{2}})", f.name)
        if not m:
            continue
        tipo, yy = m.group(1), int(m.group(2))
        anno = 2000 + yy
        mese = 4 if tipo == "am" else 10
        edizioni.append((date(anno, mese, 1), f))
    edizioni.sort()

    out: dict = {}
    for anno in range(2018, 2025):
        for q in range(1, 5):
            periodo = f"{anno}-Q{q}"
            riferimento = date(anno, q * 3, 1)
            candidate = [e for e in edizioni if e[0] <= riferimento]
            if not candidate:
                continue
            data_edizione, path = candidate[-1]
            out[periodo] = [Documento(path, "worldbank_mpo", data_edizione)]
    return out


def indicizza_documenti(iso3: str) -> dict:
    """Unisce tutte le fonti PDF multimodali per un paese, raggruppate per trimestre.

    Ritorna: {"2018-Q1": [Documento, ...], "2018-Q2": [...], ...}
    Un trimestre senza documenti semplicemente non compare come chiave.
    """
    tutte = [
        _indicizza_acaps(iso3),
        _indicizza_fews_net(iso3),
        _indicizza_unhcr_reports(iso3),
        _indicizza_cisa(iso3),
        _indicizza_mpo(iso3),
    ]
    out: dict = {}
    for indice in tutte:
        for periodo, docs in indice.items():
            out.setdefault(periodo, []).extend(docs)
    return out


if __name__ == "__main__":
    # Sanity check rapido: python document_index.py <ISO3>
    import sys
    iso3 = sys.argv[1] if len(sys.argv) > 1 else "SDN"
    indice = indicizza_documenti(iso3)
    for periodo in sorted(indice):
        fonti = [d.fonte for d in indice[periodo]]
        print(f"{periodo}: {len(indice[periodo])} doc — {fonti}")
