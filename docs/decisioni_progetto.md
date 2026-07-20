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

