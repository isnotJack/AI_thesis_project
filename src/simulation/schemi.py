"""
Blocco C - definizioni e schemi condivisi della simulazione OASIS-inspired.

Qui stanno le DEFINIZIONI che vengono passate all'agente nel prompt (dimensioni,
tipi di relazione, azioni ammesse) e lo SCHEMA JSON con cui validiamo la sua
risposta. Tenerle in un unico posto garantisce che prompt e validazione parlino
la stessa lingua (precisione = niente ambiguita').
"""

from dataclasses import dataclass, field
from typing import Optional

# --------------------------------------------------------------------------- #
# Vocabolario canonico
# --------------------------------------------------------------------------- #
TIPI_ARCO = ("cyber", "migrazione", "militare")
OPERAZIONI_ARCO = ("rafforza", "indebolisci", "crea", "taglia")

# Le 6 dimensioni dello stato di un Paese (come nei profili in data/processed/nodi).
# Testo usato nel prompt per spiegare all'agente cosa rappresenta ogni dimensione.
DIMENSIONI = {
    "contesto_generale": "Testo di sintesi sulla situazione generale del Paese nel trimestre.",
    "conflitto": "Instabilita' e violenza politica interna. Numeri (ACLED): "
                 "n_eventi_violenti, n_vittime.",
    "carestia": "Sicurezza alimentare (scala FEWS NET/IPC crescente). livello_ipc "
                "deve essere UNO tra: nessuna, fase1_minima, fase2_stressata, "
                "fase3_crisi, fase4_emergenza, fase5_carestia, non_specificato.",
    "migrazione": "Flussi di persone in uscita. Numeri (UNHCR): rifugiati, "
                  "richiedenti_asilo, sfollati_interni.",
    "economia": "Situazione economica. Numero (World Bank): tasso_poverta_pct.",
    "cyber": "Postura cyber. ruolo deve essere UNO tra: attore, vittima, "
             "entrambi, non_specificato; piu' gruppi/incidenti noti e "
             "n_incidenti_datati.",
}

# Verso semantico di ciascun tipo di relazione (fondamentale: gli archi sono diretti).
VERSI_ARCO = {
    "cyber": "attaccante -> vittima",
    "migrazione": "Paese di origine -> Paese di destinazione dei rifugiati",
    "militare": "interventore (forze militari straniere) -> teatro (Paese in cui operano)",
}

# Significato delle operazioni sugli archi.
SIGNIFICATO_OP = {
    "rafforza": "aumenta il peso di una relazione gia' esistente (o creala se assente)",
    "indebolisci": "riduci il peso di una relazione esistente",
    "crea": "crea una nuova relazione verso un Paese (anche non ancora presente sulla mappa)",
    "taglia": "azzera/rimuovi una relazione esistente",
}

# Elementi della "knowledge base" (il contesto dato all'agente) a cui una scelta
# puo' essere ANCORATA. L'agente tagga ogni scelta con la sua base; usa
# 'conoscenza_generale' se la scelta NON deriva dalla KB ma dal suo sapere.
TAG_KB = [
    "evento",              # l'evento ricevuto
    "contesto_generale", "conflitto", "carestia", "migrazione", "economia", "cyber",
    "traiettoria",         # i trend numerici della sua storia
    "relazioni",           # le sue relazioni attuali
    "conoscenza_generale", # NON dalla KB: sapere generale del modello
]


# --------------------------------------------------------------------------- #
# Evento
# --------------------------------------------------------------------------- #
@dataclass
class Evento:
    """Un evento che si propaga nella rete. Formato semplice apposta: cosi' in
    futuro puo' essere composto anche da un'interfaccia (input utente sul grafo)."""
    testo: str
    paese: str                      # ISO3 del Paese che RICEVE l'evento
    tipo: str = "generico"          # cyber | migrazione | militare | generico
    mittente: Optional[str] = None  # ISO3 di chi lo genera (None se iniettato da noi)
    data: Optional[str] = None      # 'AAAA-Qn' se datato, altrimenti None
    round: int = 0

    def as_dict(self) -> dict:
        return {"testo": self.testo, "paese": self.paese, "tipo": self.tipo,
                "mittente": self.mittente, "data": self.data, "round": self.round}


# --------------------------------------------------------------------------- #
# Schema JSON della risposta dell'agente (per validazione difensiva)
# --------------------------------------------------------------------------- #
SCHEMA_AZIONE = {
    "type": "object",
    "properties": {
        "ragionamento": {"type": "string",
                         "description": "Come sei arrivato alla decisione (2-3 frasi): "
                                        "cosa dello stato/storia/evento ti porta a reagire cosi'."},
        "reazione_breve": {"type": "string"},
        "aggiornamenti_stato": {
            "type": "object",
            "description": "Mappa 'dimensione.campo' -> nuovo valore. Solo cio' che cambia.",
        },
        "azioni_su_archi": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "op": {"enum": list(OPERAZIONI_ARCO)},
                    "verso": {"type": "string"},
                    "tipo": {"enum": list(TIPI_ARCO)},
                    "peso_delta": {"type": ["number", "null"]},
                    "motivo": {"type": "string"},
                    "base_kb": {"type": "string",
                                "description": "elemento della KB da cui deriva la scelta (vedi TAG_KB), "
                                               "o 'conoscenza_generale' se non dalla KB"},
                },
                "required": ["op", "verso", "tipo"],
            },
        },
        "genera_eventi": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "verso": {"type": "string"},
                    "tipo": {"enum": list(TIPI_ARCO) + ["generico"]},
                    "testo": {"type": "string"},
                    "base_kb": {"type": "string"},
                },
                "required": ["verso", "testo"],
            },
        },
        "basi_kb": {"type": "array", "items": {"type": "string"},
                    "description": "elenco degli elementi della KB su cui ti sei basato in questo round"},
    },
    "required": ["reazione_breve"],
}

# Risposta "vuota" valida (usata come fallback se il parsing fallisce del tutto).
AZIONE_VUOTA = {"ragionamento": "", "reazione_breve": "", "aggiornamenti_stato": {},
                "azioni_su_archi": [], "genera_eventi": [], "basi_kb": []}


# --------------------------------------------------------------------------- #
# Schema del GIUDIZIO (modello-as-a-judge)
# --------------------------------------------------------------------------- #
# Un modello di famiglia diversa valuta, per (scenario, modello), quanto il
# dialogo prodotto e' COERENTE con i dati estratti (la KB) e plausibile,
# restituendo punteggi numerici + la propria motivazione + le evidenze (dove
# nel dialogo/nella KB ha dedotto il giudizio).
SCHEMA_GIUDIZIO = {
    "type": "object",
    "properties": {
        "punteggio": {"type": "number", "description": "0-100, valutazione complessiva"},
        "coerenza_kb": {"type": "number", "description": "0-100: le scelte/ragionamenti sono coerenti coi dati?"},
        "plausibilita": {"type": "number", "description": "0-100: la catena di reazioni e' geopoliticamente plausibile?"},
        "fedelta_grounding": {"type": "number", "description": "0-100: le scelte sono davvero ancorate alla KB (non inventate)?"},
        "motivazione": {"type": "string", "description": "perche' questo punteggio (ragionamento del giudice)"},
        "evidenze": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "osservazione": {"type": "string"},
                    "riferimento": {"type": "string", "description": "dove: round/Paese del dialogo o campo della KB"},
                },
            },
        },
    },
    "required": ["punteggio", "motivazione"],
}

GIUDIZIO_VUOTO = {"punteggio": None, "coerenza_kb": None, "plausibilita": None,
                  "fedelta_grounding": None, "motivazione": "", "evidenze": []}
