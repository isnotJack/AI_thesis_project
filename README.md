# Tesi: Estrazione di Informazioni da Fonti Non Strutturate e Modellazione a Grafo per l'Analisi del Rischio Geopolitico-Cyber

Questo repository/cartella e' la struttura di lavoro ufficiale del progetto. Contiene sia i dati grezzi che il codice, organizzati per riflettere i blocchi del progetto.

> **Stato attuale del progetto (aggiornare questa riga man mano che si avanza):**
> Fase: raccolta dati grezzi — Blocco A, prima dimensione (instabilita'/conflitti).

## Struttura dei blocchi

Il progetto e' organizzato in blocchi. **Il Blocco D e' fuori scope per ora** e non ha una cartella dedicata: se in futuro verra' ripreso, verra' aggiunto separatamente.

| Blocco | Stato | Contenuto |
|---|---|---|
| A — Data Extraction con LMM | **In corso** | Raccolta documenti grezzi + estrazione JSON strutturata |
| B — Costruzione del Grafo Statico | Da iniziare | Nodi = Paesi, archi = relazioni (migrazione, diplomatico, cyber) |
| C — Simulazione "OASIS-inspired" | Da iniziare (richiede HPC) | Agenti LLM sui nodi del grafo, propagazione di eventi |

## Struttura delle cartelle

```
thesis_project/
├── config/
│   ├── countries.yaml          # Lista ufficiale dei paesi + periodo temporale (fonte di verita')
│   └── extraction_schema.json  # Schema JSON che l'LMM deve produrre per ogni (paese, periodo)
│
├── data/
│   ├── raw/                    # Documenti grezzi scaricati, MAI modificati a mano
│   │   ├── acled/<ISO3>/            # Instabilita'/conflitti
│   │   ├── fews_net/<ISO3>/         # Carestia/siccita'
│   │   ├── unhcr/<ISO3>/            # Migrazione
│   │   ├── worldbank/<ISO3>/        # Economia/poverta'
│   │   ├── cyber_advisories/<ISO3>/ # CISA, ENISA
│   │   └── wikipedia/<ISO3>/        # Contesto generale
│   │
│   └── processed/
│       ├── extracted_json/<ISO3>/  # Output del Blocco A: un JSON per (paese, periodo)
│       └── graphs/                 # Output del Blocco B: grafo serializzato (.pkl / .graphml)
│
├── notebooks/                  # Notebook Python, uno per fase della pipeline
│   ├── 01_data_collection.ipynb
│   ├── 02_extraction_lmm.ipynb
│   ├── 03_graph_construction.ipynb
│   └── 04_oasis_simulation.ipynb   # Blocco C, da avviare dopo accesso HPC
│
├── src/                         # Codice riutilizzabile richiamato dai notebook
│   ├── extraction/              # Prompt, chiamate LMM, parsing/validazione JSON
│   ├── graph/                   # Costruzione nodi/archi
│   ├── simulation/              # Ciclo agente-grafo del Blocco C
│   └── utils/                   # Funzioni di supporto (I/O, logging, retry)
│
├── outputs/                     # Risultati finali da citare in tesi
│   ├── graphs/                  # Versioni finali del grafo
│   ├── simulations/             # Log/storico delle simulazioni (Blocco C)
│   └── figures/                 # Grafici/immagini per la tesi
│
├── scripts_hpc/                 # 
│
├── docs/                        # Documentazione del progetto (note, decisioni prese, verbali col tutor)
│
└── requirements.txt
```

## Convenzioni importanti (da rispettare fin da subito)

1. **Naming dei file grezzi**: dentro ogni `data/raw/<fonte>/<ISO3>/`, salva i file con nome
   `<ISO3>_<periodo>_<descrizione-breve>.<ext>`, es. `SDN_2018-Q2_fewsnet-report.pdf`.
   Se un documento copre piu' periodi o non ha una data precisa (es. una pagina Wikipedia),
   usa `SDN_generico_wikipedia.html`.

2. **Non modificare mai `data/raw/`**: e' lo storico grezzo, deve restare intatto e riproducibile.
   Ogni trasformazione (pulizia, estrazione) produce file nuovi in `data/processed/`.

3. **Manifest**: ogni file scaricato va registrato in `data/manifest.csv` (vedi sotto). Non e'
   burocrazia inutile: e' quello che ti permette di scrivere la sezione "raccolta dati" della tesi
   senza doverti ricordare a memoria da dove viene ogni cosa, e ti fa vedere subito dove hai buchi
   di copertura (es. "Etiopia non ha FEWS NET per il 2021").

4. **`countries.yaml` e' l'unica fonte di verita'** per la lista paesi. Se cambi la lista, cambi
   solo li'; il codice deve sempre leggere da quel file, mai avere paesi hardcodati.

## Prossimi passi immediati (weekend)

- [ ] Registrarsi su ACLED (Access Portal), accettare i termini, generare la access key
- [ ] Scaricare per ogni paese l'export CSV ACLED 2018-2024 in `data/raw/acled/<ISO3>/`
- [ ] Scaricare i report PDF ACLED (mappe/grafici di intensita') dove disponibili
- [ ] Aggiornare `data/manifest.csv` per ogni file scaricato
- [ ] Segnalare eventuali paesi/periodi con copertura scarsa
