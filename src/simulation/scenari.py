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


def elenco() -> list:
    return list(SCENARI.keys())


if __name__ == "__main__":
    for nome, ev in SCENARI.items():
        print(f"- {nome}: [{ev.tipo}] {ev.paese} {ev.data} — {ev.testo[:70]}…")
