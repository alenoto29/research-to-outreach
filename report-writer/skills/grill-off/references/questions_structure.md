# Question bank — stage: structure

Input attesi prima di iniziare: `analysis_summary.md` + `numbers.json["report_keys"]` + verdetto gate 1 verbatim.

---

### Q1 — Headline number
**Obiettivo**: bloccare il numero principale del titolo e del lede.
**Domanda**: "Guardando `analysis_summary.md`, qual è il numero più sorprendente o quotabile? Questo diventa `{headline_number}` — il numero nel titolo del report."
**Recommendation**: proponi il numero con più impatto wallet/familiare (€/stagione, % risparmio, moltiplicatore). Se ce ne sono due candidati, mostra entrambi e chiedi.

---

### Q2 — Insight da includere
**Obiettivo**: selezionare i 5-7 insight chiave per la sezione "I dati chiave da sapere".
**Domanda**: "Dall'analisi sono emersi questi insight [lista da analysis_summary.md]. Quali 5-7 metti nella sezione bullets quotabili? Ogni bullet deve essere citabile standalone da un giornalista."
**Recommendation**: privilegia insight con numero specifico + contesto breve. Scarta quelli che richiedono spiegazione lunga (vanno nel corpo, non nei bullets).

---

### Q3 — Struttura H2 (ordine analisi nel corpo)
**Obiettivo**: definire l'ordine delle sezioni analisi nel corpo del report.
**Domanda**: "Le analisi da includere sono [lista da pick]. In che ordine le vuoi? Suggerisco: prima l'analisi con il numero headline, poi quelle che supportano la tesi, poi 'Perché'."
**Recommendation**: ordine narrativo (tesi → evidenze → implicazione), non ordine tecnico (facile → difficile). Chiedi se c'è un'analisi che vuole in apertura per sorpresa/shock.

---

### Q4 — Signature chart
**Obiettivo**: decidere quale analisi merita il grafico principale.
**Domanda**: "Quale analisi si visualizza meglio? Il signature chart deve essere auto-esplicativo: un editor lo guarda 5 secondi e capisce il messaggio senza leggere il testo."
**Recommendation**: in genere la comparazione o il ranking è più visivo di una serie temporale. Proponi il tipo (bar chart comparativo, line chart trend, scatter parametrico) per l'analisi scelta.

---

### Q5 — Chart secondari (se presenti)
**Obiettivo**: decidere se ci sono grafici di supporto oltre al signature.
**Domanda**: "Vuoi grafici secondari, o solo il signature chart? Ogni grafico aggiuntivo deve aggiungere una dimensione che il testo da solo non rende."
**Recommendation**: max 2-3 grafici totali per un report .docx. Più grafici = più tempo di composizione, meno chiarezza visiva.

---

### Q6 — Tono e pubblico (conferma da intent)
**Obiettivo**: verificare che lo stile scritto sia allineato all'outlet target deciso in intent.
**Domanda**: "Confermo: il report è per [outlet tipo da intent.md], quindi stile [generalista wallet / specializzato policy]. Ci sono parti dove vuoi un taglio diverso?"
**Recommendation**: consistenza > variazione. Se il report è generalista, mantenere il tono familiare anche nella metodologia (no gergo).

---

### Q7 — Cosa NON includere
**Obiettivo**: escludere esplicitamente analisi o claim che potrebbero creare problemi.
**Domanda**: "C'è qualcosa dall'analisi che vuoi escludere? Un'analisi non conclusiva, un claim troppo forte, un confronto che non vuoi fare?"
**Recommendation**: meglio escludere esplicitamente che lasciare che writer includa per default.

---

## Regola {placeholder} per questo stage

Ogni risposta che cita un valore computato (€, kWh, %, W) deve usare la chiave da `report_keys`:

```
# OK
"Nel brief mettiamo: '{villa_appp_season_eur} vs {villa_g_season_eur}'"

# NON OK
"Nel brief mettiamo: '245 € vs 489 €'"
```

Se non sai la chiave esatta: chiedi prima di scrivere il brief, non usare il numero letterale.
