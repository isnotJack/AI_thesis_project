"""
Blocco C - test 4: controllo di CONTAMINAZIONE dei modelli.

Il backtest ha senso solo se i modelli NON conoscono gia' gli eventi che devono
simulare. Prima della simulazione si chiede quindi a ogni modello che cosa sa dei
due eventi del 2025 (piu' una domanda di controllo su un evento che certamente
conosce, per verificare che risponda quando sa, e una sulla propria data limite).

Le risposte si salvano integralmente e si leggono a mano: e' quella lettura a
decidere. Il codice segnala soltanto gli INDIZI, cioe' i dettagli che un modello
potrebbe citare solo se avesse visto l'evento (luoghi, nomi, date). Alcuni indizi
possono comparire anche per conoscenza generale precedente (es. Fordow e' un sito
noto dal 2009): un indizio e' un motivo per leggere, non una prova.

Output: data/processed/backtest/contaminazione/<modello>.json

Uso (su HPC, con un server Ollama attivo):
    python3 -m src.simulation.contaminazione --modello llama3.3:70b --host http://127.0.0.1:11434
Prova locale senza modello: python3 -m src.simulation.contaminazione --mock
"""

import argparse
import json
from pathlib import Path

from src.simulation.oasis_inspired import responder_ollama
from src.simulation.run_simulazione import _safe

BASE = Path(__file__).resolve().parents[2]
OUT = BASE / "data" / "processed" / "backtest" / "contaminazione"

DOMANDE = [
    {"id": "guerra_iran_israele_2025",
     "testo": "Che cosa e' successo fra Israele e Iran nel giugno 2025? Indica date, Paesi "
              "coinvolti, attacchi militari e informatici ed esito finale. Se non conosci "
              "questo evento, dillo esplicitamente senza inventare."},
    {"id": "discorso_mattarella_2025",
     "testo": "Che cosa e' successo nel febbraio 2025 dopo il discorso del Presidente della "
              "Repubblica italiana Sergio Mattarella all'Universita' di Marsiglia? Indica le "
              "reazioni della Russia ed eventuali attacchi informatici contro l'Italia. Se non "
              "conosci questo evento, dillo esplicitamente senza inventare."},
    {"id": "controllo_7_ottobre_2023",
     "testo": "Che cosa e' successo in Israele il 7 ottobre 2023? Rispondi in poche frasi."},
    {"id": "data_limite",
     "testo": "Fino a quale data arrivano le tue conoscenze? Indica il mese e l'anno degli "
              "eventi piu' recenti che conosci."},
]

# Dettagli che difficilmente si indovinano senza aver visto l'evento.
INDIZI = {
    "guerra_iran_israele_2025": ["fordow", "al udeid", "al-udeid", "predatory sparrow",
                                 "sepah", "nobitex", "rising lion", "midnight hammer",
                                 "dodici giorni", "12 giorni", "twelve-day", "24 giugno",
                                 "22 giugno", "13 giugno", "b-2", "thaad"],
    "discorso_mattarella_2025": ["noname", "linate", "malpensa", "intesa", "nexi",
                                 "mediobanca", "zakharova", "zacharova", "blasfem",
                                 "terzo reich", "russofob", "ddos", "17 febbraio"],
}


def _indizi(id_domanda: str, risposta: str) -> list:
    t = (risposta or "").lower()
    return [k for k in INDIZI.get(id_domanda, []) if k in t]


def interroga(modello: str, responder) -> dict:
    out = {"modello": modello, "risposte": []}
    for d in DOMANDE:
        try:
            r = responder(d["testo"])
        except Exception as e:            # una domanda fallita non ferma le altre
            r = f"(errore: {e})"
        out["risposte"].append({"id": d["id"], "domanda": d["testo"], "risposta": r,
                                "indizi": _indizi(d["id"], r)})
    out["indizi_totali"] = {x["id"]: x["indizi"] for x in out["risposte"] if x["id"] in INDIZI}
    return out


def _mock(prompt: str) -> str:
    return "Non conosco questo evento: le mie conoscenze si fermano al 2023."


def main():
    ap = argparse.ArgumentParser(description="Controllo di contaminazione per il backtest.")
    ap.add_argument("--modello", default=None)
    ap.add_argument("--host", default=None)
    ap.add_argument("--forza", action="store_true")
    ap.add_argument("--mock", action="store_true")
    a = ap.parse_args()
    if a.mock:
        modello, responder = "mock", _mock
    else:
        if not a.modello:
            ap.error("specificare --modello (oppure --mock)")
        # temperatura 0 e testo libero: si vuole la risposta piu' probabile del modello
        modello = a.modello
        responder = responder_ollama(a.modello, host=a.host, num_ctx=4096,
                                     temperature=0.0, seed=0, formato="")
    f = OUT / f"{_safe(modello)}.json"
    if f.exists() and not a.forza:
        print(f"[skip] contaminazione {modello} (gia' fatta)")
        return
    res = interroga(modello, responder)
    OUT.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok  ] contaminazione {modello} -> {f}  indizi: {res['indizi_totali']}")


if __name__ == "__main__":
    main()
