"""
Indice documenti multimodali (Blocco A).

Per ogni paese, mappa il periodo trimestrale (YYYY-Qn) ai documenti PDF
grezzi rilevanti per quel trimestre, raccolti dalle fonti non strutturate
(ACAPS, FEWS NET, UNHCR/ReliefWeb, CISA, World Bank MPO, ENISA, MDDR).

Ogni fonte codifica la data nel nome file in modo diverso:
- acaps: data esatta nel nome (<ISO3>_<YYYY-MM-DD>_...)
- fews_net: anno+mese in inglese (<ISO3>_<YYYY-monthname>_...)
- unhcr_reports: trimestre gia' esplicito nel nome (<ISO3>_<YYYY>Q<n>_...)
- cisa: solo l'anno, ricavato dall'id advisory nel nome (es. AA21-077A ->
  2021); senza mese preciso, il documento viene reso disponibile a tutti
  e 4 i trimestri di quell'anno (approssimazione nota, il volume per
  paese e' comunque basso - poche unita' all'anno)
- worldbank MPO: edizione semestrale (am<YY> = Annual Meetings/ottobre,
  sm<YY> = Spring Meetings/aprile - verificato leggendo l'header reale
  dentro i PDF, il nome delle sigle e' fuorviante); l'edizione resta
  "l'outlook piu' aggiornato" finche' non esce la successiva, quindi
  viene trascinata in avanti sui trimestri successivi fino alla
  prossima edizione
- enisa / mddr: report globali annuali, non divisi per paese. Si cerca
  il nome inglese/aggettivo del paese nel testo di ogni pagina (vedi
  NOMI_RICERCA) e si prendono solo le pagine con piu' menzioni, non
  l'intero report - altrimenti ogni chiamata si ritroverebbe decine di
  pagine perlopiu' irrilevanti. Anno-livello di precisione come CISA
  (il documento e' reso disponibile a tutti e 4 i trimestri dell'anno).
"""

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import fitz

DATA_RAW = Path(__file__).resolve().parents[2] / "data" / "raw"

MESI_EN = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

# nomi/aggettivi inglesi per la ricerca testuale nei report globali
# (ENISA/MDDR non sono in inglese... sono in inglese ma non divisi per
# paese: countries.yaml ha solo il nome italiano, qui serve l'inglese
# per cercare nel testo dei report).
NOMI_RICERCA = {
    "RUS": ["russia", "russian"],
    "CHN": ["china", "chinese", "people's republic of china"],
    "PRK": ["north korea", "dprk", "north korean", "democratic people's republic of korea"],
    "IRN": ["iran", "iranian"],
    "UKR": ["ukraine", "ukrainian"],
    "SDN": ["sudan", "sudanese"],
    "SSD": ["south sudan", "south sudanese"],
    "YEM": ["yemen", "yemeni"],
    "SYR": ["syria", "syrian"],
    "ETH": ["ethiopia", "ethiopian"],
    "VEN": ["venezuela", "venezuelan"],
    "USA": ["united states", "u.s.", "usa", "american"],
    "ISR": ["israel", "israeli"],
    "KOR": ["south korea", "republic of korea", "south korean"],
    "SAU": ["saudi arabia", "saudi"],
    "ITA": ["italy", "italian"],
    "EST": ["estonia", "estonian"],
}

PAGINE_MAX_REPORT_GLOBALE = 3  # tetto pagine prese da un singolo report globale per paese

_cache_testo_pagine = {}


@dataclass
class Documento:
    path: Path
    fonte: str  # "acaps" | "fews_net" | "unhcr_reports" | "cisa" | "worldbank_mpo" | "enisa" | "mddr"
    data: "date | None"  # None se non ricavabile con precisione (es. cisa)
    pagine: "list | None" = None  # se specificato, solo queste pagine (0-indexed) vanno rese in immagine


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
        # verificato leggendo l'header reale dentro i PDF: "am" = Annual
        # Meetings (ottobre), "sm" = Spring Meetings (aprile) - il contrario
        # di quello che il nome suggerirebbe a naso.
        mese = 10 if tipo == "am" else 4
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


def _testo_pagine(path: Path) -> list:
    """Estrae il testo di ogni pagina, con cache in memoria (gli stessi 12
    PDF ENISA/MDDR vengono riletti per ognuno dei 17 paesi)."""
    chiave = str(path)
    if chiave not in _cache_testo_pagine:
        with fitz.open(path) as doc:
            _cache_testo_pagine[chiave] = [p.get_text().lower() for p in doc]
    return _cache_testo_pagine[chiave]


def _pagine_piu_rilevanti(path: Path, termini: list, tetto: int = PAGINE_MAX_REPORT_GLOBALE) -> list:
    """Ritorna gli indici (0-based) delle pagine con piu' menzioni dei
    termini di ricerca, le migliori `tetto` in ordine di rilevanza -> di
    posizione nel documento (cosi' pagine consecutive di uno stesso profilo
    paese restano vicine se possibile)."""
    pattern = re.compile("|".join(re.escape(t) for t in termini), re.IGNORECASE)
    conteggi = [(len(pattern.findall(testo)), i) for i, testo in enumerate(_testo_pagine(path))]
    rilevanti = sorted((c for c in conteggi if c[0] > 0), reverse=True)[:tetto]
    return sorted(i for _conteggio, i in rilevanti)


def _indicizza_report_globali(iso3: str) -> dict:
    termini = NOMI_RICERCA.get(iso3)
    if not termini:
        return {}
    out: dict = {}
    for cartella, fonte in [(DATA_RAW / "enisa", "enisa"), (DATA_RAW / "microsoft_mddr", "mddr")]:
        if not cartella.exists():
            continue
        for f in cartella.glob("*.pdf"):
            m = re.search(r"20\d{2}", f.name)
            if not m:
                continue
            anno = int(m.group(0))
            if not (2018 <= anno <= 2024):
                continue
            pagine = _pagine_piu_rilevanti(f, termini)
            if not pagine:
                continue
            doc = Documento(f, fonte, date(anno, 1, 1), pagine=pagine)
            for periodo in _trimestri_anno(anno):
                out.setdefault(periodo, []).append(doc)
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
        _indicizza_report_globali(iso3),
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
