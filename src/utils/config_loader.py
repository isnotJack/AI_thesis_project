"""
Funzioni di caricamento della configurazione del progetto.

Tutti gli altri moduli (extraction, graph, simulation) devono importare
la lista dei paesi da qui, MAI ridefinirla localmente. Cosi' se cambi
config/countries.yaml, tutto il resto si aggiorna automaticamente.
"""
import json
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def load_countries() -> list[dict]:
    """Carica la lista dei paesi da config/countries.yaml.

    Returns:
        Lista di dizionari, uno per paese, con chiavi:
        nome, iso3, gruppo, tag, note.
    """
    with open(CONFIG_DIR / "countries.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg["paesi"]


def load_period_range() -> dict:
    """Ritorna il periodo di riferimento del progetto (inizio/fine/granularita)."""
    with open(CONFIG_DIR / "countries.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg["periodo"]


def load_extraction_schema() -> dict:
    """Carica lo schema JSON di riferimento per il Blocco A."""
    with open(CONFIG_DIR / "extraction_schema.json", encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    # Sanity check rapido: esegui `python config_loader.py` per verificare
    # che il file di configurazione sia leggibile e ben formato.
    paesi = load_countries()
    print(f"Caricati {len(paesi)} paesi:")
    for p in paesi:
        print(f"  - {p['nome']} ({p['iso3']}) - gruppo {p['gruppo']} - {p['tag']}")
