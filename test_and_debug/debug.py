import time
from src.extraction import ollama_client, pdf_to_images
from src.extraction.document_index import indicizza_documenti
from src.extraction.pdf_to_images import documenti_a_immagini
from src.extraction.input_assembly import assembla_input
from src.extraction.prompt_builder import costruisci_prompt
from src.utils.config_loader import load_extraction_schema

schema = load_extraction_schema()
ollama_client.NUM_CTX = 32768  # tornato al valore originale, per isolare l'effetto
pdf_to_images.DPI = 170

ISO3, PERIODO = "UKR", "2024-Q3"
indice = indicizza_documenti(ISO3)
docs = indice.get(PERIODO, [])
ia = assembla_input(ISO3, PERIODO)

immagini = documenti_a_immagini(docs, tetto_totale=16)
ia.immagini = immagini
prompt, imgs = costruisci_prompt(ia)
print(f"[num_ctx=32768, tetto=16] {len(imgs)} immagini, invio...", flush=True)
t0 = time.time()
ollama_client.estrai(prompt, imgs, schema)
print(f"[num_ctx=32768, UKR 2024-Q3, 16 immagini] {time.time()-t0:.1f}s")