"""
A/B test: stessi casi ma con tetto immagini = 24 invece di 16.

Serve a capire se aggiungere PROFONDITA' (piu' pagine per documento; a 16
con la rotazione le dimensioni sono gia' tutte coperte, quindi 24 non
aggiunge fonti nuove ma piu' pagine delle stesse) migliora la qualita' -
in particolare se stabilizza il cyber di RUS, che a 16 degenera nella
lista gruppi. Confronta l'output con quello di test_qualita.py (tetto=16).

Server Ollama gia' avviato con Flash Attention e modello 32b.
Uso:  python3 test_24.py
"""

import json
import time

from jsonschema import Draft202012Validator, ValidationError

from src.extraction import ollama_client, pdf_to_images
from src.extraction.document_index import indicizza_documenti
from src.extraction.pdf_to_images import documenti_a_immagini
from src.extraction.input_assembly import assembla_input
from src.extraction.lmm_extractor import _pulisci
from src.extraction.prompt_builder import costruisci_prompt
from src.utils.config_loader import load_extraction_schema

ollama_client.NUM_CTX = 65536
pdf_to_images.DPI = 170
TETTO = 24  # <-- la differenza rispetto a test_qualita.py

schema = load_extraction_schema()
validator = Draft202012Validator(schema)

CASI = [
    ("RUS", "2022-Q3"),  # a 16 la lista gruppi degenera: vediamo se a 24 migliora
    ("UKR", "2024-Q3"),  # caso piu' pesante
]

for iso3, periodo in CASI:
    print("\n" + "=" * 70)
    print(f"  {iso3} {periodo}  (tetto={TETTO})")
    print("=" * 70)

    docs = indicizza_documenti(iso3).get(periodo, [])
    ia = assembla_input(iso3, periodo, tetto_immagini=TETTO)
    ia.immagini = documenti_a_immagini(docs, tetto_totale=TETTO)
    prompt, imgs = costruisci_prompt(ia)
    print(f"immagini: {len(imgs)}")

    t0 = time.time()
    try:
        grezzo = ollama_client.estrai(prompt, imgs, schema, timeout=400)
        dt = time.time() - t0
        risultato = _pulisci(json.loads(grezzo))
        try:
            validator.validate(risultato)
            stato = "VALIDO"
        except ValidationError as e:
            stato = f"NON VALIDO: {e.message}"
        print(f"tempo: {dt:.1f}s | schema: {stato}")
        print("-" * 70)
        print(json.dumps(risultato, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"ERRORE dopo {time.time() - t0:.1f}s: {type(e).__name__}: {e}")

print("\n\nFatto.")
