"""
Test di qualita' dell'estrazione LMM (Blocco A).

Gira l'estrazione su alcuni casi diversi con i parametri definitivi e
stampa i JSON prodotti (oltre a salvarli), per giudicare a occhio la
qualita' del modello prima di lanciare il batch completo sulle 476
combinazioni. NON e' un test di tempo (quello e' chiuso): serve a vedere
se il modello riempie i campi in modo sensato e se rispetta la disciplina
"vuoto dove non ci sono documenti".

Server Ollama da avviare PRIMA, con Flash Attention:
    pkill -9 ollama; sleep 2
    export OLLAMA_FLASH_ATTENTION=1
    ollama serve &
    sleep 5   # nel log deve comparire "enabling flash attention"
    python3 test_qualita.py
"""

import json
import time
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

from src.extraction import ollama_client, pdf_to_images
from src.extraction.document_index import indicizza_documenti
from src.extraction.pdf_to_images import documenti_a_immagini
from src.extraction.input_assembly import assembla_input
from src.extraction.prompt_builder import costruisci_prompt
from src.utils.config_loader import load_extraction_schema

# parametri definitivi (vedi docs/decisioni_progetto.md 2026-07-28)
ollama_client.NUM_CTX = 65536
pdf_to_images.DPI = 170
TETTO = 16

schema = load_extraction_schema()
validator = Draft202012Validator(schema)

CASI = [
    ("YEM", "2020-Q2"),  # crisi umanitaria: conflitto/carestia/migrazione/economia, NESSUN cyber
    ("SDN", "2023-Q2"),  # guerra, NESSUN cyber
    ("RUS", "2022-Q3"),  # attore cyber: CISA/ENISA/MDDR, NESSUN conflitto/carestia/migrazione
    ("EST", "2022-Q1"),  # controllo: solo report globali cyber (ENISA/MDDR)
]

out_dir = Path("data/processed/debug_qualita")
out_dir.mkdir(parents=True, exist_ok=True)

for iso3, periodo in CASI:
    print("\n" + "=" * 70)
    print(f"  {iso3} {periodo}")
    print("=" * 70)

    indice = indicizza_documenti(iso3)
    docs = indice.get(periodo, [])
    ia = assembla_input(iso3, periodo)
    ia.immagini = documenti_a_immagini(docs, tetto_totale=TETTO)
    prompt, imgs = costruisci_prompt(ia)

    fonti_img = [f"{f}:{n}" for f, n, _ in ia.immagini]
    print(f"immagini: {len(imgs)} -> {fonti_img}")
    print(
        f"testo: wikipedia={'si' if ia.testo_wikipedia else 'no'}, "
        f"cfr={'si' if ia.testo_cfr else 'no'}, cisa={'si' if ia.testo_cisa else 'no'}"
    )

    t0 = time.time()
    try:
        grezzo = ollama_client.estrai(prompt, imgs, schema, timeout=300)
        dt = time.time() - t0
        risultato = json.loads(grezzo)
        try:
            validator.validate(risultato)
            stato_val = "VALIDO"
        except ValidationError as e:
            stato_val = f"NON VALIDO: {e.message}"
        print(f"tempo: {dt:.1f}s | schema: {stato_val}")
        print("-" * 70)
        print(json.dumps(risultato, indent=2, ensure_ascii=False))
        with open(out_dir / f"{iso3}_{periodo}.json", "w", encoding="utf-8") as f:
            json.dump(risultato, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"ERRORE dopo {time.time() - t0:.1f}s: {type(e).__name__}: {e}")

print("\n\nFatto. JSON salvati in data/processed/debug_qualita/")
