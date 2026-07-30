import time
from src.extraction import ollama_client, pdf_to_images
from src.extraction.document_index import indicizza_documenti
from src.extraction.pdf_to_images import documenti_a_immagini
from src.extraction.input_assembly import assembla_input
from src.extraction.prompt_builder import costruisci_prompt
from src.utils.config_loader import load_extraction_schema

schema = load_extraction_schema()
ollama_client.NUM_CTX = 65536  # override senza toccare il file
pdf_to_images.DPI = 170

ISO3, PERIODO = "UKR", "2024-Q3"  # 62 immagini potenziali - il trimestre piu' pesante del dataset
indice = indicizza_documenti(ISO3)
docs = indice.get(PERIODO, [])
print(f"{ISO3} {PERIODO}: {len(docs)} documenti, fonti: {[d.fonte for d in docs]}")

ia = assembla_input(ISO3, PERIODO)

for tetto in [16, 24]:
    immagini = documenti_a_immagini(docs, tetto_totale=tetto)
    ia.immagini = immagini
    prompt, imgs = costruisci_prompt(ia)
    print(f"[tetto={tetto}] {len(imgs)} immagini reali, num_ctx={ollama_client.NUM_CTX}, invio...", flush=True)
    t0 = time.time()
    ollama_client.estrai(prompt, imgs, schema)
    print(f"[tetto={tetto}, {len(imgs)} immagini] {time.time()-t0:.1f}s")
