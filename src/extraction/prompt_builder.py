"""
Costruzione del prompt per la chiamata di estrazione (Blocco A).

Il vincolo di FORMA del JSON (quali campi, quali tipi, quali enum) lo
applica Ollama stesso via il parametro `format` (JSON Schema passato
alla generazione, vedi ollama_client.py) - qui il prompt si concentra
sul contenuto: cosa deve capire il modello da testo/immagini forniti.
Le spiegazioni di ogni campo sono lette direttamente dalle "description"
di config/extraction_schema.json, cosi' vivono in un solo posto invece
di essere duplicate qui.
"""

from src.extraction.input_assembly import InputAssemblato
from src.utils.config_loader import load_countries, load_extraction_schema

_NOME_PAESE = {p["iso3"]: p["nome"] for p in load_countries()}

# Mappa dimensione -> fonti (tipi immagine / blocchi di testo) che la
# supportano. Serve a dire esplicitamente all'LMM, trimestre per trimestre,
# quali dimensioni hanno documenti e quali no: e' la leva piu' forte contro
# l'allucinazione (se una dimensione non ha fonti, il modello non deve
# compilarla). Wikipedia e' contesto generale: sostiene 'conflitto' (spesso
# ne descrive gli eventi) e 'contesto_generale', non le dimensioni tecniche.
_FONTI_IMMAGINE_PER_DIMENSIONE = {
    "conflitto": {"acaps"},
    "carestia": {"fews_net"},
    "migrazione": {"unhcr_reports"},
    "economia": {"worldbank_mpo"},
    "cyber": {"cisa", "enisa", "mddr"},
}

# Cosa deve contenere una dimensione quando NON ha alcun documento a supporto.
_VUOTO_SE_ASSENTE = {
    "conflitto": "descrizione = null",
    "carestia": "livello_ipc = \"non_specificato\", descrizione = null",
    "migrazione": "descrizione = null",
    "economia": "sintesi = null",
    "cyber": "incidenti_noti = [], advisory_che_menzionano_il_paese = [], "
    "gruppi_minaccia_associati = [], settori_bersaglio = [], ruolo = \"non_specificato\"",
}


def _disponibilita_dimensioni(ia: InputAssemblato) -> dict:
    """Per ogni dimensione, True se in questo trimestre c'e' almeno un
    documento (immagine o testo) che la puo' supportare."""
    fonti_img = {fonte for fonte, _nome, _png in ia.immagini}
    disp = {}
    for dim, fonti in _FONTI_IMMAGINE_PER_DIMENSIONE.items():
        disp[dim] = bool(fonti_img & fonti)
    # Wikipedia sostiene anche il conflitto (spesso ne narra gli eventi).
    if ia.testo_wikipedia:
        disp["conflitto"] = True
    # Il cyber ha anche fonti testuali (CFR, riassunto CISA).
    if ia.testo_cfr or ia.testo_cisa:
        disp["cyber"] = True
    return disp


def _blocco_disponibilita(disp: dict) -> str:
    righe = []
    for dim in ("conflitto", "carestia", "migrazione", "economia", "cyber"):
        if disp.get(dim):
            righe.append(f"- {dim}: DOCUMENTI PRESENTI -> compila i campi in base ai documenti.")
        else:
            righe.append(
                f"- {dim}: NESSUN DOCUMENTO in questo trimestre -> {_VUOTO_SE_ASSENTE[dim]}. "
                "Non dedurre nulla da altre dimensioni o da conoscenza generale."
            )
    return "\n".join(righe)


def _guida_campi(schema: dict) -> str:
    righe = []
    for chiave, spec in schema["properties"].items():
        if chiave in ("paese", "periodo"):
            continue
        if spec.get("type") == "object":
            righe.append(f"- {chiave}: {spec.get('description', '')}")
            for sotto_chiave, sotto_spec in spec.get("properties", {}).items():
                desc = sotto_spec.get("description", "")
                enum = sotto_spec.get("enum")
                extra = f" [valori possibili: {', '.join(enum)}]" if enum else ""
                righe.append(f"    - {chiave}.{sotto_chiave}: {desc}{extra}")
        else:
            righe.append(f"- {chiave}: {spec.get('description', '')}")
    return "\n".join(righe)


def costruisci_prompt(input_assemblato: InputAssemblato) -> tuple:
    """Ritorna (prompt_testo, lista_immagini_png) pronti per ollama_client."""
    ia = input_assemblato
    schema = load_extraction_schema()
    nome_paese = _NOME_PAESE.get(ia.paese, ia.paese)

    disp = _disponibilita_dimensioni(ia)

    blocchi = [
        "Sei un analista di rischio geopolitico-cyber. Compili un profilo strutturato "
        f"per {nome_paese} ({ia.paese}) nel trimestre {ia.periodo}, basandoti "
        "ESCLUSIVAMENTE sui documenti forniti qui sotto (testo e immagini di pagine "
        "reali di report).",
        "",
        "REGOLE ASSOLUTE (rispettale sempre):",
        "1. Usa solo le informazioni contenute nei documenti forniti. Non usare la tua "
        "conoscenza generale del mondo.",
        "2. NON inventare nulla: ne' incidenti, ne' gruppi, ne' nomi, ne' date, ne' "
        "numeri. Se un'informazione non e' nei documenti, il campo resta vuoto.",
        "3. Campo vuoto significa: il valore JSON null per i campi descrizione/sintesi/"
        "contesto_generale (NON la stringa \"null\", NON una frase che dice che manca "
        "il dato); l'array vuoto [] per i campi lista; l'enum apposito indicato sotto "
        "per i campi a scelta chiusa.",
        "4. NON copiare nel risultato gli esempi o le spiegazioni dei campi: quelle "
        "servono solo a te per capire cosa cercare, non sono dati da riportare.",
        "5. Negli array NON ripetere due volte lo stesso elemento: ogni voce deve "
        "essere distinta. Un incidente/gruppo/settore va elencato una sola volta.",
        "6. Rispondi interamente in ITALIANO.",
        f"7. Il campo `paese` deve essere ESATTAMENTE \"{ia.paese}\" (codice ISO3) e "
        f"`periodo` esattamente \"{ia.periodo}\".",
        "8. Non riportare numeri precisi (percentuali, conteggi, cifre, importi): sono "
        "gestiti altrove nel progetto. Descrivi in modo qualitativo, senza cifre.",
        "9. Dove i documenti forniscono informazioni, compila i campi in modo completo "
        "e accurato: non lasciare vuoto cio' che i documenti supportano.",
        "",
        "DOCUMENTI DISPONIBILI PER DIMENSIONE IN QUESTO TRIMESTRE (rispetta esattamente "
        "cosa lasciare vuoto dove non ci sono documenti):",
        _blocco_disponibilita(disp),
        "",
        "Significato dei campi da compilare:",
        _guida_campi(schema),
        "",
        "Nel campo `fonti`, elenca solo i documenti che hai davvero usato per riempire "
        "il JSON (nomi file o url, vedi elenco fonti disponibili in fondo).",
    ]

    if ia.testo_wikipedia:
        blocchi += [
            "",
            f"--- Contesto Wikipedia (pagina annuale 'YYYY in {nome_paese}', copre "
            "l'intero anno, non solo questo trimestre - usa le date nel testo per "
            "isolare gli eventi del trimestre richiesto; se il trimestre non ha eventi "
            "specifici, riprendi la sintesi generale dell'anno per contesto_generale) ---",
            ia.testo_wikipedia,
        ]

    if ia.testo_cfr:
        blocchi += [
            "",
            "--- Incidenti cyber noti (CFR Cyber Operations Tracker) in questo trimestre ---",
            ia.testo_cfr,
        ]

    if ia.testo_cisa:
        blocchi += [
            "",
            "--- Advisory CISA pubblicati in questo trimestre (titolo e data) ---",
            ia.testo_cisa,
        ]

    if ia.immagini:
        elenco = "\n".join(
            f"  {i + 1}. {fonte} ({nome_file})" for i, (fonte, nome_file, _png) in enumerate(ia.immagini)
        )
        blocchi += [
            "",
            f"--- {len(ia.immagini)} immagini allegate (pagine di report PDF), in questo ordine ---",
            elenco,
        ]
    else:
        blocchi += ["", "(Nessun documento PDF disponibile per questo paese/trimestre.)"]

    blocchi += [
        "",
        f"Fonti disponibili totali: {', '.join(ia.fonti_usate) if ia.fonti_usate else 'nessuna'}.",
    ]

    prompt = "\n".join(blocchi)
    immagini_png = [png for _fonte, _nome, png in ia.immagini]
    return prompt, immagini_png


if __name__ == "__main__":
    import sys

    from src.extraction.input_assembly import assembla_input

    iso3 = sys.argv[1] if len(sys.argv) > 1 else "SDN"
    periodo = sys.argv[2] if len(sys.argv) > 2 else "2023-Q2"

    prompt, immagini = costruisci_prompt(assembla_input(iso3, periodo))
    print(prompt)
    print()
    print(f"[{len(immagini)} immagini allegate, {sum(len(p) for p in immagini) / 1024:.0f} KB totali]")
