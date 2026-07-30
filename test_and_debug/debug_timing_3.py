import time
from src.extraction import ollama_client, pdf_to_images
from src.extraction.document_index import indicizza_documenti
from src.extraction.pdf_to_images import documenti_a_immagini
from src.extraction.input_assembly import assembla_input
from src.extraction.prompt_builder import costruisci_prompt
from src.utils.config_loader import load_extraction_schema

schema = load_extraction_schema()

ISO3, PERIODO = "YEM", "2020-Q2"
indice = indicizza_documenti(ISO3)
docs = indice.get(PERIODO, [])
ia = assembla_input(ISO3, PERIODO)

pdf_to_images.DPI = 170
print(f"=== DPI={pdf_to_images.DPI}, tetto crescente ===")
for tetto in [8, 16, 24]:
    immagini = documenti_a_immagini(docs, tetto_totale=tetto)
    ia.immagini = immagini
    prompt, imgs = costruisci_prompt(ia)
    print(f"[tetto={tetto}] {len(imgs)} immagini reali, invio...", flush=True)
    t0 = time.time()
    ollama_client.estrai(prompt, imgs, schema)
    print(f"[DPI=170, tetto={tetto}, {len(imgs)} immagini] {time.time()-t0:.1f}s")
