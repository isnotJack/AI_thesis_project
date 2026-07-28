#!/bin/bash
# Estrazione LMM del Blocco A in parallelo su N GPU (default 4).
#
# Avvia un server Ollama per GPU (ognuno pinnato con CUDA_VISIBLE_DEVICES,
# su una porta diversa) e un worker Python per server: ogni worker estrae
# la sua fetta [i::N] delle combinazioni (paese, trimestre). Cosi' le 4
# A100 lavorano in parallelo.
#
# Resumable: le combinazioni gia' estratte vengono saltate (scrittura
# atomica -> nessun file troncato anche se fermi il job a meta'). Puoi
# fermare e rilanciare quando vuoi, riprende da dove era.
#
# Uso (dentro una sessione interattiva o da PBS):
#   NGPU=4 bash scripts_hpc/estrazione_parallela.sh
#
# Log per GPU in scripts_hpc/log_ollama_<i>.log e log_worker_<i>.log.

set -e
cd "${PBS_O_WORKDIR:-$HOME/AI_thesis_project}"

module load proxy 2>/dev/null || true
module load ollama/0.12.11
source .venv/bin/activate

NGPU=${NGPU:-4}
MODELLO=${OLLAMA_MODEL:-qwen2.5vl:32b}
export OLLAMA_FLASH_ATTENTION=1

echo "Avvio $NGPU server Ollama (modello $MODELLO)..."
SERVER_PIDS=()
for i in $(seq 0 $((NGPU - 1))); do
    PORT=$((11434 + i))
    CUDA_VISIBLE_DEVICES=$i OLLAMA_HOST=127.0.0.1:$PORT \
        ollama serve > "scripts_hpc/log_ollama_$i.log" 2>&1 &
    SERVER_PIDS+=($!)
done
sleep 8

# Scarica il modello una volta sola (lo store ~/.ollama/models e' condiviso)
OLLAMA_HOST=127.0.0.1:11434 ollama pull "$MODELLO"

echo "Avvio $NGPU worker..."
WORKER_PIDS=()
for i in $(seq 0 $((NGPU - 1))); do
    PORT=$((11434 + i))
    OLLAMA_HOST=127.0.0.1:$PORT OLLAMA_MODEL="$MODELLO" \
        python3 -m src.extraction.lmm_extractor --worker "$i" --nworker "$NGPU" \
        > "scripts_hpc/log_worker_$i.log" 2>&1 &
    WORKER_PIDS+=($!)
done

# Aspetta che tutti i worker finiscano
STATO=0
for p in "${WORKER_PIDS[@]}"; do
    wait "$p" || STATO=1
done

# Spegni i server
for p in "${SERVER_PIDS[@]}"; do
    kill "$p" 2>/dev/null || true
done

echo "Estrazione parallela completata (exit $STATO). Vedi scripts_hpc/log_worker_*.log"
exit $STATO
