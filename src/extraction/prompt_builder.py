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

    blocchi = [
        "Sei un analista di rischio geopolitico-cyber. Il tuo compito e' compilare "
        f"un profilo strutturato per {nome_paese} ({ia.paese}) nel trimestre {ia.periodo}, "
        "usando SOLO le informazioni nei documenti forniti qui sotto (testo e immagini "
        "allegate, pagine di report reali). Se un'informazione non e' esplicitamente "
        "presente, lascia il campo a null: non inventare, non dedurre da conoscenza "
        "generale che non sia nei documenti forniti.",
        "",
        "Significato dei campi da compilare:",
        _guida_campi(schema),
        "",
        "Nel campo `fonti`, elenca i documenti che hai davvero usato per riempire "
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
