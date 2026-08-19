"""
Blocco C - Ambiente (componente 1: "Environment Server alleggerito").

Riusa il grafo del Blocco B (grafo.pickle) e ne ricava una vista di RELAZIONI
AGGREGATE: un solo arco per (a, b, tipo) con un peso complessivo. E' questo
l'oggetto che la simulazione fa evolvere (su una COPIA: i file reali non si
toccano). Fornisce:
- le relazioni/vicini di un Paese (per costruire la scheda dell'agente),
- l'applicazione delle operazioni sugli archi (rafforza/indebolisci/crea/taglia),
- gli snapshot per round (per log e visualizzazione).

Il peso aggregato:
- migrazione / militare -> somma dei pesi reali (rifugiati / eventi),
- cyber -> numero di incidenti (il cyber non ha un peso intrinseco).
"""

import copy
import pickle
from pathlib import Path

import networkx as nx

BASE = Path(__file__).resolve().parents[2]
GRAFO = BASE / "data" / "processed" / "graphs" / "grafo.pickle"

# archi.csv usa 'coinvolgimento_militare'; nella simulazione usiamo 'militare'.
_TIPO_CANON = {"cyber": "cyber", "migrazione": "migrazione",
               "coinvolgimento_militare": "militare", "militare": "militare"}


class Ambiente:
    def __init__(self, grafo_path: Path = GRAFO):
        with open(grafo_path, "rb") as f:
            G = pickle.load(f)
        self.G = G
        self.core = {n for n, d in G.nodes(data=True) if d.get("core")}
        self.nomi = {n: (d.get("nome") or n) for n, d in G.nodes(data=True)}
        self.gruppi = {n: d.get("gruppo") for n, d in G.nodes(data=True)}
        self.R = self._aggrega(G)   # relazioni aggregate mutabili

    # ---- costruzione della vista aggregata ---- #
    @staticmethod
    def _aggrega(G) -> nx.MultiDiGraph:
        pesi: dict = {}
        for a, b, d in G.edges(data=True):
            tipo = _TIPO_CANON.get(d.get("tipo"))
            if tipo is None:
                continue
            w = 1 if tipo == "cyber" else (d.get("peso") or 0)
            pesi[(a, b, tipo)] = pesi.get((a, b, tipo), 0) + w
        R = nx.MultiDiGraph()
        for (a, b, tipo), w in pesi.items():
            R.add_edge(a, b, key=tipo, tipo=tipo, peso=float(w))
        return R

    # ---- interrogazione (per la scheda dell'agente) ---- #
    def relazioni(self, iso3: str) -> dict:
        """Relazioni del Paese, divise in uscenti ed entranti."""
        usc, ent = [], []
        if iso3 in self.R:
            for _, b, k, d in self.R.out_edges(iso3, keys=True, data=True):
                usc.append({"verso": b, "tipo": k, "peso": round(d["peso"], 1)})
            for a, _, k, d in self.R.in_edges(iso3, keys=True, data=True):
                ent.append({"da": a, "tipo": k, "peso": round(d["peso"], 1)})
        usc.sort(key=lambda r: -r["peso"]); ent.sort(key=lambda r: -r["peso"])
        return {"uscenti": usc, "entranti": ent}

    def vicini(self, iso3: str) -> set:
        v = set()
        if iso3 in self.R:
            v |= set(self.R.successors(iso3)) | set(self.R.predecessors(iso3))
        v.discard(iso3)
        return v

    # ---- mutazione (le azioni dell'agente sugli archi) ---- #
    def applica_arco(self, op: str, a: str, verso: str, tipo: str,
                     peso_delta=None) -> dict:
        """Applica un'operazione sull'arco a->verso di un certo tipo.
        Ritorna un descrittore del cambiamento (per il log/visualizzazione)."""
        tipo = _TIPO_CANON.get(tipo, tipo)
        if tipo not in ("cyber", "migrazione", "militare") or not verso or verso == a:
            return {"op": op, "esito": "ignorata"}
        delta = abs(float(peso_delta)) if peso_delta not in (None, "") else None
        esistente = self.R.has_edge(a, verso, key=tipo)
        prima = self.R[a][verso][tipo]["peso"] if esistente else 0.0

        if op == "taglia":
            if esistente:
                self.R.remove_edge(a, verso, key=tipo)
            dopo = 0.0
        elif op == "crea":
            nuovo = delta if delta is not None else max(1.0, prima)
            self._set(a, verso, tipo, nuovo)
            dopo = nuovo
        elif op == "rafforza":
            d = delta if delta is not None else max(1.0, prima * 0.5)
            self._set(a, verso, tipo, prima + d)
            dopo = prima + d
        elif op == "indebolisci":
            d = delta if delta is not None else prima * 0.5
            dopo = max(0.0, prima - d)
            if dopo <= 0:
                if esistente:
                    self.R.remove_edge(a, verso, key=tipo)
                dopo = 0.0
            else:
                self._set(a, verso, tipo, dopo)
        else:
            return {"op": op, "esito": "sconosciuta"}

        return {"op": op, "da": a, "verso": verso, "tipo": tipo,
                "peso_prima": round(prima, 1), "peso_dopo": round(dopo, 1),
                "nuovo_nodo": verso not in self.G and verso not in self.nomi}

    def _set(self, a, b, tipo, peso):
        if self.R.has_edge(a, b, key=tipo):
            self.R[a][b][tipo]["peso"] = float(peso)
        else:
            self.R.add_edge(a, b, key=tipo, tipo=tipo, peso=float(peso))

    # ---- snapshot (stato delle relazioni a fine round) ---- #
    def snapshot(self) -> list:
        return [{"da": a, "a": b, "tipo": k, "peso": round(d["peso"], 1)}
                for a, b, k, d in self.R.edges(keys=True, data=True)]
