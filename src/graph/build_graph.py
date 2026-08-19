"""
Blocco B (parte 2) - assemblaggio e serializzazione del grafo.

Costruisce un nx.MultiDiGraph:
- NODI core: i 17 paesi del progetto, ognuno con i suoi 28 profili trimestrali
  arricchiti (attributo `profili`, dict periodo->profilo) + nome/gruppo.
- NODI periferici: paesi esterni che compaiono come vittime cyber, destinazioni
  migratorie o interventori militari (attributo `core=False`, senza profilo).
- ARCHI: cyber / migrazione / coinvolgimento_militare (vedi build_edges).

Serializza in data/processed/graphs/:
- grafo.pickle  (fedelta' piena, per l'analisi)
- archi.csv     (elenco piatto degli archi, per ispezione)
"""

import csv
import json
import pickle
from pathlib import Path

import networkx as nx
import yaml

from src.graph.build_edges import archi_cyber, archi_migrazione, archi_militari

BASE = Path(__file__).resolve().parents[2]
NODI = BASE / "data" / "processed" / "nodi"
CONFIG = BASE / "config" / "countries.yaml"
OUT = BASE / "data" / "processed" / "graphs"


def _carica_paesi() -> dict:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    return {p["iso3"]: p for p in cfg["paesi"]}


def _profili(iso3: str) -> dict:
    out = {}
    for f in sorted((NODI / iso3).glob(f"{iso3}_*.json")):
        periodo = f.stem.replace(f"{iso3}_", "")
        out[periodo] = json.loads(f.read_text(encoding="utf-8"))
    return out


def costruisci_grafo() -> nx.MultiDiGraph:
    paesi = _carica_paesi()
    G = nx.MultiDiGraph()

    # nodi core (i 17 paesi, con profili + aggregati utili)
    for iso3, meta in paesi.items():
        profili = _profili(iso3)
        eventi = sum((p["conflitto"].get("n_eventi_violenti") or 0) for p in profili.values())
        vittime = sum((p["conflitto"].get("n_vittime") or 0) for p in profili.values())
        G.add_node(
            iso3, core=True, nome=meta.get("nome", iso3), gruppo=meta.get("gruppo"),
            tag=meta.get("tag"), profili=profili,
            tot_eventi_violenti=eventi, tot_vittime=vittime,
        )

    # archi (aggiungendo i nodi periferici incontrati)
    def _assicura_nodo(iso3):
        if iso3 not in G:
            G.add_node(iso3, core=False, nome=iso3)

    for costruttore in (archi_cyber, archi_migrazione, archi_militari):
        for a, b, attr in costruttore():
            _assicura_nodo(a)
            _assicura_nodo(b)
            G.add_edge(a, b, **attr)

    return G


def salva(G: nx.MultiDiGraph) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "grafo.pickle", "wb") as f:
        pickle.dump(G, f)
    with open(OUT / "archi.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["da", "a", "tipo", "periodo", "peso", "categoria", "titolo", "fonte"])
        for a, b, attr in G.edges(data=True):
            w.writerow([a, b, attr.get("tipo"), attr.get("periodo"),
                        attr.get("peso"), attr.get("categoria"), attr.get("titolo"),
                        attr.get("fonte")])


def riepilogo(G: nx.MultiDiGraph) -> None:
    core = [n for n, d in G.nodes(data=True) if d.get("core")]
    perif = [n for n, d in G.nodes(data=True) if not d.get("core")]
    from collections import Counter
    per_tipo = Counter(d["tipo"] for _, _, d in G.edges(data=True))
    print(f"nodi: {G.number_of_nodes()} ({len(core)} core + {len(perif)} periferici)")
    print(f"archi totali: {G.number_of_edges()}")
    for t, n in per_tipo.items():
        print(f"   {t}: {n}")


if __name__ == "__main__":
    G = costruisci_grafo()
    riepilogo(G)
    salva(G)
    print(f"\nGrafo salvato in {OUT}/ (grafo.pickle, archi.csv)")
