# Script HPC (Leonardo / DaVinci-1)

Il cluster usa PBS Pro (non SLURM), job GPU via `qsub -q gpu`.

- `estrazione_blocco_a.pbs` — job batch per l'estrazione LMM (Blocco A):
  avvia Ollama sul nodo GPU assegnato, scarica Qwen2.5-VL:7b se serve,
  esegue `src/extraction/lmm_extractor.py` su tutte le 476 combinazioni
  (paese, trimestre). Resumable - rilanciare lo stesso comando salta le
  combinazioni gia' estratte. Vedi commento in testa al file per l'uso.
  Usa `module load ollama/0.12.11` fisso: le versioni >=0.13.x rompono
  Qwen2.5-VL su CUDA (https://github.com/ollama/ollama/issues/13630).

Ancora da scrivere quando serviranno: job batch per la simulazione del
Blocco C (dopo che Blocco A e B saranno completi).
