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
from src.extraction.input_assembly import assembla_input
from src.extraction.prompt_builder import costruisci_prompt
from src.utils.config_loader import load_countries, load_extraction_schema, load_period_range

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "processed" / "extracted_json"
TENTATIVI_MAX = 3


def _tutti_i_periodi() -> list:
    periodo = load_period_range()
    inizio_anno = int(periodo["inizio"].split("-Q")[0])
    fine_anno = int(periodo["fine"].split("-Q")[0])
    return [f"{anno}-Q{q}" for anno in range(inizio_anno, fine_anno + 1) for q in range(1, 5)]


def _percorso_output(iso3: str, periodo: str) -> Path:
    return OUTPUT_DIR / iso3 / f"{iso3}_{periodo}.json"


def estrai_singolo(iso3: str, periodo: str, validator: Draft202012Validator, forza: bool = False) -> dict:
    """Estrae ed eventualmente salva il profilo per un singolo (paese, trimestre).

    Ritorna {"stato": "ok" | "saltato" | "fallito", ...}.
    """
    out_path = _percorso_output(iso3, periodo)
    if out_path.exists() and not forza:
        return {"stato": "saltato", "iso3": iso3, "periodo": periodo}

    input_assemblato = assembla_input(iso3, periodo)
    prompt, immagini = costruisci_prompt(input_assemblato)

    ultimo_errore = None
    for tentativo in range(1, TENTATIVI_MAX + 1):
        try:
            grezzo = ollama_client.estrai(prompt, immagini, validator.schema)
            risultato = json.loads(grezzo)
            validator.validate(risultato)
        except (json.JSONDecodeError, ValidationError) as e:
            ultimo_errore = str(e)
            time.sleep(2)
            continue
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(risultato, f, indent=2, ensure_ascii=False)
        return {"stato": "ok", "iso3": iso3, "periodo": periodo, "tentativi": tentativo}

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
            dettaglio = f" ({esito['tentativi']} tentativi)" if esito["stato"] == "ok" else ""
            dettaglio += f" ERRORE: {esito['errore']}" if esito["stato"] == "fallito" else ""
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
