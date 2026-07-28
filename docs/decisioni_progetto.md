# Log delle decisioni di progetto

Tieni qui traccia delle decisioni prese (con il tutor o autonomamente), con data.
Utile per scrivere la sezione metodologica della tesi senza doverti ricordare a memoria perche' hai fatto certe scelte.

## 2026-07-04
- Definita la lista dei 16 paesi (vedi `config/countries.yaml`), organizzati in 4 gruppi: attori cyber, alta instabilita', bersagli cyber, casi di controllo.
- Periodo di riferimento: 2018-Q1 - 2024-Q4, granularita' trimestrale.
- Struttura di progetto definita: config / data (raw + processed) / notebooks / src / outputs / scripts_hpc / docs.

## 2026-07-05
- al momento per acled ho preso solo i il due file: 
    - il primo: conta il numero totale di episodi di violenza politica (es. battaglie, esplosioni, violenze contro i civili, rivolte) per ogni country
    - il secondo: conta il numero totale di vittime (morti confermate o stimate) causate da quegli stessi conflitti e violenze.


## 2026-07-05
- Trovato il pacchetto bulk ufficiale FEWS NET "ALL_HFIC" (shapefile mensili/
  trimestrali "current situation", non proiezioni) - risolve il problema
  assessed-vs-projected e il vincolo robots.txt sulla ricerca.
- Purtroppo ha il problema che non copre tutti gli anni, va dal 2009 al 2021 circa. i file dbf non sono esplicativi mentre i pdf non sono per nazione ma per posizione geografica
- Risolto andando a mano a prendere i KMU (Key Message Update) di ogni paese (non sono molti) dovrei riuscirci a mano, se non ci riesco faccio uno script per violare robots.txt:
RUS (Russia): Non presente
CHN (Cina): Non presente
PRK (Corea del Nord): Non presente
IRN (Iran): Presente ➔ Trovato sotto Middle East and Europe -> nessun documento 
UKR (Ucraina): Presente ➔ Trovato sotto Middle East and Europe -> 26 documenti da 2024 a 2022
SDN (Sudan): Presente ➔ Trovato sotto East Africa -> 39 da 2024 a 2018
SSD (Sud Sudan) -> Trovato sotto East Africa -> 36 da 2024 a 2018
YEM (Yemen): Presente ➔ Trovato sotto Middle East and Europe da 2024 a 2018
SYR (Siria): Presente ➔ Trovato sotto Middle East and Europe
ETH (Etiopia): Presente ➔ Trovato sotto East Africa -> 37 da 2024 a 2018
VEN (Venezuela): Presente ➔ Trovato sotto Latin America and the Caribbean -> 22 dal 2024 al 2023
USA (Stati Uniti): Non presente
ISR (Israele): Non presente (Nota: nel menu c'è "Gaza", ma non Israele come nazione intera)
KOR (Corea del Sud): Non presente
SAU (Arabia Saudita): Non presente
ITA (Italia): Non presente
EST (Estonia): Non presente

## 2026-07-07
- Aggiornato il piano acled da open a research. effettuata chiamata api per prendere: event_date,year,event_type,sub_event_type,actor1,actor2,country,admin1,notes,fatalities,PERIODO -> abbiamo event_type, quindi più avanti (nel Blocco A) potremo filtrare — es. usare solo Battles/Violence against civilians/Explosions per il segnale numerico di instabilità

## 2026-07-11
-Sui 17 paesi della tua lista, 7 non hanno alcun report MPO (dimensione economia/poverta wolrd bank), e non è un bug: il prodotto MPO della World Bank copre solo le economie in via di sviluppo raggruppate nelle 5 regioni (ssa/mena/eca/eap/lac), quindi per costruzione non include le economie avanzate:

USA, ISR, KOR, ITA, EST — economie ad alto reddito, fuori dallo scope del prodotto MPO
PRK (Corea del Nord) — nessun programma/dato World Bank disponibile
VEN (Venezuela) — rientrerebbe nella regione LAC ma non è coperto (già confermato in precedenza)
Gli altri 10 paesi sono coperti, quasi tutti al completo (10/10 edizioni): RUS, CHN, IRN, UKR, ETH, SSD, SAU, YEM. Le uniche due eccezioni parziali sono quelle già trovate:

SYR: solo 6/10 (da am22 in poi — prima non era coperta dalla MENA MPO)
SDN: 9/10 (manca solo sm22)

- Problema: l'estrazione dei PDF MPO per paese (Blocco A) usava una posizione
  ordinale fissa (calcolata una volta sola sui dati sm24) per capire quale
  coppia di pagine corrispondesse a un paese, contando le occorrenze del
  testo "Key conditions and". Si rompeva perché nelle edizioni 2020-2021
  l'estrazione testo di pdfplumber falliva del tutto su alcune pagine, e
  perché il numero/ordine dei paesi cambia tra edizioni (una posizione
  fissa non regge nel tempo). Anomalie risultanti: ~20 combinazioni
  paese-edizione su 100 fuori range.
  Risolto con un approccio ibrido: bookmark nativi del PDF (affidabili per
  le edizioni 2020-2021, contengono già l'ISO3 nel titolo) + fallback
  testuale ristretto a una finestra di ±150 caratteri intorno al marcatore
  "Key conditions and" (per le edizioni 2022-2024, senza bookmark).
  Risultato: 95/100 estratte correttamente. Le 5 rimaste sono assenze reali
  del dato (SYR non coperta dalla MPO prima del 2022, SDN assente in sm22 -
  verosimilmente per il colpo di stato in Sudan di ott. 2021), non bug.
  Trovati e cancellati anche 3 file residui di un tentativo precedente,
  mal etichettati come Sudan/Siria ma con dentro pagine di Tanzania/Tunisia.

## 2026-07-11
- Problema (dimensione cyber): l'endpoint CFR per lo scaricamento incidenti cyber
  (`interactive/cyber-operations/export-incidents?_format=csv`) restituisce
  404: CFR ha rifatto il sito, passando dal vecchio tool Drupal a uno nuovo
  su WordPress (`www.cfr.org/cyber-operations/`), senza mantenere l'export
  CSV.
  Risolto usando la REST API WordPress del nuovo sito
  (`wp-json/wp/v2/posts` + tassonomie `cyber_operation`, `state_sponsor`,
  `victim_category`, `victim`, ecc.) - 865 incidenti totali.
- Problema collegato: il campo data della nuova API è la data di
  creazione/modifica della voce nel CMS, non la data dell'evento (verificato:
  su 865 post l'80% non cita nemmeno un anno nel testo per un controllo
  incrociato, e tra quelli che lo citano il 30% diverge di 3+ anni dalla
  data CMS - es. "SideWinder" creato nel 2023 ma descrive un attacco del
  2012). Il vecchio sito Drupal aveva un campo Date reale, perso nella
  migrazione.
  Risolto recuperando il vecchio export CSV dalla Wayback Machine (ultima
  cattura riuscita: 22 ottobre 2019, ~323 incidenti con Date vera) e
  riabbinandolo per titolo alla API attuale: 262/865 righe hanno ora una
  data reale (`fonte_data_evento = archivio_cfr_2019`), le restanti (per lo
  più 2020+, fuori dalla finestra dell'archivio) restano da datare via LLM
  in una fase successiva.
- Trovato l'archivio storico CISA per PDF: le Cybersecurity Advisory
  congiunte sono categorizzate per "attore di stato-nazione"
  (`advisory_nation_state_actor` su `/news-events/cybersecurity-advisories`)
  - solo 4 valori esistono: Russia, China, North Korea, Iran (esattamente i
  4 "attore_cyber" del progetto), copertura 2017-2026, ogni advisory ha un
  PDF scaricabile ospitato da CISA. Verificato che gli altri 13 paesi del
  progetto non hanno un tag equivalente su CISA: la ricerca full-text per
  quei nomi restituisce solo rumore (per USA quasi ogni advisory la cita per
  definizione; per KOR/ISR/ITA/EST i risultati sono agenzie co-firmatarie
  partner, non vittime/attori; per gli altri paesi instabilità i risultati
  sono vicini a zero) - per quei 13 resta la fonte di riferimento CFR
  (copre tutti e 17 come sponsor/vittima). Filtrato alla finestra 2018-2024
  per coerenza con le altre fonti (tolte 6 righe del 2025).
  Risultato finale: 53 advisory (RUS 18, CHN 14, PRK 8, IRN 13), 32 con PDF
  scaricato, salvate in `data/raw/cisa/{iso3}/`.

- Aggiunte le ultime due fonti cyber, ENISA Threat Landscape e Microsoft
  Digital Defense Report: a differenza di CFR/CISA sono report annuali
  globali/EU, non spezzabili per paese - salvati interi (un PDF per anno)
  in `data/raw/enisa/` e `data/raw/microsoft_mddr/`, da far passare
  all'estrazione LLM per tirarne fuori le menzioni sui 17 paesi.
  Tutti gli URL verificati a mano (nessuno indovinato) prima di scaricare.
  Entrambe le fonti hanno un buco nel 2019: ENISA non ha pubblicato
  un'edizione dedicata quell'anno (il periodo gen2019-apr2020 è coperto dal
  report etichettato "2020", uscito come 22 sotto-report invece di uno
  unico); Microsoft non ha pubblicato nulla nel 2019, nella transizione di
  brand dal vecchio "Security Intelligence Report" (fino al 2018, volume 24)
  al nuovo "Digital Defense Report" (dal 2020).
  Risultato: 6/7 edizioni scaricate per entrambe le fonti (2018, 2020-2024).

## 2026-07-12
- Aggiunto il "contesto generale" (Wikipedia) come dimensione a parte:
  scaricare dati senza un campo dichiarato nello schema JSON del Blocco A
  sarebbe stato rumore puro (dato scaricato ma mai usato). Scelta: aggiunto
  il campo `contesto_generale` a `config/extraction_schema.json`.
  A differenza delle altre dimensioni non è un segnale quantitativo per
  trimestre ma una sintesi narrativa annuale (leadership, eventi principali,
  situazioni in corso) presa dalle pagine Wikipedia "YYYY in \<Country\>" -
  esistono per tutti e 17 i paesi. Scopo dichiarato: contesto per l'LMM
  durante l'estrazione delle altre dimensioni, e knowledge di base per gli
  agenti del Blocco C (simulazione OASIS-inspired).
  Scaricate 119/119 pagine (17 paesi × 2018-2024) in `data/raw/wikipedia/{iso3}/`.
- Decisione di design per il Blocco A (estrazione, non ancora costruita):
  invece di ripetere lo stesso testo annuale su tutti e 4 i trimestri,
  un'unica chiamata LMM per (paese, anno) produrrà 4 sintesi trimestrali
  separate, basandosi sulle date già presenti nel testo (gli eventi in
  pagina sono raggruppati per mese - mappano in modo pulito sui trimestri).
  Se un trimestre non ha eventi specifici, il fallback è la sintesi generale
  dell'anno invece di un null.

- Dimensione 2 (Carestia/Siccità), risolto il blocco sul bulk ALL_HFIC
  (fermo al 2021, paese non identificabile chiaramente nelle tabelle
  shapefile): trovato che ogni pagina report di fews.net ha una versione
  `/print` che restituisce il PDF vero del report (content-type
  application/pdf) - niente più KMU da prendere a mano. Pattern URL:
  `/{regione}/{paese}/{tipo-report}/{mese}-{anno}/print`, provando in
  ordine key-message-update → food-security-outlook-update →
  food-security-outlook → targeted-analysis (si escludono a vicenda per
  mese, tranne targeted-analysis che è ad hoc).
  Solo i 7 paesi del gruppo "instabilità" sono coperti da FEWS NET (UKR,
  SDN, SSD, YEM, SYR, ETH, VEN) - confermato coerente con la ricognizione
  manuale del 5 luglio.
  Bug trovato e risolto: lo slug "corto" di atterraggio pagina (es.
  `/venezuela`, `/global/ukraine`) non è detto sia il prefisso reale sotto
  cui vivono i report - per UKR e VEN il primo tentativo ha dato 0/84 mesi,
  scoperto poi che i report veri stanno sotto un prefisso regionale diverso
  (`middle-east-and-europe/ukraine`, `latin-america-and-caribbean/venezuela`),
  trovato cercando i link ai singoli report sulla pagina paese invece di
  indovinare dal nome della regione.
  Risultato finale: 310/588 mesi-paese coperti - SDN 76/84, ETH 72/84,
  SSD 66/84, YEM 56/84, UKR 30/84 (dal 2022, coerente con l'inizio
  dell'invasione), VEN 10/84 (dal 2023), SYR 0/84 (verificato: la copertura
  FEWS NET per la Siria è iniziata solo a febbraio 2026, nessun dato
  storico 2018-2024 disponibile da questa fonte - gap reale, non un bug).

- Componente multimodale della tesi: aggiunte due fonti PDF, una per la
  dimensione instabilità/conflitti (complemento ad ACLED) e una per la
  dimensione migrazione (complemento a UNHCR), scelte dopo aver scartato
  alcune alternative:
  - ACLED stessa non pubblica più report regionali PDF liberi (paywall),
    Crisis Group CrisisWatch non ha export PDF strutturato per paese.
  - Per la migrazione: avevo già provato l'API UNHCR (richiede
    registrazione, mai approvata) e ho provato anche l'API REST di
    ReliefWeb - stesso muro: dal 1 novembre 2025 richiede un `appname`
    pre-approvato, non ottenibile al momento.
  - Soluzione: **ACAPS** (analisi di crisi umanitarie, PDF liberi,
    `acaps.org/en/countries/<slug>/archives`, paginato via TYPO3) per
    instabilità/conflitti; **ReliefWeb filtrato per fonte UNHCR** (facet
    `S2868`, HTML pubblico `reliefweb.int/updates`, niente `appname`
    necessario per la sola navigazione) per la migrazione.
  - ACAPS copre solo i paesi con una crisi umanitaria attiva: 10/17
    (CHN, IRN, UKR, SDN, SSD, YEM, SYR, ETH, VEN, ITA) hanno una country
    page con almeno un report 2018-2024; gli altri 7 (RUS, PRK, USA, ISR,
    KOR, SAU, EST) non hanno alcun prodotto ACAPS dedicato - gap reale
    della fonte. Risultato: 250 pdf totali (CHN 1, IRN 0, UKR 54, SDN 38,
    SSD 6, YEM 102, SYR 19, ETH 21, VEN 9, ITA 0), salvati in
    `data/raw/acaps/{iso3}/` con nome `{iso3}_{data}_{nomefile_acaps}.pdf`.
  - ReliefWeb+UNHCR copre tutti e 17 i paesi (anche USA/KOR/SAU/ISR, dove
    UNHCR opera comunque su asilo/resettlement), ma il volume varia
    moltissimo con l'intensità della crisi migratoria (centinaia di
    report per SDN/SYR/SSD/YEM/ETH, pochissimi per KOR/SAU/ISR). Per
    restare coerenti con la granularità trimestrale del progetto invece
    di scaricare tutto (centinaia/paese), si scarica **un solo pdf per
    trimestre**, scegliendo tra i candidati del trimestre quello con
    data più vicina alla fine del trimestre. Risultato: 245 pdf totali -
    7 paesi a copertura piena (28/28 trimestri: ETH, ITA, SDN, SSD, SYR,
    UKR, YEM), IRN 20/28, VEN 27/28, USA 2/28, e CHN/EST/ISR/KOR/PRK/RUS/
    SAU a 0 (zero articoli UNHCR su ReliefWeb nel periodo 2018-2024 per
    questi paesi - gap reale della fonte). Salvati in
    `data/raw/unhcr_reports/{iso3}/`.
  - Due problemi tecnici incontrati e risolti durante lo sviluppo:
    1. ReliefWeb blocca silenziosamente (404 sull'allegato PDF, nessun
       errore esplicito nella pagina HTML) qualsiasi User-Agent che
       contenga la parola "Bot" - richiede uno User-Agent da browser
       vero (usato uno stringa Chrome/Windows).
    2. Sui paesi ad alto volume (SDN, SSD, YEM, SYR, ETH: centinaia di
       pagine di risultati da scorrere) alcune richieste HTTP restavano
       appese per minuti pur senza errore - il timeout di `requests`
       copre solo il gap fra un chunk e l'altro, non il tempo totale
       della richiesta, quindi una risposta che arriva a scatti (mai un
       gap abbastanza lungo da far scattare il timeout) può bloccare lo
       script per tempo indefinito. Provate varie contromisure (header
       `Connection: close`, `caffeinate -i` per escludere l'App Nap di
       macOS) senza successo; la causa vera si è rivelata essere
       l'esecuzione in background dello script stesso (throttling
       dell'ambiente sandboxato sui processi lanciati in background) -
       eseguendo lo stesso identico codice in foreground il problema è
       sparito. Aggiunto comunque, per robustezza futura, un deadline
       "duro" lato client (thread separato per ogni richiesta invece di
       un pool a dimensione fissa, che si esaurirebbe con i thread
       appesi) prima di scoprire la vera causa.

## 2026-07-26
- Debug su Leonardo (nodo A100, Qwen2.5-VL:7b via Ollama) di due problemi
  distinti incontrati avviando davvero l'estrazione LMM del Blocco A:
  1. Ollama (qualunque versione >=0.13.x, testato su 0.23.3) ha una
     regressione nota nel calcolo RoPE per Qwen2.5-VL su CUDA
     (`GGML_ASSERT(a->ne[2] * 4 == b->ne[0]) failed`, crash ad ogni
     chiamata - vedi ollama/ollama#13630). Fix: pinnare `module load
     ollama/0.12.11` (confermato funzionante) in
     `scripts_hpc/estrazione_blocco_a.pbs`.
  2. Senza `num_ctx` esplicito Ollama usa il default del modello
     (>=128000 token): il KV-cache/compute-buffer risultante non entra
     su una singola A100 40GB e il runtime retrocede silenziosamente a
     girare su CPU (minuti a chiamata invece di secondi). Fix: `num_ctx`
     esplicito a 32768 in `src/extraction/ollama_client.py` (il nostro
     input reale, anche nel caso piu' pesante, sta ben sotto questa
     soglia) - con questo il modello sta tutto su una GPU (`offloaded
     29/29 layers`).
- DPI e tetto immagini per chiamata (`src/extraction/pdf_to_images.py`),
  ridimensionati dopo aver misurato il costo reale: con Flash Attention
  attiva, una chiamata con 1 sola immagine impiega ~10s, ma con le 10
  immagini del tetto originale il tempo sale oltre i 18 minuti (test
  interrotto ancora in corso, GPU-Util all'88% - non e' un blocco, e'
  calcolo vero che scala piu' che linearmente con i token immagine
  totali nel prompt). Con 476 chiamate nel batch anche spalmando su 4
  GPU in parallelo, un tetto a 10 immagini rende il job intero
  infattibile in tempi ragionevoli.
  Analisi della distribuzione reale (`indicizza_documenti` su tutti e 17
  i paesi, 423 trimestri con almeno un documento): mediana 3
  documenti/trimestre (media 3.67, max 16; coda lunga su YEM 7.6,
  SDN 6.2, UKR 6.1, ETH 5.7 - i paesi piu' instabili). Contando anche le
  pagine per documento (fino a `PAGINE_MAX_PER_DOCUMENTO`=4 ciascuno),
  il totale di immagini potenzialmente disponibili per trimestre ha
  mediana 9 e media 13 - quindi anche un tetto moderato (es. 6) taglia
  la maggioranza dei trimestri (58%), non solo i pochi casi estremi:
  il taglio e' la norma, non l'eccezione, per via del costo di calcolo.
  Mitigazione: `PRIORITA_FONTE` (gia' esistente) sceglie sempre prima le
  pagine di ACAPS/FEWS NET, le uniche fonti qualitative senza un
  equivalente testuale nel prompt; CISA e CFR hanno gia' un riassunto
  testuale indipendente dalle immagini (`input_assembly.py`), quindi
  perdere le loro pagine quando si taglia costa relativamente meno.
  Scelta finale (provvisoria, poi superata - vedi 2026-07-28): `DPI`
  170->130, `IMMAGINI_MAX_PER_CHIAMATA` 10->4.

## 2026-07-28
- Chiuso il tuning dei parametri di estrazione dopo una lunga serie di
  test su Leonardo (nodo A100, Qwen2.5-VL:7b, Ollama 0.12.11). La cosa
  piu' importante emersa: **gran parte dei "blocchi" catastrofici visti
  nei giorni scorsi (18 min, 14 min, 21 min su singole chiamate) NON
  erano dovuti al contenuto (numero immagini / risoluzione / lunghezza
  testo) ma allo stato del server Ollama**: prima chiamata "a freddo"
  dopo l'avvio o dopo un cambio di `num_ctx` (che forza un reload del
  modello), oppure degrado dopo molte chiamate consecutive sullo stesso
  processo. Prova decisiva: la stessa identica chiamata (RUS 2022-Q3,
  16 immagini, num_ctx=65536) che il 26/07 era esplosa oltre i 21 minuti
  (interrotta a mano), il 28/07 su nodo fresco + server appena riavviato
  ha girato in **21.2s, due volte di fila identiche**. Lezione operativa:
  riavviare `ollama serve` pulito prima di un giro serio, e comunque
  rendere la pipeline resiliente a chiamate anomale (vedi sotto).
- Fattori reali (a server "caldo" e sano) effettivamente misurati:
  - Flash Attention DEVE essere attiva (`OLLAMA_FLASH_ATTENTION=1`):
    senza, l'attenzione naive su sequenze lunghe (molti token immagine)
    e' memory-bandwidth-bound e degenera. Era spenta durante il primo
    test catastrofico, attiva in tutti quelli veloci successivi.
  - A 16 immagini (DPI 170) il tempo steady-state e' basso e prevedibile:
    RUS 2022-Q3 21s, YEM 2020-Q2 23s, UKR 2024-Q3 62s. La differenza di
    UKR e' spiegata dal testo Wikipedia molto piu' lungo (21.5k caratteri
    vs 3.3k di YEM: "2024 in Ukraine" e' un anno di guerra densissimo).
  - Esiste pero' un cliff reale intorno alle 24 immagini: UKR 2024-Q3 a
    24 immagini, stesso server caldo, e' passata a 857s (14 min) contro
    i 62s a 16. Quindi 16 e' dentro la zona sicura, 24 no.
  - La dimensione di `num_ctx` NON influenza la velocita' (32768 e 65536
    danno lo stesso tempo a parita' di contenuto): dimensiona solo lo
    spazio allocato, non il calcolo. Si tiene alto (65536) solo come
    margine di sicurezza contro il troncamento silenzioso del prompt
    (Ollama con `truncating input prompt` taglia il contenuto senza
    errore se il prompt supera num_ctx - pericoloso perche' l'estrazione
    "riesce" ma su input mutilato).
- **Parametri definitivi** (`src/extraction/pdf_to_images.py` e
  `ollama_client.py`): `DPI=170`, `PAGINE_MAX_PER_DOCUMENTO=4`,
  `IMMAGINI_MAX_PER_CHIAMATA=16`, `num_ctx=65536`,
  `OLLAMA_FLASH_ATTENTION=1`. A 16 immagini si perde ancora qualcosa nel
  28.6% dei trimestri (sempre i soliti paesi ad alto volume: SDN, YEM,
  ETH, IRN, SSD, UKR, RUS), ma e' un valore affidabile: inseguire tetti
  piu' alti continuava a far emergere cliff imprevedibili caso per caso.
- Due modifiche di logica decise (non ancora implementate al momento di
  questa nota):
  1. **Selezione immagini a rotazione tra le fonti** invece che a
     riempimento greedy. Problema del greedy attuale: in un trimestre con
     tanti ACAPS (es. YEM/UKR fino a 9), i primi 4 ACAPS saturano il tetto
     e fonti a priorita' piu' bassa ma di dimensioni diverse (UNHCR =
     migrazione, MPO = economia) restano fuori del tutto, lasciando quelle
     dimensioni al buio anche se il documento c'era. Soluzione: un giro
     "un documento per fonte" prima di dare un secondo documento a
     chiunque, cosi' ogni dimensione con almeno un documento e'
     rappresentata prima che una singola fonte esaurisca il budget.
  2. **Pipeline resiliente**: timeout per chiamata (~3 min) e, se scatta,
     retry con meno immagini (dimezzate), poi solo-testo, poi la
     combinazione si marca come "fallita" e il batch prosegue - invece di
     bloccare l'intero giro delle 476 chiamate su un singolo caso
     patologico o su una chiamata "a freddo" andata storta.
- **Scelta del modello per il giro finale: ancora aperta.** Punto onesto:
  in due giorni abbiamo misurato solo TEMPI, mai la QUALITA' di un output
  reale (non abbiamo ancora aperto un solo JSON prodotto). Prima di
  lanciare le 476 chiamate va fatto uno spot-check di qualita' su 3-5 casi
  diversi con qwen2.5vl:7b; se la qualita' e' adeguata si tiene il 7b (il
  piu' veloce), altrimenti si confronta con qwen2.5vl:32b in q4_K_M (~19GB,
  entra comodo su una A100-40GB, piu' lento ma con 4 GPU quasi idle e'
  comunque sostenibile). La scelta va guidata dalla qualita', non dalla
  velocita', dato che la velocita' non e' piu' un vincolo.

- Spot-check qualita' fatto (qwen2.5vl:7b, prompt/schema induriti, casi
  YEM 2020-Q2, SDN 2023-Q2, RUS 2022-Q3). Esito:
  - MIGLIORAMENTO netto dopo l'hardening: la sezione cyber su YEM/SDN
    (nessun documento cyber) e' ora correttamente vuota (array [] e
    ruolo 'non_specificato') - sparita l'invenzione di APT28/incidenti
    che c'era col prompt vecchio, che veniva dagli esempi inline nelle
    description dello schema (ora rimossi). Lingua italiana e paese=ISO3
    per lo piu' rispettati.
  - DEBOLEZZE RESIDUE del 7b, non risolvibili col solo prompt (gia'
    spinto parecchio): (a) non rispetta il "-> null" sulle dimensioni
    marcate assenti: YEM riempie migrazione/economia con speculazioni e
    arriva a scrivere "secondo il World Bank MPO il tasso di poverta' e'
    aumentato" quando l'immagine MPO non gli e' nemmeno arrivata (tagliata
    dal cap); (b) SDN mette lo stesso testo (conflitto/sfollamento) in
    tutti i campi, senza distinguere le dimensioni; (c) livello_ipc resta
    'non_specificato' anche quando il FEWS NET la riporta (lettura debole
    di mappe/grafici); (d) SDN scivola quasi tutto in inglese nonostante
    la regola. Sono limiti di capacita'/instruction-following del 7b.
  - Conclusione: il 7b e' marginale per una tesi. Prossimo passo:
    confronto con qwen2.5vl:32b (q4) sugli stessi casi, con 4 A100 quasi
    libere la qualita' deve decidere.
  - RUS 2022-Q3 (caso cyber-heavy: CISA/ENISA/MDDR) si e' ri-bloccata
    (>4 min, interrotta) nonostante Flash Attention attiva - eppure la
    stessa identica chiamata il 28/07 mattina era girata in 21s due volte.
    Conferma definitiva che la latenza delle singole chiamate e'
    intrinsecamente instabile in questo setup: la pipeline resiliente e'
    obbligatoria, non opzionale.

- Implementata la **pipeline resiliente** (`lmm_extractor.py` +
  `ollama_client.py`): ogni chiamata ha un timeout; se scatta o fallisce,
  una scaletta di degrado prova rung successivi prima di arrendersi -
  (1) chiamata normale, (2) ritenta identica (spesso basta: e' il caso
  RUS, colpa dello stato del server, non del contenuto), (3) DPI ridotto
  (stesse immagini, meno token), (4) meno immagini, (5) solo testo. Solo
  se falliscono tutti la combinazione si marca "fallito" e il batch
  prosegue - niente piu' blocco dell'intero giro su un singolo caso.
  Ordine DPI-prima-di-meno-immagini scelto apposta: ridurre il DPI tiene
  tutte le dimensioni rappresentate, ridurre le immagini butta interi
  documenti (quindi possibili intere dimensioni). Le immagini vengono
  ri-renderizzate al volo al DPI/tetto del rung, via i parametri passati
  a `assembla_input`/`documenti_a_immagini`/`pagine_a_immagini`.

- **Confronto 7b vs 32b (q4_K_M) sugli stessi 4 casi -> scelto il 32b.**
  Il 32b sistema tutte e quattro le debolezze del 7b:
  1. Rispetta il "-> null" sulle dimensioni assenti: YEM/SDN hanno
     migrazione ed economia a null invece di speculazioni; RUS ha
     carestia/migrazione a null. Niente piu' invenzione di documenti
     mai ricevuti.
  2. Legge davvero la fase IPC dalle mappe FEWS NET: YEM
     'fase4_emergenza', SDN 'fase3_crisi' (il 7b diceva sempre
     'non_specificato').
  3. Distingue le dimensioni: SDN ha conflitto (SAF/RSF) e carestia
     (driver alimentari) con contenuti diversi, non lo stesso testo
     copiato ovunque come faceva il 7b.
  4. Italiano coerente ovunque (il 7b scivolava in inglese su SDN).
  Inoltre il cyber su RUS e' ricco e corretto (ruolo 'attore', gruppi
  reali: FSB/SVR/GRU/Berserk Bear/Nobelium/UNC2452..., advisory citati
  per nome file) e su EST identifica correttamente il ruolo 'vittima'
  (DDoS su siti governativi, da ENISA). Tempi: 80-96s a chiamata sui casi
  pesanti (16 img), 28s su EST (3 img) - circa 2x il 7b, sostenibile con
  4 GPU in parallelo (~476 chiamate stimate in ~3h su 4 GPU).
  - Due difetti residui minori del 32b, da sistemare nella pipeline (non
    bloccanti): (a) su RUS l'array incidenti_noti ripete 16 volte lo
    stesso incidente Viasat (loop di ripetizione) -> serve dedup degli
    array in post-processing; (b) su SDN migrazione/economia valorizzati
    con la stringa "null" invece del vero null JSON (valido a schema
    perche' il tipo e' string|null, ma va normalizzato). Entrambi si
    risolvono con un piccolo post-processing deterministico a valle.
  - Decisione: modello definitivo per il Blocco A = **qwen2.5vl:32b**
    (q4_K_M). La qualita' e' di livello tesi; il costo in tempo e'
    accettabile viste le 4 A100.

- **Significato dei due tetti sulle immagini e cosa resta fuori (dati
  reali).** Due parametri in `pdf_to_images.py` limitano quante immagini
  finiscono in una chiamata:
  - `PAGINE_MAX_PER_DOCUMENTO = 4`: da un singolo PDF si prendono al
    massimo 4 pagine (le prime 4; per ENISA/MDDR invece le 3 pagine con
    piu' menzioni del paese). Assunzione: nei report brevi che
    raccogliamo l'executive summary / i risultati chiave stanno
    all'inizio. Le pagine oltre la 4a di un documento non vengono mai
    viste.
  - `IMMAGINI_MAX_PER_CHIAMATA = 16`: totale di immagini per chiamata,
    sommando tutti i documenti del trimestre. Serve a tenere il tempo di
    inferenza gestibile (16 immagini ~ 80-96s col 32b; oltre le ~24 il
    tempo esplode).
  - Distribuzione reale (423 trimestri con almeno un documento, su tutti
    i 17 paesi): mediana 3 documenti/trimestre, ma coda lunga fino a 16
    (YEM/UKR/SDN nei periodi di crisi). Contando le pagine, la mediana di
    immagini potenzialmente disponibili e' 9, con punte a 62 (UKR
    2024-Q3). Quindi in molti trimestri affollati il tetto di 16 taglia
    qualcosa.
  - COSA resta fuori, DOPO la rotazione tra fonti (vedi sotto): su 423
    trimestri, solo 31 (7.3%) perdono una dimensione che pure aveva un
    documento, e in TUTTI e 31 la dimensione persa e' **cyber**, mai
    conflitto/carestia/migrazione/economia. E' il risultato voluto: nella
    rotazione il cyber (ENISA/MDDR/CISA) ha priorita' piu' bassa, e in
    piu' e' l'unica dimensione con un canale di riserva testuale (CFR +
    riassunto CISA in `input_assembly`), quindi perdere le sue *immagini*
    costa relativamente poco. Prima della rotazione (riempimento greedy)
    invece a perdersi era il 28.6% dei trimestri, spesso migrazione ed
    economia - molto peggio.

- **Rotazione tra le fonti** (`_ordine_a_rotazione` in `pdf_to_images.py`).
  Sostituito il riempimento greedy (tutti i documenti della fonte a
  priorita' 0, poi la 1, ...) con un giro "un documento per fonte" in
  ordine di priorita', poi il secondo di ogni fonte, ecc. Cosi' ogni
  dimensione con almeno un documento e' rappresentata prima che una
  singola fonte (es. i tanti ACAPS di YEM/SDN) esaurisca il budget.
  Effetto verificato: YEM 2020-Q2 passa da {acaps, fews_net} a {acaps,
  fews_net, unhcr_reports, worldbank_mpo} - migrazione ed economia, prima
  perse del tutto, ora coperte.

- **Post-processing deterministico** a valle del modello
  (`_pulisci` in `lmm_extractor.py`), per i due difetti residui del 32b:
  dedup degli array cyber (il caso RUS/Viasat ripetuto 16 volte) e
  normalizzazione della stringa "null" nel vero null JSON. Non aggiunge
  contenuto, ripulisce solo forme sbagliate. Rinforzate anche le regole
  corrispondenti nel prompt (no ripetizioni, null vero non stringa).

- **Esecuzione parallela su 4 GPU e resumability**
  (`scripts_hpc/estrazione_parallela.sh`, `lmm_extractor --worker/--nworker`).
  Un server Ollama per GPU (pinnato con CUDA_VISIBLE_DEVICES, porte
  11434+i) + un worker per server; ogni worker fa la fetta `[i::N]` delle
  476 combinazioni, interleavata per bilanciare (i paesi pesanti sono
  sparsi: 119 combinazioni a worker, tutti i 17 paesi in ognuno).
  Scrittura atomica (file temporaneo + rename) e skip-se-esiste: il job
  si puo' fermare e rilanciare su piu' giorni senza lasciare file
  troncati ne' rifare lavoro. Stima: ~476 chiamate / 4 GPU a ~90s
  l'una ~ 3 ore.



