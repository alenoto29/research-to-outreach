---
name: grill-off
description: "Sessione di grilling strutturata per la pipeline report off-page. Tre stage con meccanica identica (1 domanda/turno + recommendation): 'intent' (framing pre-analisi → intent.md), 'structure' (post-approvazione analisi → brief_write/graph/layout.md con placeholder {chiave}), 'issue' (post-rifiuto analisi → fix_analysis_brief.md). Trigger: 'grill-off intent', 'grill-off structure', 'grill-off issue', o quando il gate 1 (analisi) emette OK/NOT-OK. I brief di structure DEVONO usare {chiave} da numbers.json, mai numeri letterali calcolati."
model_tier: opus-xhigh
model_rationale: "Intervista strategica che determina la direzione dell'intero report. L'angolo, gli insight da includere, la struttura editoriale — decisioni non delegabili a modelli più piccoli. Errore qui si propaga a tutte le skill a valle."
---

# grill-off

Sessione di interview strutturata che prepara i brief per la pipeline report off-page. Una domanda per turno, sempre con recommendation esplicita. Tre stage con question bank diversi, stesso contratto di qualità.

## Intent

- **Obiettivo**: estrarre le decisioni editoriali chiave da Alessandro (o collega off-page) prima che la macchina lavori. Intent prima dell'analisi; struttura dopo.
- **Ottimizza per**: domande che disambiguano davvero (non domande ovvie che Alessandro risponderebbe uguale comunque).
- **Sacrifica**: completezza — meglio 5 domande incisive che 12 generiche.
- **Successo stage `intent`**: `intent.md` cattura topic, angolo preferito, pubblico target, perché questo report adesso — abbastanza per papers-references di fare analisi mirate.
- **Successo stage `structure`**: 3 brief con `{placeholder}` validi — validate_briefs.py li accetta exit 0.
- **Successo stage `issue`**: `fix_analysis_brief.md` specifica cosa patchare nell'xlsx (parametri, metodi, analisi) — abbastanza per analyzer di patchare senza ricostruire.
- **Fallimento**: brief con numeri letterali calcolati, intent.md vago/generico, loop issue oltre max iterazioni.

## Gotchas

- **Stage `structure` → {chiave}, mai numeri letterali calcolati.** Se sei tentato di scrivere "245 €" nel brief, usa `{villa_appp_season_eur}` da `numbers.json`. validate_briefs.py rifiuterà i numeri letterali analitici (hard-fail). Anni, date, statistiche di terze parti = OK come letterali.
- **Question bank `intent` è placeholder** (collega off-page in ferie al 2026-06-05). Usa le domande di `references/questions_intent.md` — se vuote, adatta dal tuo giudizio editoriale ma NON inventare domande sulla struttura (quelle sono stage `structure`).
- **Loop guard stage `issue`**: il contatore iterazione è nell'header di `fix_analysis_brief.md`. Alla 3ª iterazione senza OK → STOP esplicito con motivo, non generare un 4° fix brief.
- **Verdetto verbatim**: trascrivi le parole esatte del giudice nell'header del brief di output. Non parafrasare, non sintetizzare. Il paper trail serve per tracciare l'intenzione, non la tua interpretazione.
- **Stage ≠ sessione completa**: ogni stage può durare più turni (più domande). Non chiudere lo stage prima di aver coperto il question bank.

## Runtime Rules

1. Una domanda per turno. Aspetta la risposta prima della prossima.
2. Ogni domanda include una **recommendation esplicita** ("Raccomando X perché...").
3. Leggi `references/questions_<stage>.md` all'inizio — copertura completa del bank.
4. Stage `structure`: ogni valore computato nei brief → `{chiave}` da `numbers.json["report_keys"]`. Leggi `report_keys` prima di scrivere i brief.
5. Stage `issue`: apri `fix_analysis_brief.md` precedente (se esiste) + verdetto del giudice prima di fare domande. Non chiedere cose già risolte in iterazioni precedenti.
6. Verdetto gate trascritto **verbatim** nell'header dell'output (sezione `## Verdetto gate`).
7. Stage `issue` iterazione ≥ 3: STOP. Scrivi in `fix_analysis_brief.md` header: `## ⚠️ LOOP GUARD — iterazione {N}/3 esaurita`. Segnala cosa non ha convinto in ogni iterazione precedente.
8. Chiudi ogni stage con un riepilogo delle decisioni prese (1 bullet per risposta chiave).

## Test Prompt

1. `grill-off intent` → clarify framing, audience and scope → `intent.md`. Save structure questions for the structure stage.
2. `grill-off structure` con `numbers.json` che ha `report_keys` → brief_write.md contiene solo `{chiave}`, validate_briefs.py exit 0.
3. `grill-off structure` e Opus scrive "245 €" nel brief → correggere con `{villa_appp_season_eur}` prima di salvare.
4. `grill-off issue` con iteration=3 → STOP + loop guard message, non generare 4° fix brief.

## Input

| Stage | Input obbligatori |
|---|---|
| `intent` | topic (stringa) + angle grezzo (opzionale) |
| `structure` | `<TOPIC>/numbers.json` (con `report_keys`) + `<TOPIC>/analysis_summary.md` + verdetto gate 1 |
| `issue` | `<TOPIC>/numbers.json` + `<TOPIC>/analysis_summary.md` + verdetto rifiuto + `fix_analysis_brief.md` precedente (se esiste) + contatore iterazione |

## Workflow

```
START: leggi references/questions_<stage>.md

STAGE intent:
  1. Per ogni domanda nel bank intent: poni domanda + recommendation → attendi risposta
  2. Riepilogo decisioni prese
  3. Scrivi <TOPIC>/intent.md (vedi Output Contract)

STAGE structure:
  0. Leggi <TOPIC>/numbers.json → estrai report_keys (lista chiavi disponibili)
  1. Trascrivi verdetto gate 1 verbatim → sezione "## Verdetto gate" in testa a ogni brief
  2. Per ogni domanda nel bank structure: poni domanda + recommendation → attendi risposta
     Le risposte devono specificare {chiave} da report_keys, non valori letterali
  3. Riepilogo decisioni prese
  4. Scrivi brief_write.md + brief_graph.md + brief_layout.md con {placeholder}
  5. Verifica mentale: ogni valore numerico computato è un {placeholder}?
     Se no → sostituisci. Non delegare a validate_briefs.py come unica guardia.

STAGE issue:
  0. Controlla contatore iterazione. Se ≥ 3 → LOOP GUARD, STOP.
  1. Leggi fix_analysis_brief.md precedente + verdetto rifiuto
  2. Per ogni domanda nel bank issue: poni domanda + recommendation → attendi risposta
     Focus: cosa NON va nell'analisi + fix specifico (parametri, metodi, scope)
  3. Riepilogo decisioni prese
  4. Scrivi fix_analysis_brief.md con header iterazione + patch delta
```

## Output

### Stage `intent` → `<TOPIC>/intent.md`

```markdown
# Intent — <TOPIC>

**Topic**: <stringa>
**Angle grezzo**: <angolo/ipotesi editoriale>
**Pubblico target**: <tipo editor / outlet>
**Hook editoriale**: <perché questo report adesso, cosa lo rende esclusivo>
**Fonti preferite**: <eventuali preferenze dataset/feed>
**Note aggiuntive**: <vincoli, cose da evitare>
```

### Stage `structure` → 3 file (tutti con header verdetto)

**`<TOPIC>/brief_write.md`**:
```markdown
## Verdetto gate 1
[Parole esatte del giudice]

## Struttura testo report
- H1: <formula titolo con {headline_number}>
- Standfirst: <una frase con numero chiave>
- Lede: <stile A (scene) o B (claim diretto)>
- H2[1] "I dati chiave": bullets {chiave} da includere
- H2[2..N]: per ogni sezione analisi: titolo + 1-2 frasi narrative con {chiave}
- H2 Perché: sintesi pattern
- Chiusura: note particolari
```

**`<TOPIC>/brief_graph.md`**:
```markdown
## Verdetto gate 1
[Parole esatte del giudice]

## Chart spec
- Chart 1 (signature): tipo + asse x ({chiave}) + asse y ({chiave}) + messaggio titolo
- Chart 2 (se presente): ...
- Note stile: enfasi, colori speciali, cosa evidenziare
```

**`<TOPIC>/brief_layout.md`**:
```markdown
## Verdetto gate 1
[Parole esatte del giudice]

## Struttura docx (ordine sezioni)
1. Titolo + standfirst
2. I dati chiave (bullets)
3. [sezioni analisi in ordine]
4. Chart [posizione]
5. Perché
6. Metodologia
7. Chiusura
```

### Stage `issue` → `<TOPIC>/fix_analysis_brief.md`

```markdown
## Iterazione: <N>/3
## Verdetto rifiuto
[Parole esatte del giudice]

## Delta patch per analyzer
- Parametri da cambiare: <lista>
- Analisi da aggiungere: <lista>
- Metodi da correggere: <lista>
- Scope da ridurre/espandere: <se applicabile>
```

## Output Contract (→ validate_briefs.py + analyzer)

- `intent.md`: esiste, non vuoto, contiene topic + angle + hook.
- `brief_write/graph/layout.md`: ogni valore computato = `{chiave}` da `report_keys`. `validate_briefs.py` exit 0.
- `fix_analysis_brief.md`: header iterazione presente, delta patch specifico (non "migliorare l'analisi" generico).

## QA Gates

1. Stage `structure`: validate_briefs.py exit 0 su tutti e 3 i brief.
2. Verdetto verbatim presente in header di ogni brief di stage structure/issue.
3. Stage `issue` iterazione ≥ 3: LOOP GUARD scritto, STOP.
4. intent.md contiene hook editoriale (non solo topic + angle).
5. Nessuna domanda di stage `structure` posta in stage `intent` (concern separati).
