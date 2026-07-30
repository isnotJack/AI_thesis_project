import time
from src.extraction import ollama_client
from src.extraction.input_assembly import assembla_input
from src.extraction.prompt_builder import costruisci_prompt
from src.utils.config_loader import load_extraction_schema

schema = load_extraction_schema()

t0 = time.time()
r = ollama_client.estrai("Rispondi con un JSON valido secondo lo schema per il Sudan, periodo 2023-Q2.", [], schema)
print(f"[solo testo, 0 immagini] {time.time()-t0:.1f}s")

ia = assembla_input('SDN', '2023-Q2')
prompt, immagini = costruisci_prompt(ia)
print(f"immagini assemblate per SDN 2023-Q2: {len(immagini)}")

t0 = time.time()
r = ollama_client.estrai(prompt, immagini[:1], schema)
print(f"[1 immagine] {time.time()-t0:.1f}s")

t0 = time.time()
r = ollama_client.estrai(prompt, immagini, schema)
print(f"[{len(immagini)} immagini, prompt completo] {time.time()-t0:.1f}s")