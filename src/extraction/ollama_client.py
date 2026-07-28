"""
Wrapper minimale per chiamare Ollama in locale (Blocco A).

Assume un server Ollama gia' in esecuzione (locale, o su un nodo HPC via
job PBS con `ollama serve` in background), raggiungibile su OLLAMA_HOST
(default http://localhost:11434). Usa lo JSON Schema di
config/extraction_schema.json come `format`: la generazione viene
vincolata a quello schema, il JSON malformato diventa strutturalmente
impossibile - niente retry-loop complesso sul parsing, solo una
validazione difensiva a valle (vedi lmm_extractor.py).
"""

import os

import ollama

MODELLO = os.environ.get("OLLAMA_MODEL", "qwen2.5vl:7b")
HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
# Senza num_ctx esplicito il runtime usa il default del modello (fino a
# 128000+ token): il KV-cache/compute-buffer risultante non ci sta su una
# singola A100 da 40GB e Ollama retrocede a girare su CPU (lentissimo, ~5
# minuti a chiamata prima di andare in timeout). Il nostro input reale
# (fino a 10 immagini + testo Wikipedia/CFR/CISA + output JSON) sta
# comodamente sotto questa soglia.
NUM_CTX = int(os.environ.get("OLLAMA_NUM_CTX", 65536))

_client = ollama.Client(host=HOST)


def modello_disponibile(modello: str = MODELLO) -> bool:
    """Controlla se il modello e' gia' scaricato (evita un pull silenzioso e
    lungo a meta' di una pipeline di centinaia di chiamate)."""
    disponibili = [m["model"] for m in _client.list()["models"]]
    return modello in disponibili or f"{modello}:latest" in disponibili


def estrai(prompt: str, immagini: list, schema: dict, modello: str = MODELLO) -> str:
    """Una singola chiamata di estrazione.

    Ritorna la stringa JSON grezza prodotta dal modello (gia' vincolata
    alla forma dello schema da Ollama, ma va comunque validata a valle -
    vedi lmm_extractor.py per la validazione difensiva + retry).
    """
    messaggio = {"role": "user", "content": prompt}
    if immagini:
        messaggio["images"] = immagini

    risposta = _client.chat(
        model=modello,
        messages=[messaggio],
        format=schema,
        options={"temperature": 0, "num_ctx": NUM_CTX},
    )
    return risposta["message"]["content"]


if __name__ == "__main__":
    # Sanity check di connessione: python ollama_client.py
    try:
        modelli = [m["model"] for m in _client.list()["models"]]
        print(f"Connesso a Ollama su {HOST}. Modelli disponibili: {modelli}")
        print(f"Modello di estrazione ({MODELLO}) disponibile: {modello_disponibile()}")
    except Exception as e:
        print(f"Impossibile connettersi a Ollama su {HOST}: {e}")
        print("Serve un server Ollama in esecuzione (`ollama serve`).")
