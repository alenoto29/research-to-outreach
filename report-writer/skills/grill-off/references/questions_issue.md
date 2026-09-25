# Question bank — stage: issue

Input attesi: `analysis_summary.md` + verdetto rifiuto verbatim + `fix_analysis_brief.md` precedente (se iterazione > 1).

**Loop guard**: se iterazione ≥ 3 → STOP prima di fare qualsiasi domanda. Scrivi il loop guard message e interrompi.

---

### Q1 — Natura del problema
**Obiettivo**: capire se il problema è nei dati, nel metodo, nello scope, o nella presentazione.
**Domanda**: "Il problema con l'analisi è: (a) i numeri sembrano sbagliati/inattendibili, (b) l'analisi non risponde alla domanda giusta, (c) lo scope è troppo stretto/ampio, o (d) la presentazione nel digest non è chiara?"
**Recommendation**: distingui (a)+(b) = problema sostanziale → serve fix nel modello; (c) = fix dello scope (parametri o analisi aggiuntive); (d) = il modello può essere ok, cambia solo il digest. Propone la categoria più probabile dal verdetto.

---

### Q2 — Dati o metodo specifico da correggere
**Obiettivo**: identificare esattamente cosa patchare nell'xlsx.
**Domanda**: "Quale analisi specifica o quale parametro non convince? Più specifico = patch più chirurgico. 'L'analisi del payback' è meglio di 'i numeri non tornano'."
**Recommendation**: guarda `analysis_summary.md` e proponi la sezione più probabile basandoti sul verdetto. Se il verdetto è vago, chiedi di indicare una riga/numero specifico.

---

### Q3 — Parametri da cambiare
**Obiettivo**: identificare i parametri del foglio Parametri da modificare.
**Domanda**: "Ci sono assunzioni di base da cambiare? Es. prezzo elettricità, ore di utilizzo, scenario climatico. I parametri editabili sono [lista da numbers.json constants]."
**Recommendation**: cambiare un parametro = si ricalcola tutto il modello. Proponi il parametro con impatto maggiore sul risultato contestato.

---

### Q4 — Analisi mancanti da aggiungere
**Obiettivo**: capire se mancano analisi che cambierebbero il giudizio.
**Domanda**: "Manca un'analisi che cambierebbe la valutazione? Es. un confronto geografico, uno scenario aggiuntivo, un'analisi di sensitività."
**Recommendation**: suggerisci l'analisi più veloce da aggiungere al modello esistente (non ricostruire da zero). Se richiede un feed nuovo non implementato → `[DA CALCOLARE: motivo]`.

---

### Q5 — Threshold di accettazione
**Obiettivo**: capire cosa deve cambiare nel prossimo output per ottenere OK.
**Domanda**: "Se il prossimo digest mostrasse [X cambiato], sarebbe approvato? Voglio capire il criterio di accettazione prima di patchare."
**Recommendation**: proponi un criterio concreto basato sulle risposte precedenti. Meglio "il payback sotto 5 anni" che "analisi più convincente".

---

## Header fix_analysis_brief.md per iterazione

```markdown
## Iterazione: {N}/3
**Verdetto rifiuto**: [parole esatte del giudice]

**Criterio accettazione**: [da Q5 — cosa deve cambiare per ottenere OK]

## Delta patch
### Parametri da cambiare
- {parametro}: {valore attuale} → {valore proposto} | motivo: ...

### Analisi da aggiungere
- {slug analisi}: {metodo} | feed: {fonte} | priorità: alta/media

### Metodi da correggere
- {analisi_id}: {cosa correggere}

### Scope
- {espandere/restringere}: {motivazione}
```
