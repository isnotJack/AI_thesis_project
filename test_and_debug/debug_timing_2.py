import time
from src.extraction import ollama_client, pdf_to_images
from src.extraction.document_index import indicizza_documenti
from src.extraction.pdf_to_images import documenti_a_immagini
from src.extraction.input_assembly import assembla_input
from src.extraction.prompt_builder import costruisci_prompt
from src.utils.config_loader import load_extraction_schema

schema = load_extraction_schema()

ISO3 = "YEM"
PERIODO = "2020-Q2"  # 14 documenti, ~56 immagini potenziali - stress test vero

indice = indicizza_documenti(ISO3)
docs = indice.get(PERIODO, [])
print(f"{ISO3} {PERIODO}: {len(docs)} documenti, fonti: {[d.fonte for d in docs]}")

ia = assembla_input(ISO3, PERIODO)  # testo (wikipedia/cfr/cisa) resta uguale, cambiamo solo le immagini

print(f"\n=== DPI={pdf_to_images.DPI} (attuale), tetto crescente ===")
for tetto in [4, 8, 12, 16]:
    immagini = documenti_a_immagini(docs, tetto_totale=tetto)
    ia.immagini = immagini
    prompt, imgs = costruisci_prompt(ia)
    print(f"[tetto={tetto}] {len(imgs)} immagini reali, invio...", flush=True)
    t0 = time.time()
    ollama_client.estrai(prompt, imgs, schema)
    print(f"[tetto={tetto}, {len(imgs)} immagini] {time.time()-t0:.1f}s")

# confronto diretto a parita' di 4 immagini: solo DPI cambia
pdf_to_images.DPI = 170
print(f"\n=== DPI={pdf_to_images.DPI}, tetto=4 (confronto diretto) ===")
immagini = documenti_a_immagini(docs, tetto_totale=4)
ia.immagini = immagini
prompt, imgs = costruisci_prompt(ia)
print(f"[DPI=170, tetto=4] {len(imgs)} immagini reali, invio...", flush=True)
t0 = time.time()
ollama_client.estrai(prompt, imgs, schema)
print(f"[DPI=170, tetto=4, {len(imgs)} immagini] {time.time()-t0:.1f}s")
