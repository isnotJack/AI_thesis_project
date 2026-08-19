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
                },
                "required": ["verso", "testo"],
            },
        },
    },
    "required": ["reazione_breve"],
}

# Risposta "vuota" valida (usata come fallback se il parsing fallisce del tutto).
AZIONE_VUOTA = {"reazione_breve": "", "aggiornamenti_stato": {},
                "azioni_su_archi": [], "genera_eventi": []}
