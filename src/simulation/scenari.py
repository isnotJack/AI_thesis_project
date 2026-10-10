"""
Blocco C - scenari iniziali per la simulazione.

Un "evento iniettato" e' il seme della simulazione: lo decidiamo noi e lo diamo
a un Paese (che deve essere uno dei 17 core, cosi' ha un profilo e puo' reagire).
Sono volutamente MISTI (cyber e non) e su Paesi/dimensioni diverse, per far
emergere catene di propagazione differenti. La data ancora lo stato iniziale al
trimestre giusto (l'agente parte da quella "fotografia" + la storia precedente).

Uso:
    from src.simulation.scenari import SCENARI
    ev = SCENARI["siccita_darfur"]
"""

from src.simulation.schemi import Evento

SCENARI = {
    # --- cyber ---
    "ransomware_usa": Evento(
        tipo="cyber", paese="USA", data="2023-Q1",
        testo="Un vasto attacco ransomware colpisce simultaneamente ospedali e "
              "operatori energetici statunitensi, con interruzioni prolungate dei "
              "servizi e forte pressione mediatica per una risposta."),
    "sanzioni_russia_cyber": Evento(
        tipo="cyber", paese="RUS", data="2022-Q2",
        testo="Una coalizione di Stati attribuisce pubblicamente alla Russia una "
              "grande operazione cyber contro infrastrutture occidentali e annuncia "
              "nuove sanzioni coordinate."),
    "spionaggio_cina": Evento(
        tipo="cyber", paese="CHN", data="2023-Q3",
        testo="Viene scoperta e resa pubblica una campagna di cyber-spionaggio su "
              "larga scala attribuita a gruppi legati alla Cina, con espulsioni "
              "diplomatiche e reazioni dei Paesi colpiti."),

    # --- carestia / migrazione ---
    "siccita_darfur": Evento(
        tipo="generico", paese="SDN", data="2018-Q3",
        testo="Una grave siccita' colpisce il Darfur aggravando la carestia; le "
              "scorte alimentari crollano e cresce la pressione a migrare verso i "
              "Paesi confinanti."),
    "crisi_venezuela": Evento(
        tipo="generico", paese="VEN", data="2019-Q1",
        testo="Il collasso economico e l'iperinflazione in Venezuela raggiungono un "
              "nuovo picco, spingendo un'ondata di emigrazione verso i Paesi della "
              "regione."),

    # --- conflitto / militare ---
    "escalation_ucraina": Evento(
        tipo="militare", paese="UKR", data="2022-Q1",
        testo="Un'improvvisa escalation militare colpisce l'Ucraina: forze straniere "
              "intensificano le operazioni sul territorio, con vittime e sfollamenti "
              "di massa."),
    "guerra_yemen": Evento(
        tipo="militare", paese="YEM", data="2019-Q2",
        testo="Nuova offensiva nel conflitto yemenita con coinvolgimento di potenze "
              "regionali; peggiorano crisi umanitaria e insicurezza alimentare."),
}


# --------------------------------------------------------------------------- #
# Scenari del BACKTEST (test 4): eventi REALI del 2025, successivi alla data fino
# alla quale i tre modelli sono stati addestrati (Llama 3.3 e Nemotron: dicembre
# 2023; Qwen2.5: circa meta' 2024) e all'ultimo trimestre dei dati (2024-Q4).
# Lo stato di partenza e' la fotografia 2024-Q4; il testo descrive SOLO l'evento
# scatenante, senza alcun accenno a cio' che e' accaduto dopo, che e' la verita'
# di riferimento con cui confrontare la simulazione (config/verita_backtest.json).
# --------------------------------------------------------------------------- #
SCENARI_BACKTEST = {
    # 13 giugno 2025: inizio della guerra dei dodici giorni (13-24 giugno 2025)
    "guerra_iran_israele_2025": Evento(
        tipo="militare", paese="IRN", mittente="ISR", data="2024-Q4",
        testo="Israele lancia un vasto attacco aereo a sorpresa contro l'Iran: colpisce "
              "impianti nucleari e basi militari in diverse regioni del Paese e uccide alti "
              "comandanti dei Pasdaran e diversi scienziati nucleari."),
    # 5 febbraio 2025: discorso del Presidente della Repubblica all'Universita' di Marsiglia
    "discorso_mattarella_2025": Evento(
        tipo="generico", paese="RUS", mittente="ITA", data="2024-Q4",
        testo="In un discorso pubblico all'Universita' di Marsiglia, il Presidente della "
              "Repubblica italiana accosta l'aggressione russa all'Ucraina ai progetti di "
              "conquista del Terzo Reich in Europa."),
}


def trova(nome: str) -> Evento:
    """Lo scenario per nome, fra quelli di base e quelli del backtest."""
    if nome in SCENARI:
        return SCENARI[nome]
    if nome in SCENARI_BACKTEST:
        return SCENARI_BACKTEST[nome]
    raise KeyError(f"scenario sconosciuto: {nome}")


def elenco() -> list:
    return list(SCENARI.keys())


if __name__ == "__main__":
    for nome, ev in {**SCENARI, **SCENARI_BACKTEST}.items():
        print(f"- {nome}: [{ev.tipo}] {ev.paese} {ev.data} — {ev.testo[:70]}…")
