"""
Seconda passata mirata sul CYBER dei paesi attori.

Solo i trimestri di RUS/CHN/PRK/IRN che a tetto=16 perdevano documenti
cyber (advisory CISA distinti = informazione non ridondante) vengono
ri-estratti a tetto=32, dove tutti i loro documenti cyber ci stanno.
Del nuovo profilo si prende SOLO la sezione `cyber`, che sostituisce
quella vecchia; conflitto/carestia/migrazione/economia/contesto restano
dalla versione a 16 (migliore: piu' specifica, non diluita).

Motivazione e prove: docs/decisioni_progetto.md + test_seconda_passata.py
(a 32 il cyber di RUS passa da 2 a 6 advisory con malware reali e lista
gruppi pulita; i paesi di crisi invece a 32 peggioravano -> esclusi).

Aggiorna i file ufficiali in data/processed/extracted_json/ (scrittura
atomica) ma NON committa: rivedi i before/after stampati e, se non va,
  git checkout -- data/processed/extracted_json/

Server Ollama con Flash Attention e modello 32b gia' avviato.
Uso:  python3 seconda_passata_cyber.py
"""

import json
import time

from jsonschema import Draft202012Validator, ValidationError

from src.extraction import ollama_client, pdf_to_images
from src.extraction.document_index import indicizza_documenti
from src.extraction.pdf_to_images import _ordine_a_rotazione, PAGINE_MAX_PER_DOCUMENTO
from src.extraction.input_assembly import assembla_input
from src.extraction.lmm_extractor import _pulisci, _percorso_output, _salva_atomico
from src.extraction.prompt_builder import costruisci_prompt
from src.utils.config_loader import load_extraction_schema

ollama_client.NUM_CTX = 65536
pdf_to_images.DPI = 170
TETTO = 32
ATTORI = ["RUS", "CHN", "PRK", "IRN"]
CYBER = {"cisa", "enisa", "mddr"}

schema = load_extraction_schema()
validator = Draft202012Validator(schema)


def perde_cyber(docs) -> bool:
    """True se a tetto=16 (rotazione) almeno un documento cyber resta fuori."""
    ordinati = _ordine_a_rotazione(docs)
    budget, tenuti = 16, set()
    for d in ordinati:
        if budget <= 0:
            break
        n = len(d.pagine) if d.pagine is not None else PAGINE_MAX_PER_DOCUMENTO
        preso = min(n, budget)
        if preso > 0:
            tenuti.add(id(d))
            budget -= preso
    return any(id(d) not in tenuti and d.fonte in CYBER for d in ordinati)


# individua i trimestri target
target = []
for iso3 in ATTORI:
    for periodo, docs in indicizza_documenti(iso3).items():
        if perde_cyber(docs):
            target.append((iso3, periodo))
target.sort()
print(f"trimestri da aggiornare (cyber ri-estratto a tetto={TETTO}): {len(target)}")
print("  ", target)

aggiornati, saltati = 0, 0
for iso3, periodo in target:
    docs = indicizza_documenti(iso3).get(periodo, [])
    ia = assembla_input(iso3, periodo, tetto_immagini=TETTO)
    prompt, imgs = costruisci_prompt(ia)
    print(f"\n=== {iso3} {periodo} | {len(imgs)} immagini (a 16 ne mandavamo max 16) ===")
    t0 = time.time()
    try:
        nuovo = _pulisci(json.loads(ollama_client.estrai(prompt, imgs, schema, timeout=400)))
    except Exception as e:
        print(f"  ERRORE ({type(e).__name__}): {e} -> profilo INVARIATO")
        saltati += 1
        continue

    path = _percorso_output(iso3, periodo)
    prof = json.loads(path.read_text(encoding="utf-8"))
    print("  cyber PRIMA:", json.dumps(prof["cyber"], ensure_ascii=False))
    print("  cyber DOPO :", json.dumps(nuovo["cyber"], ensure_ascii=False))

    prof["cyber"] = nuovo["cyber"]
    try:
        validator.validate(prof)
    except ValidationError as e:
        print(f"  profilo risultante NON valido: {e.message} -> profilo INVARIATO")
        saltati += 1
        continue
    _salva_atomico(path, prof)
    aggiornati += 1
    print(f"  aggiornato ({time.time()-t0:.0f}s)")

print(f"\nFatto. Aggiornati {aggiornati}, saltati {saltati} su {len(target)}.")
print("NON e' committato. Rivedi i before/after; per annullare tutto:")
print("  git checkout -- data/processed/extracted_json/")
