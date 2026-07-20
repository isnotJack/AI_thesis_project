# Script HPC (Leonardo)

Cartella vuota per ora. Quando avrai accesso a Leonardo, qui andranno:

- script di trasferimento dati locale -> cluster (rsync/scp) verso `$WORK` o `$SCRATCH`
- script batch SLURM per far girare l'estrazione LMM su piu' documenti in parallelo (Blocco A, se si sceglie un modello locale invece di un'API)
- script batch SLURM per la simulazione del Blocco C

Nota: verifica appena hai le credenziali se il tuo progetto su Leonardo ha
accesso a JupyterHub (interattivo) o se dovrai lavorare solo via job batch.
Questo cambia come strutturare il codice in questa cartella.
