"""
Modulo di estrazione dati tramite LMM (Blocco A).

Da implementare quando si passa dalla raccolta dati all'estrazione:
- funzione per costruire il prompt (usa config/extraction_schema.json come contratto)
- funzione per chiamare il modello (Gemini 2.0 Flash o alternativa) passando
  testo + eventuali immagini/pagine PDF renderizzate
- funzione di parsing/validazione del JSON restituito, con retry in caso di
  output malformato (criticita' nota, vedi documento di progetto sez. 4.7)

Placeholder: non ancora implementato. Al momento il progetto e' in fase di
raccolta dati grezzi (vedi notebooks/01_data_collection.ipynb).
"""

# TODO: def build_prompt(paese: str, periodo: str, documenti: list) -> str: ...
# TODO: def call_lmm(prompt: str, immagini: list = None) -> str: ...
# TODO: def parse_and_validate(risposta_raw: str, schema: dict) -> dict: ...
