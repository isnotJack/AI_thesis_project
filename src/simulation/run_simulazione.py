"""
Blocco C - esecutore della simulazione (CLI).

Esegue uno o piu' scenari con UN modello e salva, per ogni (scenario, modello):
    data/processed/simulazioni/<scenario>/<modello>/
        risultato.json   (traccia completa: storico + snapshot + stati finali)
        mappa.html       (mappa-simulazione interattiva)

Resumable: salta le run gia' presenti (a meno di --forza).

Uso tipico:
    # su HPC, con un server Ollama attivo:
    python3 -m src.simulation.run_simulazione --modello qwen2.5:32b --host http://127.0.0.1:11434
    # un solo scenario:
    python3 -m src.simulation.run_simulazione --modello gemma2:27b --scenario siccita_darfur
    # prova in locale SENZA modello (reazioni finte, per validare la pipeline):
    python3 -m src.simulation.run_simulazione --mock

Helper (usati dal notebook 04): carica(), modelli_disponibili(), riepilogo().
"""

import argparse
import json
from pathlib import Path

from src.simulation.mappa_sim import genera
from src.simulation.oasis_inspired import responder_mock, responder_ollama, simula
from src.simulation.scenari import SCENARI

BASE = Path(__file__).resolve().parents[2]
OUT = BASE / "data" / "processed" / "simulazioni"
MODELLI_DEFAULT = ["qwen2.5:32b", "llama3.3:70b", "gemma2:27b"]


def _safe(m: str) -> str:
    return m.replace(":", "_").replace("/", "_")


def esegui(scenario: str, modello: str, responder, n_round: int = 5, forza: bool = False):
    d = OUT / scenario / _safe(modello)
    fjson = d / "risultato.json"
    if fjson.exists() and not forza:
        print(f"[skip] {scenario} / {modello} (gia' fatto)")
        return
    print(f"[run ] {scenario} / {modello} ...")
    res = simula(SCENARI[scenario], responder, n_round=n_round, verbose=True)
    res["modello"] = modello
    res["scenario"] = scenario
    d.mkdir(parents=True, exist_ok=True)
    fjson.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    genera(res, titolo=f"{scenario} · {modello}", out_path=d / "mappa.html")
    print(f"[ok  ] {scenario} / {modello} -> {d}")


# --------------------------------------------------------------------------- #
# Helper per il notebook / il confronto
# --------------------------------------------------------------------------- #
def carica(scenario: str, modello: str) -> dict:
    f = OUT / scenario / _safe(modello) / "risultato.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def modelli_disponibili(scenario: str) -> list:
    d = OUT / scenario
    return sorted(p.name for p in d.iterdir() if (p / "risultato.json").exists()) if d.exists() else []


def scenari_disponibili() -> list:
    return sorted(p.name for p in OUT.iterdir() if p.is_dir()) if OUT.exists() else []


def riepilogo(res: dict) -> dict:
    """Statistiche di sintesi di una run (per la tabella di confronto)."""
    creati = tagliati = rafforzati = indeboliti = stato = 0
    for s in res["snapshots"]:
        for c in s.get("cambi_archi", []):
            op = c.get("op")
            creati += op == "crea"; tagliati += op == "taglia"
            rafforzati += op == "rafforza"; indeboliti += op == "indebolisci"
        stato += len(s.get("cambi_stato", []))
    paesi = {h["paese"] for h in res["storico"] if "reazione" in h}
    return {"round": len(res["snapshots"]) - 1, "paesi_reagito": len(paesi),
            "archi_creati": creati, "archi_tagliati": tagliati,
            "archi_rafforzati": rafforzati, "archi_indeboliti": indeboliti,
            "cambi_stato": stato}


def main():
    ap = argparse.ArgumentParser(description="Esegue la simulazione Blocco C.")
    ap.add_argument("--modello", default=None, help="tag Ollama del modello (es. qwen2.5:32b)")
    ap.add_argument("--scenario", default=None, help="uno scenario; se assente, tutti")
    ap.add_argument("--host", default=None, help="host del server Ollama (es. http://127.0.0.1:11434)")
    ap.add_argument("--round", type=int, default=5)
    ap.add_argument("--forza", action="store_true", help="ri-esegue anche se gia' presente")
    ap.add_argument("--mock", action="store_true", help="usa reazioni finte (nessun modello)")
    a = ap.parse_args()

    if a.mock:
        modello, responder = "mock", responder_mock
    else:
        if not a.modello:
            ap.error("specificare --modello (oppure --mock)")
        modello, responder = a.modello, responder_ollama(a.modello, host=a.host)

    scenari = [a.scenario] if a.scenario else list(SCENARI)
    for s in scenari:
        esegui(s, modello, responder, n_round=a.round, forza=a.forza)
    print(f"\nFatto. Output in {OUT}/")


if __name__ == "__main__":
    main()
