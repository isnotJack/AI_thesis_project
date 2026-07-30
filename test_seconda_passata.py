"""
Test seconda passata: ri-estrae alcuni nodi "pesanti" (che a tetto=16
hanno perso documenti) con tetto=32, per capire se piu' documenti
MIGLIORANO il profilo o lo DILUISCONO. Confronta l'output con la versione
gia' salvata a tetto=16 in data/processed/extracted_json/.

Non sovrascrive i file ufficiali: stampa e salva a parte in
data/processed/seconda_passata_test/.

Server Ollama con Flash Attention e modello 32b gia' avviato.
Uso:  python3 test_seconda_passata.py
"""

import json
import time
from pathlib import Path

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
TETTO = 32  # doppio del tetto ufficiale, per recuperare i documenti persi

schema = load_extraction_schema()
validator = Draft202012Validator(schema)
out_dir = Path("data/processed/seconda_passata_test")
out_dir.mkdir(parents=True, exist_ok=True)

CASI = [
    ("YEM", "2020-Q2"),  # perdeva 8 ACAPS + 2 FEWS -> qui ne recupera meta'
    ("RUS", "2022-Q3"),  # perdeva advisory CISA distinti (info cyber non ridondante)
    ("UKR", "2024-Q3"),  # il piu' pesante (16 documenti)
]

for iso3, periodo in CASI:
    print("\n" + "=" * 70)
    print(f"  {iso3} {periodo}  (tetto={TETTO}, confronta con la versione a 16 gia' salvata)")
    print("=" * 70)
    docs = indicizza_documenti(iso3).get(periodo, [])
    ia = assembla_input(iso3, periodo, tetto_immagini=TETTO)
    ia.immagini = documenti_a_immagini(docs, tetto_totale=TETTO)
    prompt, imgs = costruisci_prompt(ia)
    print(f"documenti nel trimestre: {len(docs)} | immagini inviate: {len(imgs)} (a 16 ne inviavamo max 16)")

    t0 = time.time()
    try:
        grezzo = ollama_client.estrai(prompt, imgs, schema, timeout=400)
        dt = time.time() - t0
        ris = _pulisci(json.loads(grezzo))
        try:
            validator.validate(ris); stato = "VALIDO"
        except ValidationError as e:
            stato = f"NON VALIDO: {e.message}"
        print(f"tempo: {dt:.1f}s | schema: {stato}")
        (out_dir / f"{iso3}_{periodo}.json").write_text(json.dumps(ris, indent=2, ensure_ascii=False))
        print("-" * 70)
        print(json.dumps(ris, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"ERRORE dopo {time.time()-t0:.1f}s: {type(e).__name__}: {e}")

print("\n\nFatto. Nuove versioni in data/processed/seconda_passata_test/")
print("Confronta con le originali in data/processed/extracted_json/<PAESE>/")
EOF
