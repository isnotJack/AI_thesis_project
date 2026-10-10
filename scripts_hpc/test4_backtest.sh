#!/bin/bash
# Launcher del TEST 4 (backtest su eventi reali del 2025) su Leonardo.
#
# Un solo job, in quest'ordine:
#   0. controllo di contaminazione: ogni modello dice che cosa sa dei due eventi;
#   1. per ogni ripetizione k = 1..RIPETIZIONI (seed k): i 2 scenari del backtest con
#      i 3 modelli, poi dialoghi, giudice standard, giudice con la verita' e report;
#   2. confronto deterministico con la realta' su tutte le ripetizioni.
# Ogni ripetizione e' completa prima di passare alla successiva: se il walltime
# scade, le ripetizioni gia' chiuse sono utilizzabili. Resumable: rilanciando, tutto
# cio' che e' gia' stato salvato viene saltato.
#
# Uso a mano dentro una sessione interattiva (dalla root del progetto):
#   bash scripts_hpc/test4_backtest.sh
# Parametri personalizzabili, es.:  RIPETIZIONI=1 bash scripts_hpc/test4_backtest.sh
set -u

MODELLI="${MODELLI:-llama3.3:70b qwen2.5:72b nemotron:70b}"   # gli stessi dei test 2 e 3
JUDGE="${JUDGE:-command-r}"                                   # giudice del test 3 (Cohere)
ROUND="${ROUND:-10}"
RIPETIZIONI="${RIPETIZIONI:-3}"
PREFISSO="${PREFISSO:-test4_backtest}"
PORT="${PORT:-11434}"
HOST="http://127.0.0.1:${PORT}"

module load ollama/0.12.11 2>/dev/null || true   # versione usata nei test precedenti
module load proxy 2>/dev/null || true            # serve per 'ollama pull' e per pip

source .venv/bin/activate 2>/dev/null || true
python3 -m pip install -q -r requirements.txt 2>/dev/null || true

export OLLAMA_HOST="127.0.0.1:${PORT}"
export OLLAMA_FLASH_ATTENTION=1
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

echo "== $(date '+%F %T') avvio ollama serve (porta ${PORT}) =="
ollama serve > scripts_hpc/log_ollama_test4.log 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null' EXIT
for i in $(seq 1 60); do
  curl -s "${HOST}/api/tags" >/dev/null 2>&1 && break
  sleep 2
done

for M in $MODELLI $JUDGE; do
  echo "== pull $M =="
  ollama pull "$M" || echo "  (pull fallito: procedo, forse gia' presente)"
done

echo "== $(date '+%F %T') 0. controllo di contaminazione =="
for M in $MODELLI; do
  python3 -m src.simulation.contaminazione --modello "$M" --host "$HOST"
done

for K in $(seq 1 "$RIPETIZIONI"); do
  TEST="${PREFISSO}_r${K}"
  echo "== $(date '+%F %T') 1.${K} ripetizione ${K}/${RIPETIZIONI}: ${TEST} (seed ${K}) =="
  for M in $MODELLI; do
    python3 -m src.simulation.run_simulazione --modello "$M" --host "$HOST" \
        --backtest --test "$TEST" --seed "$K" --round "$ROUND"
  done
  python3 -m src.simulation.dialogo --test "$TEST" || true
  python3 -m src.simulation.judge --test "$TEST" --giudice "$JUDGE" --host "$HOST" || true
  python3 -m src.simulation.judge_realta --test "$TEST" --giudice "$JUDGE" --host "$HOST" || true
  python3 -m src.simulation.report_giudizi --test "$TEST" || true
done

echo "== $(date '+%F %T') 2. confronto con la realta' =="
python3 -m src.simulation.confronto_realta --prefisso "$PREFISSO" || true

echo "== $(date '+%F %T') FATTO. simulazioni: data/processed/simulazioni/${PREFISSO}_r*/ | giudizi: data/processed/giudizi/${PREFISSO}_r*/ | contaminazione e confronto: data/processed/backtest/ =="
