# Script HPC (Leonardo / DaVinci-1)

Il cluster usa PBS Pro (non SLURM), job GPU via `qsub -q gpu`.

- `estrazione_parallela.sh` — launcher dell'estrazione LMM (Blocco A) in
  parallelo su N GPU (default 4): un server Ollama per GPU (pinnato con
  CUDA_VISIBLE_DEVICES, su porte 11434+i) + un worker Python per server,
  ognuno estrae la fetta `[i::N]` delle 476 combinazioni (paese,
  trimestre). Modello: qwen2.5vl:32b. Si puo' lanciare a mano dentro una
  sessione interattiva:  `NGPU=4 bash scripts_hpc/estrazione_parallela.sh`.
  Resumable + scrittura atomica: fermabile e ri-lanciabile su piu' giorni,
  riprende da dove era senza file corrotti.
- `estrazione_blocco_a.pbs` — wrapper PBS che richiede 4 GPU e chiama il
  launcher sopra. Uso:  `qsub scripts_hpc/estrazione_blocco_a.pbs`.
  Usa `module load ollama/0.12.11` fisso: le versioni >=0.13.x rompono
  Qwen2.5-VL su CUDA (https://github.com/ollama/ollama/issues/13630), e
  `module load proxy` per far raggiungere il registry a `ollama pull`.

Modalita' utili di `python3 -m src.extraction.lmm_extractor`:
  `--paese SDN`            un solo paese, tutti i trimestri
  `--paese SDN --periodo 2023-Q2`   una sola combinazione (forza)
  `--worker i --nworker N` la fetta [i::N] (usata dal launcher parallelo)
  (nessun argomento)       tutte le 476 combinazioni, sequenziale

Ancora da scrivere quando serviranno: job batch per la simulazione del
Blocco C (dopo che Blocco A e B saranno completi).
