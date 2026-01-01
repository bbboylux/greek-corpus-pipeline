# -*- coding: utf-8 -*-
"""The entries of the “Correct” tab and of the “Revised corpus” tab.

They live here and not in :mod:`gui_qt.i18n` because the general file would otherwise
grow too large. ``i18n`` imports this module by itself and adds its entries to the
general dictionary; each key is written in one place only.

The shape is the same as ``_STRINGS``: dotted key -> (Italian, English).
"""
from __future__ import annotations

STRINGS: dict[str, tuple[str, str]] = {

    # ── The “Correct” tab: what it is ──────────────────────────────────
    "review.title": ("Correggi il corpus, un caso alla volta",
                     "Correct the corpus, one case at a time"),
    "review.intro": (
        "Il programma non cambia niente da solo. Ogni segnalazione che porta "
        "con sé un valore proposto te la mostra qui, con il valore attuale e "
        "quello proposto uno accanto all'altro: sei tu ad accettarla o a "
        "rifiutarla, un caso alla volta. L'unica correzione che si applica in "
        "blocco è il dizionario di forme, perché quello lo hai scritto tu. Il "
        "corpus originale non viene mai toccato: le tue decisioni producono "
        "una seconda versione, separata, che al passo 10 esporti come versione "
        "revisionata.",
        "The program changes nothing by itself. Every finding that carries a "
        "proposed value is shown here, with the current value and the proposed "
        "one side by side: you accept it or reject it, one case at a time. The "
        "only correction applied in bulk is the form dictionary, because you "
        "wrote that one yourself. The original corpus is never touched: your "
        "decisions produce a second, separate version, which you export as a "
        "revised corpus at step 10."),

    "review.tab.cases": ("Proposte, una alla volta", "Proposals, one at a time"),
    "review.tab.dictionary": ("Dizionario di forme", "Form dictionary"),
    "review.tab.decisions": ("Le mie decisioni", "My decisions"),

    # ── The proposals, case by case ────────────────────────────────────
    "review.cases.hint": (
        "Ogni riga è un caso solo. Le colonne «ora → proposta» mostrano il "
        "valore che il corpus ha adesso e quello che il programma propone: "
        "guarda la frase a destra, poi accetta o rifiuta. Niente viene scritto "
        "nel corpus finché non premi il pulsante in fondo alla pagina.",
        "Every row is one single case. The «now → proposed» columns show the "
        "value the corpus has and the value the program proposes: read the "
        "sentence on the right, then accept or reject. Nothing is written into "
        "the corpus until you press the button at the foot of the page."),
    "review.cases.only_proposals": ("Solo i casi con una proposta",
                                    "Only cases that carry a proposal"),
    "review.cases.only_undecided": ("Solo quelli che non ho ancora deciso",
                                    "Only the ones I have not decided yet"),
    "review.cases.none": (
        "Nessun caso da mostrare con questi filtri. Togli la spunta a «solo i "
        "casi con una proposta» per vedere anche le segnalazioni su cui il "
        "programma non propone niente e che vanno decise leggendo la frase.",
        "No case to show with these filters. Untick «only cases that carry a "
        "proposal» to see the findings on which the program proposes nothing "
        "and which have to be settled by reading the sentence."),
    "review.cases.count": ("{0} casi, {1} già decisi", "{0} cases, {1} decided"),

    "review.current": ("Come sta scritto adesso", "How it is written now"),
    "review.proposal": ("La proposta del programma", "What the program proposes"),
    "review.proposal.none": (
        "Su questo caso il programma non propone nessun valore: la segnalazione "
        "indica il punto da guardare, la correzione la scrivi tu qui sotto.",
        "On this case the program proposes no value: the finding shows the "
        "place to look at, the correction is one you write yourself below."),
    "review.accept": ("Accetta questa proposta", "Accept this proposal"),
    "review.accept.hint": (
        "Scrive la proposta fra le tue decisioni. Il corpus cambia solo quando "
        "premi «Applica».",
        "Records the proposal among your decisions. The corpus changes only "
        "when you press «Apply»."),
    "review.reject": ("Rifiuta", "Reject"),
    "review.reject.hint": (
        "Segna il caso come guardato e respinto: resta nel registro, con la "
        "data, e sparisce dall'elenco di quelli da decidere.",
        "Marks the case as looked at and refused: it stays in the log, with its "
        "date, and leaves the list of the ones still to decide."),
    "review.accepted": ("Proposta accettata.", "Proposal accepted."),
    "review.rejected": ("Proposta rifiutata.", "Proposal rejected."),
    "review.by_hand": ("Oppure scrivi tu il valore",
                       "Or write the value yourself"),
    "review.decided": ("Deciso il {0}", "Decided on {0}"),
    "review.no_proposal_to_accept": (
        "Qui non c'è nessuna proposta da accettare.",
        "There is no proposal to accept here."),

    "review.decisions.hint": (
        "Il registro di quello che hai deciso: che cosa c'era prima, che cosa "
        "hai scritto, quando e perché. È un CSV dentro la cartella "
        "dell'esecuzione, quindi si legge, si versiona e si manda a un collega "
        "anche senza questo programma.",
        "The log of what you decided: what was there before, what you wrote, "
        "when and why. It is a CSV inside the run's folder, so it can be read, "
        "versioned and sent to a colleague without this program."),
    "review.decisions.none": (
        "Non hai ancora deciso niente. Le decisioni che prendi nella scheda "
        "delle proposte finiscono qui.",
        "You have not decided anything yet. The decisions you take in the "
        "proposals tab end up here."),

    # ── The dictionary of forms ────────────────────────────────────────
    "review.dict.title": ("Un dizionario di forme che hai già corretto tu",
                          "A form dictionary you have already corrected"),
    "review.dict.intro": (
        "Se hai già un file con le tue correzioni (una tabella forma → lemma e/o etichetta, magari corretta in un foglio di calcolo) puoi caricarlo qui e applicarlo in blocco a tutte le occorrenze di quelle forme. È l'unica correzione di massa che questa pagina fa, e la fa perché il contenuto lo hai deciso tu.",
        "If you already have a file with your corrections (a form → lemma and/or tag table, corrected in a spreadsheet perhaps) you can load it here and apply it in bulk to every occurrence of those forms. It is the only mass correction this page performs, and it performs it because you decided its content."),
    "review.dict.format": (
        "<b>Che file serve.</b> Un CSV con l'intestazione, in UTF-8, separato "
        "da virgola, punto e virgola o tabulazione (va bene quello che salva "
        "Excel).<br><br>"
        "<b>Le colonne, con questi nomi esatti:</b>"
        "<table cellspacing='0' cellpadding='4'>"
        "<tr><td><code><b>form</b></code></td><td><b>obbligatoria</b></td>"
        "<td>la forma come compare nel corpus</td></tr>"
        "<tr><td><code><b>postag</b></code></td><td>facoltativa</td>"
        "<td>l'etichetta morfologica da assegnare</td></tr>"
        "<tr><td><code><b>lemma</b></code></td><td>facoltativa</td>"
        "<td>il lemma da assegnare</td></tr>"
        "</table>"
        "<b>Almeno una fra <code>postag</code> e <code>lemma</code> deve "
        "esserci</b>, altrimenti il file non dice niente e viene rifiutato. Un "
        "file a due colonne <code>form,lemma</code> è il caso in cui "
        "<code>postag</code> manca, ed è accettato.<br><br>"
        "<b>Come vengono lette le righe.</b> Una cella vuota lascia il valore "
        "com'è, non lo cancella. Una riga senza forma, o con lemma ed "
        "etichetta entrambi vuoti, viene saltata e contata. Se la stessa forma "
        "compare due volte vale l'ultima. Le righe che cominciano con "
        "<code>#</code> sono commenti.<br><br>"
        "<b>Le righe che non corrispondono a niente non sono un errore</b>: "
        "vengono ignorate, e il programma ti dice quante sono prima che tu "
        "applichi qualcosa.<br><br>"
        "<b>Il confronto è esatto</b>: accenti, spiriti e maiuscole contano "
        "(<i>ἄνδρες</i>, <i>Ἄνδρες</i> e <i>ανδρες</i> sono tre voci diverse). "
        "L'unica cosa che il programma uniforma è la composizione Unicode, "
        "così una forma digitata su un'altra tastiera corrisponde lo stesso.",
        "<b>What file it wants.</b> A CSV with a header row, in UTF-8, "
        "separated by comma, semicolon or tab (what Excel saves will do).<br><br>"
        "<b>The columns, under these exact names:</b>"
        "<table cellspacing='0' cellpadding='4'>"
        "<tr><td><code><b>form</b></code></td><td><b>required</b></td>"
        "<td>the form as it appears in the corpus</td></tr>"
        "<tr><td><code><b>postag</b></code></td><td>optional</td>"
        "<td>the morphological tag to assign</td></tr>"
        "<tr><td><code><b>lemma</b></code></td><td>optional</td>"
        "<td>the lemma to assign</td></tr>"
        "</table>"
        "<b>At least one of <code>postag</code> and <code>lemma</code> must be "
        "present</b>, otherwise the file says nothing and is refused. A "
        "two-column <code>form,lemma</code> file is the case in which "
        "<code>postag</code> is absent, and it is accepted.<br><br>"
        "<b>How the rows are read.</b> An empty cell leaves the value as it is, "
        "it does not erase it. A row with no form, or with both lemma and tag "
        "empty, is skipped and counted. If the same form appears twice, the "
        "last one wins. Lines starting with <code>#</code> are comments.<br><br>"
        "<b>Rows that match nothing are not an error</b>: they are ignored, and "
        "the program tells you how many they are before you apply "
        "anything.<br><br>"
        "<b>Matching is exact</b>: accents, breathings and capitals count "
        "(<i>ἄνδρες</i>, <i>Ἄνδρες</i> and <i>ανδρες</i> are three different "
        "entries). The only thing the program levels out is Unicode "
        "composition, so a form typed on a different keyboard still matches."),
    "review.dict.file": ("Il tuo file CSV", "Your CSV file"),
    "review.dict.placeholder": (
        "Nessun file scelto, colonne: form (obbligatoria), postag, lemma",
        "No file chosen, columns: form (required), postag, lemma"),
    "review.dict.choose": ("Scegli il file…", "Choose the file…"),
    "review.dict.template": ("Scarica un modello CSV già pronto",
                             "Download a ready-made CSV template"),
    "review.dict.template.hint": (
        "Un file con l'intestazione giusta e le istruzioni dentro, da riempire "
        "con le tue forme.",
        "A file with the right header and the instructions inside, to fill in "
        "with your own forms."),
    "review.dict.template.saved": ("Modello salvato in {0}",
                                   "Template saved to {0}"),
    "review.dict.clear": ("Togli il dizionario", "Remove the dictionary"),
    "review.dict.none": ("Nessun dizionario caricato.",
                         "No dictionary loaded."),
    "review.dict.read": (
        "{0} voci lette: {1} con il lemma, {2} con l'etichetta.",
        "{0} entries read: {1} with a lemma, {2} with a tag."),
    "review.dict.skipped": (
        " {0} righe saltate (senza forma, o senza niente da assegnare).",
        " {0} rows skipped (no form, or nothing to assign)."),
    "review.dict.duplicates": (
        " {0} forme ripetute: vale l'ultima riga.",
        " {0} repeated forms: the last row wins."),
    "review.dict.coverage": (
        "In questo corpus: {0} voci corrispondono a una forma, {1} non "
        "corrispondono a niente e restano senza effetto. Cambierebbero {2} "
        "parole ({3} nel lemma, {4} nell'etichetta).",
        "In this corpus: {0} entries match a form, {1} match nothing and will "
        "have no effect. They would change {2} words ({3} in the lemma, {4} in "
        "the tag)."),
    "review.dict.error": ("Il dizionario non è stato caricato. {0}",
                          "The dictionary was not loaded. {0}"),
    "review.dict.preview": ("Che cosa contiene il file", "What the file contains"),
    "review.dict.save_mine": ("Salva le mie decisioni come dizionario",
                              "Save my decisions as a dictionary"),
    "review.dict.save_mine.hint": (
        "Le decisioni accettate escono nello stesso formato che questa pagina "
        "legge: forma, etichetta, lemma. Puoi correggerle in un foglio di "
        "calcolo e ricaricarle, qui o su un altro corpus.",
        "Your accepted decisions come out in the very format this page reads: "
        "form, tag, lemma. You can correct them in a spreadsheet and load them "
        "back, here or on another corpus."),
    "review.dict.saved_mine": ("{0} forme salvate in {1}",
                               "{0} forms saved to {1}"),
    "review.dict.ambiguous": (
        " {0} forme sono state corrette in due modi diversi e restano fuori: un "
        "dizionario assegna un valore solo per forma.",
        " {0} forms were corrected in two different ways and are left out: a "
        "dictionary assigns one value per form."),
    "review.dict.nothing_to_save": (
        "Non ci sono ancora decisioni accettate da salvare.",
        "There are no accepted decisions to save yet."),

    # The messages that the dictionary reader raises by itself.
    "review.dict.err.no_form": (
        "Il file non ha una colonna «form»: senza la forma il programma non sa "
        "a che cosa applicare la correzione. Le colonne trovate sono: {0}.",
        "The file has no «form» column: without the form the program does not "
        "know what to apply the correction to. The columns found are: {0}."),
    "review.dict.err.no_value": (
        "Il file ha la colonna «form» ma non ha né «postag» né «lemma»: non "
        "c'è niente da assegnare. Le colonne trovate sono: {0}.",
        "The file has a «form» column but neither «postag» nor «lemma»: there "
        "is nothing to assign. The columns found are: {0}."),
    "review.dict.err.missing": ("Il file non esiste: {0}",
                                "That file does not exist: {0}"),
    "review.dict.err.unreadable": (
        "Il file non si riesce a leggere come CSV: {0}",
        "The file cannot be read as a CSV: {0}"),

    # ── The application to the corpus ──────────────────────────────────
    "review.apply.title": ("Applica al corpus", "Apply to the corpus"),
    "review.apply": ("Applica le decisioni che ho preso",
                     "Apply the decisions I took"),
    "review.apply.hint": (
        "Il corpus originale non viene toccato: quello che nasce è una seconda "
        "versione, in un file a parte. Si può rifare tutte le volte che vuoi, e "
        "una decisione tolta dal registro sparisce anche dalla versione revisionata "
        "alla prossima applicazione.",
        "The original corpus is left alone: what is written is a second "
        "version, in a separate file. You can redo it as often as you like, and "
        "a decision removed from the log disappears from the revised corpus "
        "at the next application."),
    "review.apply.summary": (
        "Verranno applicate {0} decisioni accettate e {1} voci di dizionario.",
        "{0} accepted decisions and {1} dictionary entries will be applied."),
    "review.apply.nothing": (
        "Non c'è ancora niente da applicare: accetta qualche proposta, oppure "
        "carica un dizionario di forme.",
        "There is nothing to apply yet: accept a few proposals, or load a form "
        "dictionary."),

    # ── The pointer to step 10 ─────────────────────────────────────────
    "review.gold_ready.body": (
        "Hai {n} correzioni applicate. Esiste adesso una tua versione del corpus, distinta dall'originale: si esporta in XML AGDT, CSV o CoNLL-U, si mette da parte in un file solo e si confronta con Stanza e UDPipe: tutto al passo 10.",
        "You have {n} corrections applied. There is now a version of the corpus that is yours, distinct from the original: it exports to AGDT XML, CSV or CoNLL-U, it can be put aside in a single file and compared against Stanza and UDPipe: all of that at step 10."),

    # ── The gold tab: the result only ──────────────────────────────────
    "gold.intro": (
        "Questa pagina non decide niente: le decisioni si prendono al passo 5. "
        "Qui c'è soltanto il risultato.",
        "This page decides nothing: decisions are taken at step 5. What is here "
        "is only the result."),
    "gold.howto.2": (
        "Questa pagina non decide niente: le decisioni si prendono al passo 5. Qui c'è soltanto il risultato: che cosa è cambiato rispetto all'originale, come portarlo fuori nei tre formati, come conservarlo in un file solo e come misurare Stanza e UDPipe contro la tua versione invece che contro l'originale. Il corpus originale resta intatto e serve da termine di confronto.",
        "This page decides nothing: decisions are taken at step 5. What is here is only the result: what changed with respect to the original, how to take it out in the three formats, how to keep it in a single file, and how to measure Stanza and UDPipe against your version instead of against the original. The original corpus stays intact and serves as the point of comparison."),
    "gold.state.none": (
        "Le decisioni non sono ancora state applicate al corpus. Torna al passo "
        "«Correggi» e premi «Applica le decisioni che ho preso»: solo allora "
        "esiste una versione revisionata da esportare.",
        "Your decisions have not been applied to the corpus yet. Go back to the "
        "«Correct» step and press «Apply the decisions I took»: only then does a "
        "revised corpus exist."),
    "gold.msg.not_applied": (
        "Non esiste ancora una versione revisionata. Torna al passo «Correggi», "
        "accetta le proposte che ti convincono e premi «Applica le decisioni "
        "che ho preso».",
        "There is no revised corpus yet. Go back to the «Correct» step, "
        "accept the proposals you agree with, and press «Apply the decisions I "
        "took»."),
    "gold.goto_review": ("Vai al passo «Correggi» →", "Go to the «Correct» step →"),
    "gold.metric.missing_before": ("Lemmi mancanti prima", "Missing lemmas before"),
    "gold.metric.missing_after": ("Lemmi mancanti dopo", "Missing lemmas after"),
    "gold.tab.diff.hint": (
        "Una riga per parola cambiata, con il valore prima e dopo. È l'unico "
        "posto del programma in cui questa tabella sta, ed è quella che rende "
        "ogni correzione verificabile una per una.",
        "One row per changed word, with the value before and after. It is the "
        "one place in the program where this table lives, and it is what makes "
        "every correction checkable one by one."),
    "gold.diff.none": (
        "Nessuna parola è stata cambiata: la versione revisionata è identica "
        "all'originale.",
        "Not one word has been changed: the revised corpus is identical to "
        "the original."),

    # ── Column names, as they are read ─────────────────────────────────
    "column.anomalia": ("anomalia", "anomaly"),
    "column.che cosa non torna": ("che cosa non torna", "what looks wrong"),
    "column.etichetta_proposta": ("etichetta: ora → proposta",
                                  "tag: now → proposed"),
    "column.lemma_proposto": ("lemma: ora → proposto", "lemma: now → proposed"),
    "column.relazione_proposta": ("relazione: ora → proposta",
                                  "relation: now → proposed"),
    "column.decisione": ("la tua decisione", "your decision"),
    "column.document_id": ("documento", "document"),
    "column.sentence_id": ("frase", "sentence"),
    "column.token_id": ("record n.", "record no."),
    "column.rule_id": ("codice regola", "rule code"),
    "column.parola_n": ("record n.", "record no."),
    "column.lemma_prima": ("lemma prima", "lemma before"),
    "column.lemma_dopo": ("lemma dopo", "lemma after"),
    "column.etichetta_prima": ("etichetta prima", "tag before"),
    "column.etichetta_dopo": ("etichetta dopo", "tag after"),
    "column.quando": ("quando", "when"),
    "column.perché": ("perché", "why"),
    "column.chi": ("chi", "who"),
    "column.stato": ("stato", "state"),
    "column.etichetta nuova": ("etichetta nuova", "new tag"),
    "column.lemma nuovo": ("lemma nuovo", "new lemma"),
    "column.relazione nuova": ("relazione nuova", "new relation"),
    "column.etichetta vecchia": ("etichetta vecchia", "old tag"),
    "column.lemma vecchio": ("lemma vecchio", "old lemma"),
    "column.relazione vecchia": ("relazione vecchia", "old relation"),

    # ── Category values, as they are read ──────────────────────────────
    "value.accettata": ("accettata", "accepted"),
    "value.respinta": ("respinta", "rejected"),
    "value.proposta": ("da decidere", "still to decide"),
    "value.da decidere": ("da decidere", "still to decide"),
}
