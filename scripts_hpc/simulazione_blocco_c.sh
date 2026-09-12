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

MODELLI="${MODELLI:-llama3.3:70b qwen2.5:72b nemotron:70b}"   # stessa fascia (~70B), famiglie diverse
ROUND="${ROUND:-10}"                                          # round aumentati
TEST="${TEST:-test3_tag_kb}"                                  # etichetta dell'esperimento (con tag base_kb)
JUDGE="${JUDGE:-command-r}"                                   # modello giudice (Cohere: famiglia diversa)
PORT="${PORT:-11434}"

# moduli (guardati: se lanciato in una shell senza 'module' non fallisce)
module load ollama/0.12.11 2>/dev/null || true   # versione testata nel Blocco A
module load proxy 2>/dev/null || true            # serve per 'ollama pull' e per pip

# Il job PBS gira in una shell nuova: attiva qui il virtualenv del progetto
# (dove stanno networkx, ollama-python, jsonschema, ...) e allinea le dipendenze.
# Eseguito da PBS_O_WORKDIR (= root del progetto), quindi il path relativo va bene.
source .venv/bin/activate 2>/dev/null || true
python3 -m pip install -q -r requirements.txt 2>/dev/null || true

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
  echo "== esecuzione scenari con $M (round=$ROUND, test=$TEST) =="
  python3 -m src.simulation.run_simulazione --modello "$M" --host "http://127.0.0.1:${PORT}" \
      --round "$ROUND" --test "$TEST"
done

echo "== genero i dialoghi affiancati (confronto del ragionamento tra modelli) =="
python3 -m src.simulation.dialogo --test "$TEST" || true

echo "== JUDGE: scarico il modello giudice ($JUDGE) e valuto tutti i dialoghi =="
ollama pull "$JUDGE" || echo "  (pull del giudice fallito: procedo, forse gia' presente)"
python3 -m src.simulation.judge --test "$TEST" --giudice "$JUDGE" --host "http://127.0.0.1:${PORT}" || true

echo "== genero il report grafico dei giudizi =="
python3 -m src.simulation.report_giudizi --test "$TEST" || true

echo "== FATTO. simulazioni: data/processed/simulazioni/$TEST/ | giudizi+report: data/processed/giudizi/$TEST/ =="
