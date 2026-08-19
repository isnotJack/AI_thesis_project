#!/bin/bash
# Launcher della simulazione Blocco C (OASIS-inspired) su Leonardo.
#
# Avvia UN server Ollama (1 GPU basta: i modelli girano in sequenza), scarica i
# 3 modelli aperti e per ognuno esegue tutti gli scenari, salvando in
# data/processed/simulazioni/<scenario>/<modello>/. Resumable: rilanciando,
# salta le run gia' fatte.
#
# Uso a mano dentro una sessione interattiva (dalla root del progetto):
#   bash scripts_hpc/simulazione_blocco_c.sh
# Modelli personalizzabili:
#   MODELLI="qwen2.5:32b gemma2:27b" bash scripts_hpc/simulazione_blocco_c.sh
set -u

MODELLI="${MODELLI:-qwen2.5:32b llama3.3:70b gemma2:27b}"
PORT="${PORT:-11434}"

# moduli (guardati: se lanciato in una shell senza 'module' non fallisce)
module load ollama/0.12.11 2>/dev/null || true   # versione testata nel Blocco A
module load proxy 2>/dev/null || true            # serve solo per 'ollama pull'

export OLLAMA_HOST="127.0.0.1:${PORT}"
export OLLAMA_FLASH_ATTENTION=1
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

echo "== avvio ollama serve (porta ${PORT}) =="
ollama serve > scripts_hpc/log_ollama_sim.log 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null' EXIT

# attende che il server risponda
for i in $(seq 1 60); do
  curl -s "http://127.0.0.1:${PORT}/api/tags" >/dev/null 2>&1 && break
  sleep 2
done

for M in $MODELLI; do
  echo "== pull $M =="
  ollama pull "$M" || echo "  (pull fallito: procedo, forse gia' presente)"
  echo "== esecuzione scenari con $M =="
  python3 -m src.simulation.run_simulazione --modello "$M" --host "http://127.0.0.1:${PORT}"
done

echo "== fatto. risultati in data/processed/simulazioni/ =="
