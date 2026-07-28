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
import os
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


# stringhe che il modello a volte scrive al posto del vero null JSON
_STRINGHE_VUOTE = {"", "null", "none", "n/a", "na", "nessuno", "nessuna", "non specificato"}


def _normalizza_null(v):
    if isinstance(v, str) and v.strip().lower() in _STRINGHE_VUOTE:
        return None
    return v


def _dedup(lista: list) -> list:
    """Rimuove i duplicati preservando l'ordine (il 32b a volte entra in
    loop e ripete lo stesso elemento nell'array - vedi caso RUS/Viasat)."""
    visti, out = set(), []
    for x in lista:
        if x not in visti:
            visti.add(x)
            out.append(x)
    return out


def _pulisci(risultato: dict) -> dict:
    """Post-processing deterministico a valle del modello:
    - normalizza la stringa "null" (e simili) nel vero null JSON;
    - deduplica gli array cyber e il campo fonti.
    Non aggiunge/inventa nulla: ripulisce solo forme sbagliate dello stesso
    contenuto. Applicato prima della validazione, che quindi passa comunque.
    """
    for sez in ("conflitto", "carestia", "migrazione"):
        campo = risultato.get(sez)
        if isinstance(campo, dict) and "descrizione" in campo:
            campo["descrizione"] = _normalizza_null(campo["descrizione"])
    eco = risultato.get("economia")
    if isinstance(eco, dict) and "sintesi" in eco:
        eco["sintesi"] = _normalizza_null(eco["sintesi"])
    risultato["contesto_generale"] = _normalizza_null(risultato.get("contesto_generale"))

    cyber = risultato.get("cyber")
    if isinstance(cyber, dict):
        for campo in ("incidenti_noti", "advisory_che_menzionano_il_paese",
                      "gruppi_minaccia_associati", "settori_bersaglio"):
            if isinstance(cyber.get(campo), list):
                cyber[campo] = _dedup(cyber[campo])
    if isinstance(risultato.get("fonti"), list):
        risultato["fonti"] = _dedup(risultato["fonti"])
    return risultato


def _salva_atomico(out_path: Path, risultato: dict) -> None:
    """Scrive su un file temporaneo e poi rinomina: se il processo viene
    fermato a meta' scrittura non resta mai un JSON troncato che verrebbe
    scambiato per 'gia' fatto' allo restart (stop/restart sicuro)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(risultato, f, indent=2, ensure_ascii=False)
    os.replace(tmp, out_path)


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
            risultato = _pulisci(json.loads(grezzo))
            validator.validate(risultato)
        except Exception as e:  # timeout httpx, errori del server, JSON/schema invalido
            ultimo_errore = f"{type(e).__name__}: {e}"
            time.sleep(2)
            continue

        _salva_atomico(out_path, risultato)
        return {
            "stato": "ok",
            "iso3": iso3,
            "periodo": periodo,
            "tentativi": tentativo,
            "solo_testo": tetto == 0,
        }

    return {"stato": "fallito", "iso3": iso3, "periodo": periodo, "errore": ultimo_errore}


def _tutte_le_combinazioni() -> list:
    """Lista piatta di tutte le (paese, periodo) del progetto, in ordine."""
    paesi = [p["iso3"] for p in load_countries()]
    periodi = _tutti_i_periodi()
    return [(iso3, periodo) for iso3 in paesi for periodo in periodi]


def estrai_lista(combinazioni: list, forza: bool = False, etichetta: str = "") -> list:
    """Estrae una lista esplicita di (paese, periodo). Resumable: le
    combinazioni gia' presenti su disco vengono saltate."""
    validator = Draft202012Validator(load_extraction_schema())
    riepilogo = []
    for iso3, periodo in combinazioni:
        esito = estrai_singolo(iso3, periodo, validator, forza=forza)
        dettaglio = ""
        if esito["stato"] == "ok" and esito["tentativi"] > 1:
            dettaglio = f" ({esito['tentativi']} tentativi"
            dettaglio += ", solo testo)" if esito.get("solo_testo") else ")"
        elif esito["stato"] == "fallito":
            dettaglio = f" ERRORE: {esito['errore']}"
        print(f"{etichetta}[{esito['stato']}] {iso3} {periodo}{dettaglio}", flush=True)
        riepilogo.append(esito)

    n_ok = sum(1 for r in riepilogo if r["stato"] == "ok")
    n_saltati = sum(1 for r in riepilogo if r["stato"] == "saltato")
    n_falliti = sum(1 for r in riepilogo if r["stato"] == "fallito")
    print(f"{etichetta}Totale: {n_ok} estratti, {n_saltati} gia' presenti, "
          f"{n_falliti} falliti su {len(riepilogo)}", flush=True)
    return riepilogo


def estrai_tutti(paesi: list = None, periodi: list = None, forza: bool = False) -> list:
    """Ciclo completo su tutte le combinazioni (paese, trimestre) del progetto."""
    if paesi is None and periodi is None:
        combinazioni = _tutte_le_combinazioni()
    else:
        paesi = paesi or [p["iso3"] for p in load_countries()]
        periodi = periodi or _tutti_i_periodi()
        combinazioni = [(iso3, periodo) for iso3 in paesi for periodo in periodi]
    return estrai_lista(combinazioni, forza=forza)


def estrai_partizione(worker: int, nworker: int, forza: bool = False) -> list:
    """Estrae solo la fetta [worker::nworker] delle combinazioni totali,
    interleavata per bilanciare il carico (i paesi pesanti sono sparsi).
    Un worker per GPU - vedi scripts_hpc/estrazione_parallela.sh."""
    combinazioni = _tutte_le_combinazioni()[worker::nworker]
    return estrai_lista(combinazioni, forza=forza, etichetta=f"[w{worker}] ")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Estrazione LMM Blocco A")
    ap.add_argument("--paese", help="ISO3 di un singolo paese (tutti i suoi trimestri)")
    ap.add_argument("--periodo", help="un singolo trimestre YYYY-Qn (usare con --paese)")
    ap.add_argument("--worker", type=int, help="indice worker per l'esecuzione parallela")
    ap.add_argument("--nworker", type=int, default=1, help="numero totale di worker")
    ap.add_argument("--forza", action="store_true", help="ri-estrae anche se il file esiste")
    args = ap.parse_args()

    if args.paese and args.periodo:
        validator = Draft202012Validator(load_extraction_schema())
        print(estrai_singolo(args.paese, args.periodo, validator, forza=True))
    elif args.paese:
        estrai_lista([(args.paese, p) for p in _tutti_i_periodi()], forza=args.forza)
    elif args.worker is not None:
        estrai_partizione(args.worker, args.nworker, forza=args.forza)
    else:
        estrai_tutti(forza=args.forza)
