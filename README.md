# Tesi: Estrazione di Informazioni da Fonti Non Strutturate e Modellazione a Grafo per l'Analisi del Rischio Geopolitico-Cyber

Pipeline completa che (A) estrae informazione strutturata da fonti eterogenee e non
strutturate con un modello multimodale, (B) la trasforma in un grafo di relazioni tra
Paesi con una mappa interattiva, e (C) usa quel grafo per una simulazione ad agenti
"OASIS-inspired" in cui ogni Paese è un agente LLM che reagisce agli eventi.

**Domanda di ricerca:** l'instabilità geopolitica ed economica di un Paese è correlata,
o precede temporalmente, un aumento della sua esposizione a rischio cyber (come vittima)
o della sua attività cyber offensiva (come attore)?

**Perimetro:** 17 Paesi in 4 gruppi (fonte di verità `config/countries.yaml`) —
attori cyber (RUS, CHN, PRK, IRN) · alta instabilità (UKR, SDN, SSD, YEM, SYR, ETH, VEN) ·
bersagli cyber (USA, ISR, KOR, SAU) · casi di controllo (ITA, EST). Periodo 2018-Q1 → 2024-Q4
(granularità trimestrale) → 476 profili (paese × trimestre).

## Stato dei blocchi

| Blocco | Stato | Contenuto |
|---|---|---|
| **A — Estrazione con LMM** | Completato | Profili JSON per (paese, trimestre) estratti da PDF/CSV/testi con `qwen2.5vl:32b` (Ollama, su HPC). |
| **B — Grafo statico + mappa** | Completato | Nodi = Paesi (qualitativo dall'LLM + numerico dai CSV); archi = cyber / migrazione / coinvolgimento militare; mappa interattiva. |
| **C — Simulazione "OASIS-inspired"** | Completato | Ogni Paese è un agente LLM: un evento si propaga sul grafo, gli agenti aggiornano stato e relazioni. 7 scenari × 3 modelli aperti (su HPC). |

## Cosa guardare (deliverable principali)

- **Mappa interattiva del grafo** → `data/processed/graphs/grafo_mappa.html`
  (planisfero: 17 Paesi evidenziati, layer cyber/migrazione/militare accendibili, slider
  temporale, tema chiaro/scuro, zoom). Si apre nel browser, è autosufficiente.
- **Mappe delle simulazioni** → `data/processed/simulazioni/<scenario>/<modello>/mappa.html`
  (slider dei round, spessore = intensità, archi creati/tagliati, pop-up sui cambi di stato).
- **Log dettagliato delle decisioni progettuali** → `docs/decisioni_progetto.md`
  (il "diario di bordo": tutte le scelte, i problemi e le soluzioni, blocco per blocco —
  è il materiale per scrivere la sezione metodologica della tesi).

## Struttura delle cartelle

```
thesis_project/
├── config/
│   ├── countries.yaml            # 17 Paesi + gruppi + periodo (fonte di verità)
│   └── extraction_schema.json    # Schema JSON che l'LMM deve produrre
│
├── data/
│   ├── raw/                      # Fonti grezze, MAI modificate a mano
│   │   ├── acled/<ISO3>/              # Conflitto (eventi violenti, vittime)
│   │   ├── fews_net/, acaps/          # Carestia / sicurezza alimentare
│   │   ├── unhcr/<ISO3>/              # Migrazione (rifugiati, sfollati)
│   │   ├── worldbank/<ISO3>/          # Economia (povertà, MPO)
│   │   ├── cyber_advisories/, cisa/, enisa/, microsoft_mddr/, eurepoc/  # Cyber
│   │   └── wikipedia/<ISO3>/          # Contesto generale
│   │
│   └── processed/
│       ├── extracted_json/<ISO3>/     # Blocco A: 476 profili qualitativi (LLM)
│       ├── nodi/<ISO3>/               # Blocco B: profili arricchiti (LLM + numeri CSV)
│       ├── graphs/                    # Blocco B: grafo.pickle, archi.csv, grafo_mappa.html
│       └── simulazioni/<scenario>/<modello>/   # Blocco C: risultato.json + mappa.html
│
├── notebooks/
│   ├── 01_data_collection.ipynb
│   ├── 02_extraction_lmm.ipynb
│   ├── 03_graph_construction.ipynb   # costruzione grafo + mappa
│   └── 04_oasis_simulation.ipynb     # cruscotto simulazione + confronto tra modelli
│
├── src/
│   ├── extraction/     # Blocco A: ollama_client, pdf_to_images, prompt_builder, lmm_extractor
│   ├── graph/          # Blocco B: build_nodes, build_edges, build_graph, build_map, eurepoc
│   ├── simulation/     # Blocco C: schemi, ambiente, stato_agente, oasis_inspired, scenari,
│   │                   #           mappa_sim, run_simulazione
│   └── utils/          # supporto (config_loader)
│
├── scripts_hpc/        # Job per Leonardo (PBS): estrazione (A) e simulazione (C)
├── docs/               # decisioni_progetto.md + documento di progetto + paper OASIS
└── requirements.txt
```

## Come riprodurre

Setup: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`

**Blocco A — estrazione (HPC, Ollama + `qwen2.5vl:32b`)**
```bash
qsub scripts_hpc/estrazione_blocco_a.pbs        # -> data/processed/extracted_json/
```

**Blocco B — grafo + mappa (in locale)**
```bash
python -m src.graph.build_nodes    # arricchisce i nodi (LLM + numeri CSV) -> data/processed/nodi/
python -m src.graph.build_graph    # costruisce il grafo -> graphs/grafo.pickle + archi.csv
python -m src.graph.build_map      # genera la mappa interattiva -> graphs/grafo_mappa.html
```
(oppure esegui `notebooks/03_graph_construction.ipynb`). Fonte cyber principale per gli
archi: **EuRepoC** (dati datati 2018-2024) in unione con CFR — vedi `src/graph/eurepoc.py`.

**Blocco C — simulazione (HPC, 3 modelli aperti via Ollama)**
```bash
qsub scripts_hpc/simulazione_blocco_c.pbs       # 7 scenari × qwen2.5:32b, llama3.3:70b, gemma2:27b
```
Prova locale senza HPC (reazioni finte): `python -m src.simulation.run_simulazione --mock`.
Per esplorare/confrontare i risultati: `notebooks/04_oasis_simulation.ipynb`.

## Convenzioni

1. **`data/raw/` è intoccabile**: ogni trasformazione produce file nuovi in `data/processed/`.
2. **`countries.yaml` è l'unica fonte di verità** per la lista dei Paesi (mai hardcodare).
3. **Numeri solo dai CSV, qualitativo solo dall'LLM**: i due livelli restano affiancati nei
   nodi; gli archi del grafo vengono da dati strutturati (zero LLM), l'LLM alimenta i nodi
   (e quindi gli agenti del Blocco C).
4. Le simulazioni girano su una **copia** del grafo: i dati reali non vengono mai modificati.

## Sintesi dei risultati (Blocco C, primo giro)

Coerenza di formato perfetta (0 valori fuori vocabolario) e catene di propagazione
plausibili. Confronto tra modelli: **`llama3.3:70b` nettamente il migliore** (catene lunghe
e coerenti), mentre i modelli più piccoli reagiscono ma propagano poco — la ricchezza della
simulazione cresce con la dimensione del modello. Dettagli in `docs/decisioni_progetto.md`.
