#!/bin/bash
# Job di SOLI GIUDICI per il test 4 (le simulazioni sono gia' fatte e non si toccano).
#
# Rifa' i giudizi delle ripetizioni test4_backtest_r1..r3 con il metodo A BLOCCHI (i
# primi giudizi erano troncati: dialoghi fino a 85 mila token contro una finestra di
# 32.768), con due giudici della stessa famiglia (Cohere), uno dopo l'altro:
#   - command-r       (35B): lo stesso del test 3, per confronto;
#   - command-r-plus (104B): il giudice piu' forte.
# Per ogni giudice e ripetizione: giudice standard, giudice con la verita', report.
# Alla fine: confronto con la realta' (deterministico) con i punteggi di entrambi.
#
# Ripartibile: si salta solo un giudizio gia' fatto con il metodo a blocchi; quelli
# troncati della prima run vengono rifatti senza bisogno di --forza.
#
# Uso a mano (dalla root del progetto, dentro una sessione su nodo GPU):
#   bash scripts_hpc/test4_giudici.sh
# Un solo giudice:  GIUDICI="command-r-plus" bash scripts_hpc/test4_giudici.sh
set -u

GIUDICI="${GIUDICI:-command-r command-r-plus}"
RIPETIZIONI="${RIPETIZIONI:-3}"
PREFISSO="${PREFISSO:-test4_backtest}"
PORT="${PORT:-11434}"
HOST="http://127.0.0.1:${PORT}"

module load ollama/0.12.11 2>/dev/null || true
module load proxy 2>/dev/null || true
source .venv/bin/activate 2>/dev/null || true
python3 -m pip install -q -r requirements.txt 2>/dev/null || true

export OLLAMA_HOST="127.0.0.1:${PORT}"
export OLLAMA_FLASH_ATTENTION=1
echo "== risorse: NCPUS=${NCPUS:-?} CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-non impostata} =="
nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv 2>/dev/null || true

echo "== $(date '+%F %T') avvio ollama serve (porta ${PORT}) =="
ollama serve > scripts_hpc/log_ollama_giudici.log 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null' EXIT
for i in $(seq 1 60); do
  curl -s "${HOST}/api/tags" >/dev/null 2>&1 && break
  sleep 2
done

for G in $GIUDICI; do
  echo "== $(date '+%F %T') pull $G =="
  ollama pull "$G" || echo "  (pull fallito: controllo se e' gia' presente)"
  if ! ollama show "$G" >/dev/null 2>&1; then
    echo "== [ERRORE] giudice $G non disponibile (download non riuscito?): lo salto =="
    continue
  fi
  for K in $(seq 1 "$RIPETIZIONI"); do
    TEST="${PREFISSO}_r${K}"
    echo "== $(date '+%F %T') giudice $G, ripetizione ${K}/${RIPETIZIONI}: ${TEST} =="
    python3 -m src.simulation.judge --test "$TEST" --giudice "$G" --host "$HOST" || true
    python3 -m src.simulation.judge_realta --test "$TEST" --giudice "$G" --host "$HOST" || true
    python3 -m src.simulation.report_giudizi --test "$TEST" --giudice "$G" || true
  done
done

echo "== $(date '+%F %T') confronto con la realta' (con i punteggi di tutti i giudici) =="
python3 -m src.simulation.confronto_realta --prefisso "$PREFISSO" || true

echo "== $(date '+%F %T') FATTO. giudizi: data/processed/giudizi/${PREFISSO}_r*/ | confronto: data/processed/backtest/ =="
