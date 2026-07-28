"""
Conversione pagine PDF -> immagini (Blocco A).

Usa PyMuPDF (fitz) per rasterizzare le pagine PDF in PNG, cosi' l'LMM
puo' leggere mappe/grafici/tabelle nei report oltre al testo semplice.

Due tetti per tenere sotto controllo la dimensione della chiamata:
- pagine per documento: le prime N (dove nei report brevi che abbiamo
  raccolto tipicamente sta l'executive summary/i risultati chiave -
  approssimazione ragionevole visto che la mediana e' 5 pagine, ma nota
  per documenti lunghi come alcune analisi ACAPS o i report MPO)
- immagini totali per chiamata: nei trimestri con piu' documenti
  sovrapposti (mediana 3 documenti/trimestre ma coda lunga, fino a 16) si
  taglia dando priorita' alle fonti piu' rilevanti per il contenuto
  narrativo/qualitativo (ACAPS/FEWS NET), poi ai documenti piu' recenti.

DPI e tetto immagini fissati sperimentalmente su Leonardo (A100 40GB,
Qwen2.5-VL:7b, vedi docs/decisioni_progetto.md 2026-07-26): il costo di
un'inferenza cresce piu' che linearmente con i token immagine totali nel
prompt (1 immagine a DPI 170 ~10s, 10 immagini >18min e in salita) - non
e' un blocco, e' calcolo vero (GPU-Util 88% durante l'attesa). Con 476
chiamate nel batch, un tetto piu' alto rende il job intero infattibile
anche spalmato sulle 4 GPU disponibili.
"""

from pathlib import Path

import fitz

DPI = 170
PAGINE_MAX_PER_DOCUMENTO = 4
IMMAGINI_MAX_PER_CHIAMATA = 16

# priorita' di fonte quando serve tagliare (0 = piu' importante)
PRIORITA_FONTE = {
    "acaps": 0,
    "fews_net": 0,
    "unhcr_reports": 1,
    "worldbank_mpo": 1,
    "cisa": 2,
    "enisa": 2,
    "mddr": 2,
}


def pagine_a_immagini(
    path: Path,
    pagine_max: int = PAGINE_MAX_PER_DOCUMENTO,
    pagine_specifiche: list = None,
    dpi: int = None,
) -> list:
    """Ritorna pagine del PDF come lista di PNG (bytes).

    Se `pagine_specifiche` e' data (indici 0-based, es. le pagine di un
    report globale che nominano un paese - vedi document_index), rende
    solo quelle pagine invece delle prime `pagine_max`.

    `dpi` sovrascrive il default del modulo (usato dalla pipeline
    resiliente per ri-renderizzare a risoluzione ridotta in un retry).
    """
    if dpi is None:
        dpi = DPI
    immagini = []
    with fitz.open(path) as doc:
        if pagine_specifiche is not None:
            indici = [i for i in pagine_specifiche if i < len(doc)][:pagine_max]
        else:
            indici = range(min(len(doc), pagine_max))
        for i in indici:
            pix = doc[i].get_pixmap(dpi=dpi)
            immagini.append(pix.tobytes("png"))
    return immagini


def documenti_a_immagini(
    documenti: list,
    tetto_totale: int = IMMAGINI_MAX_PER_CHIAMATA,
    dpi: int = None,
) -> list:
    """documenti: lista di document_index.Documento per un singolo trimestre.

    Ritorna lista di (fonte, nome_file, png_bytes) rispettando `tetto_totale`.
    Se il totale naturale lo supera, taglia per priorita' di fonte e poi per
    data piu' recente. Il nome_file serve a valorizzare il campo "fonti"
    dello schema di estrazione con i documenti davvero usati (dopo il taglio).

    `dpi` sovrascrive il default del modulo; `tetto_totale=0` -> nessuna
    immagine (modalita' solo-testo della pipeline resiliente).
    """
    ordinati = sorted(
        documenti,
        key=lambda d: (PRIORITA_FONTE.get(d.fonte, 9), -(d.data.toordinal() if d.data else 0)),
    )
    out = []
    for doc in ordinati:
        if len(out) >= tetto_totale:
            break
        rimanenti = tetto_totale - len(out)
        immagini = pagine_a_immagini(
            doc.path,
            pagine_max=min(PAGINE_MAX_PER_DOCUMENTO, rimanenti),
            pagine_specifiche=doc.pagine,
            dpi=dpi,
        )
        for png in immagini:
            out.append((doc.fonte, doc.path.name, png))
            if len(out) >= tetto_totale:
                break
    return out


if __name__ == "__main__":
    # Sanity check: python pdf_to_images.py <ISO3> <periodo, es. 2023-Q2>
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.extraction.document_index import indicizza_documenti

    iso3 = sys.argv[1] if len(sys.argv) > 1 else "SDN"
    periodo = sys.argv[2] if len(sys.argv) > 2 else "2023-Q2"

    indice = indicizza_documenti(iso3)
    documenti = indice.get(periodo, [])
    print(f"{iso3} {periodo}: {len(documenti)} documenti nell'indice")
    immagini = documenti_a_immagini(documenti)
    print(f"-> {len(immagini)} immagini generate:")
    for fonte, nome_file, png in immagini:
        print(f"   {fonte} ({nome_file}): {len(png) / 1024:.0f} KB")
