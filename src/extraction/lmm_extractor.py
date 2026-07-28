"""
Orchestrazione dell'estrazione LMM (Blocco A).

Per ogni (paese, trimestre) del progetto: assembla l'input (testo +
immagini), chiama Ollama vincolato allo JSON Schema del progetto,
valida difensivamente il risultato e lo salva in
data/processed/extracted_json/<ISO3>/<ISO3>_<periodo>.json.

Resumable: salta le combinazioni gia' estratte (utile su HPC, dove la
pipeline puo' girare a pezzi su piu' job PBS con walltime limitato).
"""

import json
import time
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

from src.extraction import ollama_client
from src.extraction import pdf_to_images
from src.extraction.input_assembly import assembla_input
from src.extraction.prompt_builder import costruisci_prompt
from src.utils.config_loader import load_countries, load_extraction_schema, load_period_range

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "processed" / "extracted_json"

# Scaletta di degrado per la pipeline resiliente: una voce per tentativo,
# (dpi, tetto_immagini, timeout_s). L'ordine e' pensato per perdere il meno
# possibile a ogni passo (vedi docs/decisioni_progetto.md 2026-07-28):
#   1. normale
#   2. ritenta identico - la latenza delle chiamate e' instabile a causa
#      dello stato del server Ollama, non del contenuto: spesso la stessa
#      identica chiamata al secondo tentativo va (caso RUS 2022-Q3).
#   3. DPI ridotto, stesse immagini - meno token, tutte le dimensioni
#      restano rappresentate.
#   4. meno immagini - qui si iniziano a perdere interi documenti.
#   5. solo testo (nessuna immagine) - ultima spiaggia, produce comunque
#      un'estrazione valida da Wikipedia/CFR/CISA.
_DPI = pdf_to_images.DPI
_TETTO = pdf_to_images.IMMAGINI_MAX_PER_CHIAMATA
SCALETTA_RETRY = [
    (_DPI, _TETTO, 180),
    (_DPI, _TETTO, 180),
    (110, _TETTO, 180),
    (110, max(1, _TETTO // 2), 180),
    (None, 0, 120),
]


def _tutti_i_periodi() -> list:
    periodo = load_period_range()
    inizio_anno = int(periodo["inizio"].split("-Q")[0])
    fine_anno = int(periodo["fine"].split("-Q")[0])
    return [f"{anno}-Q{q}" for anno in range(inizio_anno, fine_anno + 1) for q in range(1, 5)]


def _percorso_output(iso3: str, periodo: str) -> Path:
    return OUTPUT_DIR / iso3 / f"{iso3}_{periodo}.json"


def estrai_singolo(iso3: str, periodo: str, validator: Draft202012Validator, forza: bool = False) -> dict:
    """Estrae ed eventualmente salva il profilo per un singolo (paese, trimestre).

    Scorre SCALETTA_RETRY: a ogni rung ri-assembla l'input col DPI/tetto
    di quel rung, chiama Ollama con il timeout del rung e valida. Al primo
    successo salva e ritorna; se tutti i rung falliscono (timeout, JSON
    invalido, errori del server), marca la combinazione come fallita e il
    batch prosegue.

    Ritorna {"stato": "ok" | "saltato" | "fallito", ...}.
    """
    out_path = _percorso_output(iso3, periodo)
    if out_path.exists() and not forza:
        return {"stato": "saltato", "iso3": iso3, "periodo": periodo}

    # ri-assembla solo quando cambiano (dpi, tetto): rung 1 e 2 sono identici
    cache_input = {}

    ultimo_errore = None
    for tentativo, (dpi, tetto, timeout) in enumerate(SCALETTA_RETRY, start=1):
        chiave = (dpi, tetto)
        if chiave not in cache_input:
            ia = assembla_input(iso3, periodo, tetto_immagini=tetto, dpi=dpi)
            cache_input[chiave] = costruisci_prompt(ia)
        prompt, immagini = cache_input[chiave]

        try:
            grezzo = ollama_client.estrai(prompt, immagini, validator.schema, timeout=timeout)
            risultato = json.loads(grezzo)
            validator.validate(risultato)
        except Exception as e:  # timeout httpx, errori del server, JSON/schema invalido
            ultimo_errore = f"{type(e).__name__}: {e}"
            time.sleep(2)
            continue

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(risultato, f, indent=2, ensure_ascii=False)
        return {
            "stato": "ok",
            "iso3": iso3,
            "periodo": periodo,
            "tentativi": tentativo,
            "solo_testo": tetto == 0,
        }

    return {"stato": "fallito", "iso3": iso3, "periodo": periodo, "errore": ultimo_errore}


def estrai_tutti(paesi: list = None, periodi: list = None, forza: bool = False) -> list:
    """Ciclo completo su tutte le combinazioni (paese, trimestre) del progetto."""
    if paesi is None:
        paesi = [p["iso3"] for p in load_countries()]
    if periodi is None:
        periodi = _tutti_i_periodi()

    validator = Draft202012Validator(load_extraction_schema())

    riepilogo = []
    for iso3 in paesi:
        for periodo in periodi:
            esito = estrai_singolo(iso3, periodo, validator, forza=forza)
            dettaglio = ""
            if esito["stato"] == "ok":
                if esito["tentativi"] > 1:
                    dettaglio = f" ({esito['tentativi']} tentativi"
                    dettaglio += ", solo testo)" if esito.get("solo_testo") else ")"
            elif esito["stato"] == "fallito":
                dettaglio = f" ERRORE: {esito['errore']}"
            print(f"[{esito['stato']}] {iso3} {periodo}{dettaglio}")
            riepilogo.append(esito)

    n_ok = sum(1 for r in riepilogo if r["stato"] == "ok")
    n_saltati = sum(1 for r in riepilogo if r["stato"] == "saltato")
    n_falliti = sum(1 for r in riepilogo if r["stato"] == "fallito")
    print(f"\nTotale: {n_ok} estratti, {n_saltati} gia' presenti, {n_falliti} falliti su {len(riepilogo)}")
    return riepilogo


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3:
        validator = Draft202012Validator(load_extraction_schema())
        print(estrai_singolo(sys.argv[1], sys.argv[2], validator, forza=True))
    else:
        estrai_tutti()
