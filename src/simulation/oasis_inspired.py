"""
Modulo di simulazione "OASIS-inspired" (Blocco C).

Da implementare dopo l'accesso a Leonardo (HPC), quando Blocco A e B saranno
completi. Architettura di riferimento (vedi documento di progetto sez. 4.4):

1. Il grafo (Environment Server alleggerito): si riusa il grafo del Blocco B,
   nessun database relazionale.
2. L'agente (Agent Module semplificato, RecSys implicito nei vicini di grafo):
   prompt -> risposta JSON -> parsing con retry.
3. Il ciclo (sostituisce Time Engine e Scalable Inferencer): round discreti
   e sincroni su un ciclo Python (eventualmente asyncio se serve concorrenza).

Placeholder: non ancora implementato, fuori scope fino a nuovo accesso HPC.
"""

# TODO: def crea_prompt_agente(nome_paese, profilo, evento_ricevuto, relazione) -> str: ...
# TODO: def chiama_llm_e_parsa(prompt: str) -> dict: ...
# TODO: def simula(G, evento_iniziale: dict, n_round: int = 5) -> tuple: ...
