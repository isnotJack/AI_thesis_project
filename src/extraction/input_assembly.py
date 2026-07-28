"""
Assemblaggio dell'input per una chiamata di estrazione (Blocco A).

Per una coppia (paese, periodo) mette insieme:
- immagini dai PDF (ACAPS, FEWS NET, UNHCR/ReliefWeb, CISA, MPO) via
  document_index + pdf_to_images
- testo Wikipedia dell'anno del periodo (l'LMM deriva la sintesi del
  trimestre nello stesso passaggio, in linea con la decisione di design:
  vedi docs/decisioni_progetto.md)
- incidenti CFR con data nota che cadono in quel trimestre come lista
  testuale. Nota: molti incidenti CFR non hanno una data nota (nel csv
  grezzo "fonte_data_evento" == "da_estrarre_con_llm") - restano esclusi
  qui, assegnarli a un trimestre richiederebbe un passaggio di datazione
  a parte, non ancora costruito. E' un limite noto, non un bug.
- advisory CISA con data nota che cadono in quel trimestre, come lista
  testuale compatta (titolo + data) - complemento alle immagini dei PDF
  degli stessi advisory, aiuta l'LMM a enumerarli con precisione.
"""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.extraction.document_index import indicizza_documenti
from src.extraction.pdf_to_images import documenti_a_immagini

DATA_RAW = Path(__file__).resolve().parents[2] / "data" / "raw"


@dataclass
class InputAssemblato:
    paese: str
    periodo: str
    immagini: list  # [(fonte, nome_file, png_bytes), ...]
    testo_wikipedia: str  # stringa vuota se assente
    testo_cfr: str  # stringa vuota se nessun incidente datato in questo trimestre
    testo_cisa: str  # stringa vuota se nessun advisory datato in questo trimestre
    fonti_usate: list  # nomi file/riferimenti effettivamente inclusi nel prompt


def _anno_da_periodo(periodo: str) -> int:
    return int(periodo.split("-Q")[0])


def _trimestre_da_data_iso(data_iso: str) -> str:
    y, m, _d = str(data_iso).split("-")[:3]
    q = (int(m) - 1) // 3 + 1
    return f"{y}-Q{q}"


def _carica_wikipedia(iso3: str, anno: int) -> str:
    path = DATA_RAW / "wikipedia" / iso3 / f"{iso3}_{anno}_wikipedia-context.txt"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _carica_cfr(iso3: str, periodo: str) -> tuple:
    path = DATA_RAW / "cyber_advisories" / iso3 / f"{iso3}_cfr-cyber-operations.csv"
    if not path.exists():
        return "", []
    df = pd.read_csv(path)
    if "fonte_data_evento" in df.columns:
        df = df[df["fonte_data_evento"] != "da_estrarre_con_llm"]
    df = df.dropna(subset=["data_evento"])
    if df.empty:
        return "", []
    df = df[df["data_evento"].apply(_trimestre_da_data_iso) == periodo]
    if df.empty:
        return "", []
    righe, fonti = [], []
    for _, r in df.iterrows():
        righe.append(
            f"- {r['titolo']} ({r['data_evento']}, categoria={r.get('categoria', '?')}): "
            f"sponsor={r.get('sponsor_stato', '?')}, vittime={r.get('paesi_vittima', '?')}, "
            f"ruolo={r.get('ruolo', '?')}. {r.get('descrizione', '')}"
        )
        fonti.append(str(r.get("link") or r["titolo"]))
    return "\n".join(righe), fonti


def _carica_cisa(iso3: str, periodo: str) -> tuple:
    path = DATA_RAW / "cisa" / iso3 / f"{iso3}_cisa-advisories.csv"
    if not path.exists():
        return "", []
    df = pd.read_csv(path)
    df = df.dropna(subset=["data"])
    if df.empty:
        return "", []
    df = df[df["data"].apply(_trimestre_da_data_iso) == periodo]
    if df.empty:
        return "", []
    righe, fonti = [], []
    for _, r in df.iterrows():
        righe.append(f"- {r['titolo']} ({r['data']})")
        fonti.append(str(r.get("link") or r["titolo"]))
    return "\n".join(righe), fonti


def assembla_input(iso3: str, periodo: str, tetto_immagini: int = None, dpi: int = None) -> InputAssemblato:
    """Assembla l'input per (paese, periodo).

    `tetto_immagini` e `dpi` sovrascrivono i default del modulo
    pdf_to_images: servono alla pipeline resiliente per ri-assemblare a
    risoluzione ridotta / meno immagini / solo testo (tetto_immagini=0)
    in un retry, senza toccare le costanti globali.
    """
    indice = indicizza_documenti(iso3)
    documenti_trimestre = indice.get(periodo, [])
    if tetto_immagini is None:
        immagini = documenti_a_immagini(documenti_trimestre, dpi=dpi)
    else:
        immagini = documenti_a_immagini(documenti_trimestre, tetto_totale=tetto_immagini, dpi=dpi)

    anno = _anno_da_periodo(periodo)
    testo_wikipedia = _carica_wikipedia(iso3, anno)
    testo_cfr, fonti_cfr = _carica_cfr(iso3, periodo)
    testo_cisa, fonti_cisa = _carica_cisa(iso3, periodo)

    fonti_usate = sorted(set(nome_file for _, nome_file, _ in immagini) | set(fonti_cfr) | set(fonti_cisa))
    if testo_wikipedia:
        fonti_usate.append(f"wikipedia:{iso3}_{anno}")

    return InputAssemblato(
        paese=iso3,
        periodo=periodo,
        immagini=immagini,
        testo_wikipedia=testo_wikipedia,
        testo_cfr=testo_cfr,
        testo_cisa=testo_cisa,
        fonti_usate=fonti_usate,
    )


if __name__ == "__main__":
    import sys

    iso3 = sys.argv[1] if len(sys.argv) > 1 else "SDN"
    periodo = sys.argv[2] if len(sys.argv) > 2 else "2023-Q2"

    ia = assembla_input(iso3, periodo)
    print(f"{iso3} {periodo}")
    print(f"  immagini: {len(ia.immagini)}")
    print(f"  wikipedia: {'presente' if ia.testo_wikipedia else 'assente'} ({len(ia.testo_wikipedia)} char)")
    print(f"  cfr: {'presente' if ia.testo_cfr else 'assente'}")
    if ia.testo_cfr:
        print("   " + ia.testo_cfr.replace("\n", "\n   "))
    print(f"  cisa: {'presente' if ia.testo_cisa else 'assente'}")
    print(f"  fonti totali: {len(ia.fonti_usate)}")
