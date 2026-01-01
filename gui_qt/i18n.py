"""Every visible string, in Italian and English, in one place.

The interface is bilingual, and English is the language it starts in. Switching
language changes the whole interface at once and takes effect immediately, without
restarting.

Strings are keyed by a dotted path (``load.title``) rather than by their
Italian text, so that editing the Italian never silently breaks the English.
A missing key returns the key itself, visibly wrong, rather than an empty
label that looks like a rendering bug.
"""
from __future__ import annotations

import re
from typing import Callable

LANGUAGES = {"it": "Italiano", "en": "English"}

_STRINGS: dict[str, tuple[str, str]] = {

    # ── Application shell ──────────────────────────────────────────────
    "app.title": ("Greek Corpus Pipeline", "Greek Corpus Pipeline"),
    "app.subtitle": ("Analisi e controllo dei treebank di greco antico",
                     "Analysis and quality control for Ancient Greek treebanks"),
    "app.language": ("Lingua", "Language"),
    "app.help": ("Guida", "Help"),
    "app.no_corpus": ("Nessun corpus caricato", "No corpus loaded"),
    "app.corpus": ("Corpus", "Corpus"),
    "app.ready": ("Pronto", "Ready"),
    "app.working": ("Elaborazione in corso…", "Working…"),
    "app.busy_title": ("Un'operazione è già in corso", "An operation is already running"),
    "app.busy_body": ("Aspetta che finisca, poi riprova.",
                      "Wait for it to finish, then try again."),
    "app.error": ("Si è verificato un errore", "Something went wrong"),
    "app.log": ("Registro delle operazioni", "Activity log"),
    "app.show_log": ("Mostra registro", "Show log"),
    "app.hide_log": ("Nascondi registro", "Hide log"),
    "app.done": ("Fatto.", "Done."),

    # ── Steps in the left rail ─────────────────────────────────────────
    "step.load": ("Carica il corpus", "Load a corpus"),
    "step.load.hint": ("Da cartella o da GitHub", "From a folder or from GitHub"),
    "step.overview": ("Panoramica", "Overview"),
    "step.overview.hint": ("Che cosa c'è dentro", "What is in it"),
    "step.errors": ("Trova le segnalazioni", "Diagnostic findings"),
    "step.errors.hint": ("Controlli diagnostici", "Diagnostic checks"),
    "step.review": ("Correggi", "Correct"),
    "step.review.hint": ("Decidi cosa modificare", "Decide what to change"),
    "step.search": ("Cerca nel corpus", "Search the corpus"),
    "step.search.hint": ("Forme e lemmi, con il contesto",
                         "Forms and lemmas, with their context"),
    "overview.manifest": ("Esporta il manifest", "Export the manifest"),
    "overview.manifest.hint": (
        "Un file con la provenienza di quello che vedi: versione del programma, "
        "corpus e sua impronta, filtri in vigore, le cinque unità con il loro "
        "conteggio, il denominatore di ogni percentuale, il catalogo dei "
        "controlli e ogni lista scientifica con la sua versione e la sua "
        "impronta. Un numero senza la sua provenienza non si può controllare.",
        "A file with the provenance of what you see: program version, corpus and "
        "its fingerprint, the filters in force, the five units with their "
        "counts, the denominator of every percentage, the catalogue of checks "
        "and every scientific list with its version and its fingerprint. A "
        "number without its provenance cannot be checked."),
    "overview.manifest.done": ("Manifest scritto: {0}", "Manifest written: {0}"),
    "rail.reference": ("RIFERIMENTO", "REFERENCE"),
    "rail.done": ("Fatto", "Done"),
    "step.variation": ("Variation n-gram", "Variation n-gram"),
    "step.variation.hint": ("Incoerenze fra passi simili",
                            "Inconsistencies across similar passages"),
    "step.stats": ("Statistiche", "Statistics"),
    "step.stats.hint": ("Il ritratto del corpus", "The corpus in numbers"),
    "step.charts": ("Grafici", "Charts"),
    "step.charts.hint": ("Sintesi visive", "Visual summaries"),
    "step.models": ("Confronta i modelli", "Compare the models"),
    "step.models.hint": ("Stanza e UDPipe", "Stanza and UDPipe"),
    "step.gold": ("Versione revisionata", "Revised corpus"),
    "step.gold.hint": ("Esporta, conserva, confronta", "Export, keep, compare"),

    "step.locked": ("Prima carica un corpus", "Load a corpus first"),
    "step.needs_analysis": ("Prima esegui il controllo", "Run the check first"),

    # ── Load page ──────────────────────────────────────────────────────
    "load.title": ("Carica un treebank", "Load a treebank"),
    "load.intro": (
        "Indica dove sono i file XML del treebank. Puoi scegliere una cartella sul "
        "tuo computer oppure incollare l'indirizzo di una repository GitHub: in quel "
        "caso il programma la scarica da solo.",
        "Point the program at the treebank's XML files. Choose a folder on your "
        "computer, or paste a GitHub address and the program will download it."),
    "load.source": ("Da dove prendo i file", "Where the files are"),
    "load.folder": ("Cartella sul computer", "Folder on this computer"),
    "load.github": ("Indirizzo GitHub", "GitHub address"),
    "load.browse": ("Scegli cartella…", "Choose folder…"),
    "load.name": ("Nome da dare a questo corpus", "Name for this corpus"),
    "load.name_hint": ("Serve solo a ritrovarlo dopo", "Only used to find it again later"),
    "load.go": ("Carica il corpus", "Load the corpus"),
    "load.examples": ("Esempi pronti", "Ready-made examples"),
    "load.examples_hint": (
        "Un clic scarica e carica uno dei due treebank su cui il programma è stato "
        "messo a punto, oppure uno dei quattro strati del campione di GLAUx.",
        "One click downloads and loads one of the two treebanks the program was "
        "developed on, or one of the four strata of the GLAUx sample."),
    "load.saved": ("Corpora già caricati", "Corpora already loaded"),
    "load.saved_hint": (
        "Ogni caricamento resta salvato: selezionalo per riprendere il lavoro.",
        "Every load is kept: select one to pick up where you left off."),
    "load.open": ("Apri", "Open"),
    "load.pick_a_run": ("Scegli prima un giro dall'elenco qui sopra.",
                        "Pick a run from the list above first."),
    "load.delete": ("Elimina", "Delete"),
    "load.missing": ("Indica prima una cartella o un indirizzo",
                     "Give a folder or an address first"),
    # ── The catalogue of the user's metadata ──────────────────────────
    "load.metadata": ("Metadati del corpus", "Corpus metadata"),
    # The text states what actually happens: the program does not deduce author, work,
    # century, dialect or genre from the file names, for any corpus.
    "load.metadata_hint": (
        "Facoltativi. GCP può analizzare il corpus anche senza metadati: i "
        "controlli, i confronti fra annotazioni, la ricerca e le statistiche "
        "funzionano lo stesso. Aggiungili se vuoi filtrare o confrontare i "
        "risultati per autore, opera, periodo, genere, dialetto o altre "
        "categorie. Quello che il programma sa da sé viene da due sole strade: "
        "l'identificativo che il file dichiara di sé dentro l'XML, e il "
        "catalogo di una risorsa che ha riconosciuto dall'impronta del corpus. "
        "Il nome del file non conta: un file chiamato «medea.xml» non diventa "
        "Euripide. Per tutto il resto puoi caricare un CSV tuo: scarica "
        "l'esempio, riempilo e caricalo. La guida «Metadati» spiega ogni "
        "colonna.",
        "Optional. GCP can analyse the corpus without metadata too: the "
        "checks, the annotation comparisons, the search and the statistics all "
        "work the same. Add them if you want to filter or compare the results "
        "by author, work, period, genre, dialect or other categories. What the "
        "program knows by itself comes from two roads only: the identifier the "
        "file declares about itself inside the XML, and the catalogue of a "
        "resource it recognised from the fingerprint of the corpus. The file "
        "name does not count: a file called «medea.xml» does not become "
        "Euripides. For everything else you can load a CSV of your own: "
        "download the example, fill it in and load it. The «Metadata» guide "
        "explains every column."),
    "load.metadata_choose": ("Carica il tuo CSV…", "Load your CSV…"),
    "load.metadata_template": ("Scarica l'esempio", "Download the example"),
    "load.metadata_clear": ("Torna ai metadati di serie", "Back to the shipped metadata"),
    # The status always says which set of metadata applies, and does not suggest that
    # one applies when none does.
    "load.metadata_none": ("Nessun metadato disponibile.", "No metadata available."),
    "load.metadata_bundled": ("Metadati di serie — {0}.", "Shipped metadata — {0}."),
    "load.metadata_active": ("Metadati caricati dall'utente — {file}.",
                             "Metadata loaded by the user — {file}."),
    "meta.view_needs": (
        "Questa vista richiede il metadato «{0}». Il corpus può essere "
        "analizzato normalmente; carica dei metadati se vuoi questo "
        "raggruppamento.",
        "This view needs the «{0}» metadata field. The corpus can be analysed "
        "normally; load metadata if you want this grouping."),
    "load.metadata_ok": ("Catalogo caricato.", "Catalogue loaded."),
    "load.metadata_ko": ("Il catalogo non è stato caricato.", "The catalogue was not loaded."),
    "load.metadata_template_ok": (
        "Esempio salvato come {file}. Aprilo con un foglio di calcolo, sostituisci "
        "le due righe con le tue e ricaricalo.",
        "Example saved as {file}. Open it in a spreadsheet, replace the two rows "
        "with your own and load it back."),

    "load.filters": ("Che cosa escludere dall'analisi", "What to leave out of the analysis"),
    "load.filter_placeholders": (
        "Nodi ellittici (segnaposto [0] e parole aggiunte dall'annotatore)",
        "Elliptic nodes (both [0] placeholders and words supplied by the annotator)"),
    "load.filter_placeholders_help": (
        "Non sono refusi: stanno al posto di parole sottintese. Alcuni sono vuoti "
        "([0]), altri portano la parola che l'annotatore ha aggiunto, e altri "
        "ancora un semplice marcatore (GLAUx scrive «E»): li esclude tutti, "
        "perché il file li dichiara tutti allo stesso modo. Escluderli è la "
        "scelta più comune, ma è una scelta, e si può disattivare.",
        "Not typos: they stand in for elided words. Some are empty ([0]), some "
        "carry the word the annotator supplied, and some are a bare marker "
        "(GLAUx writes \"E\"): all are excluded, because the file declares them "
        "all the same way. Leaving them out is the common choice, but it is a "
        "choice, and it can be turned off."),
    "load.expectation": ("Le regole su καί, μέν, δέ, τε, ἤ, ἀλλά",
                         "The rules on καί, μέν, δέ, τε, ἤ, ἀλλά"),
    "load.expectation_corpus": (
        "Confronta ogni occorrenza con il resto di questo corpus",
        "Compare each occurrence with the rest of this corpus"),
    "load.expectation_agdt": (
        "Confronta con la pratica dei corpora AGDT annotati a mano",
        "Compare with the practice of the hand-annotated AGDT corpora"),
    "load.expectation_help": (
        "Queste dieci parole fanno più cose: καί coordina in Σωκράτης καὶ Πλάτων ed è avverbio in καὶ σύ. Quando l'etichetta e la relazione non dicono la stessa cosa, il programma segnala il punto senza proporre correzioni, ma «non dicono la stessa cosa» rispetto a che cosa?\nLa prima scelta risponde: rispetto a questo corpus. Se qui δέ con relazione AuxY porta l'etichetta di particella nel 98% dei casi, le altre occorrenze si guardano. È un controllo di coerenza interna, e vale su qualunque corpus.\nLa seconda risponde: rispetto ai corpora annotati a mano di area Perseus, dove AuxY va con l'avverbio. Serve a misurare quanto un corpus si discosta da quella pratica, che è una domanda diversa: AuxY è avverbio nel 98,1% di Gorman, nel 67,6% di Pedalion e nello 0,7% di GLAUx, e su GLAUx la risposta giusta è «molto lontano», non «sbagliato».",
        "These ten words do several jobs: καί coordinates in Σωκράτης καὶ Πλάτων and is an adverb in καὶ σύ. When the tag and the relation do not say the same thing, the program shows the spot and proposes nothing, but 'do not say the same thing' compared with what?\nThe first choice answers: with this corpus. If δέ under AuxY is tagged as a particle in 98% of its occurrences here, the others are worth a look. That is an internal-consistency check, and it holds on any corpus.\nThe second answers: with the hand-annotated Perseus-style corpora, where AuxY goes with the adverb. It measures how far a corpus departs from that practice, which is a different question: AuxY is an adverb in 98.1% of Gorman, 67.6% of Pedalion and 0.7% of GLAUx, and on GLAUx the right answer is 'very far', not 'wrong'."),
    "load.filter_nongreek": ("Record senza caratteri greci", "Records with no Greek letters"),
    "load.filter_punct": ("Punteggiatura", "Punctuation"),

    # ── Overview page ──────────────────────────────────────────────────
    "overview.title": ("Che cosa c'è in questo corpus", "What is in this corpus"),
    "overview.intro": (
        "I numeri di base, e poi la composizione per autore, opera, periodo e "
        "dialetto. Ogni tabella si può ordinare cliccando sull'intestazione e "
        "salvare in CSV.",
        "The basic figures, then the make-up by author, work, period and dialect. "
        "Every table sorts on a header click and saves to CSV."),
    "overview.documents": ("Documenti", "Documents"),
    "overview.authors": ("Autori", "Authors"),
    "overview.works": ("Opere", "Works"),
    "overview.by_author": ("Per autore", "By author"),
    "overview.by_document": ("Per documento", "By document"),
    "overview.by_period": ("Per periodo", "By period"),
    "overview.by_genre": ("Per genere", "By genre"),
    "overview.by_dialect": ("Per dialetto", "By dialect"),
    "overview.encoding": ("Igiene della codifica", "Encoding hygiene"),
    "overview.unmatched": ("Documenti non riconosciuti", "Unrecognised documents"),
    "overview.unmatched_hint": (
        "Il catalogo non è riuscito ad attribuire questi file a un autore: i "
        "conteggi restano validi, ma non si possono scomporre per autore o per "
        "secolo. Per averli, aggiungi una riga per ciascun file al catalogo dei "
        "metadati (la struttura è descritta nel manuale).",
        "The catalogue could not attribute these files to an author: the counts "
        "stay valid, but they cannot be broken down by author or by century. To "
        "get that, add one row per file to the metadata catalogue (its structure "
        "is described in the manual)."),

    # ── Errors page ────────────────────────────────────────────────────
    "errors.title": ("Trova le segnalazioni", "Diagnostic findings"),
    "errors.intro": (
        "Il programma passa il corpus attraverso cinque famiglie di controlli. Ogni "
        "segnalazione dice che cosa non torna e perché.",
        "The program runs the corpus through five families of check. Every finding "
        "says what looks wrong and why."),
    "errors.howto.1": (
        "Il programma passa il corpus attraverso cinque famiglie di controlli: "
        "l'etichetta morfologica, il lemma, la struttura dell'albero sintattico, "
        "il testo e la codifica, l'accordo grammaticale. Ogni segnalazione dice "
        "che cosa non torna e perché.",
        "The program runs the corpus through five families of check: the "
        "morphological tag, the lemma, the shape of the syntactic tree, the text "
        "and its encoding, grammatical agreement. Every finding says what looks "
        "wrong and why."),
    "errors.run": ("Avvia il controllo", "Run the check"),
    "errors.run_again": ("Ripeti il controllo", "Run the check again"),
    "errors.choose": ("Quali controlli eseguire", "Which checks to run"),
    "errors.family.morphology": ("Etichetta morfologica", "Morphological tag"),
    "errors.family.lemma": ("Lemmatizzazione", "Lemmatisation"),
    "errors.family.syntax": ("Struttura sintattica", "Syntactic structure"),
    "errors.family.text": ("Testo e codifica", "Text and encoding"),
    "errors.family.agreement": ("Accordo e reggenza", "Agreement and government"),
    # The selection box of step 3 and the title of the tab that shows its result carry
    # the same name: they are the same thing seen before and after. “Inconsistencies
    # between similar passages” remains only as the subtitle of step 4, where it names
    # the method — Variation n-gram — and not the object that the reader has in front of
    # them.
    "errors.family.variation": ("Confronti tra annotazioni", "Annotation comparisons"),
    "errors.variation_card": ("Confronti tra annotazioni", "Annotation comparisons"),
    # The wording must not say “in the same context”: identical context is the condition
    # of the context plane alone; the other four planes compare the occurrences wherever
    # they are in the corpus, and saying otherwise would describe a stricter check than
    # the one the program performs.
    "errors.variation_warning": (
        "Il confronto tra annotazioni raggruppa le occorrenze che condividono "
        "lo stesso nucleo — a seconda del piano: una forma, una forma con la "
        "sua parte del discorso, una forma con i vicini identici, una coppia "
        "di parole legate da un arco — e mostra dove l'annotazione differisce. "
        "È l'analisi più lenta e su un corpus grande può richiedere qualche "
        "minuto.",
        "Annotation comparison groups the occurrences that share the same "
        "nucleus — depending on the plane: a form, a form with its part of "
        "speech, a form with identical neighbours, a pair of words joined by "
        "an arc — and shows where the annotation differs. It is the slowest "
        "analysis and on a large corpus it can take a few minutes."),
    "errors.summary": ("Riepilogo", "Summary"),
    "errors.list": ("Elenco delle segnalazioni", "List of findings"),
    "errors.filter_family": ("Famiglia", "Family"),
    "errors.filter_level": ("Classe diagnostica", "Diagnostic class"),
    "errors.filter_rule": ("Regola", "Rule"),
    "errors.filter_all": ("tutte", "all"),
    "errors.none": ("Nessuna segnalazione: il corpus supera tutti i controlli attivi.",
                    "No findings: the corpus passes every active check."),
    "errors.context": ("La frase intera", "The whole sentence"),
    # Two boxes and not one, and the distinction is the point. The first says what the
    # check looks for, and is the canonical description of the catalogue: identical for
    # all the occurrences of the same rule. The second says what this row shows, and
    # changes from one occurrence to another.
    "errors.what": ("Che cosa controlla", "What this check looks for"),
    "errors.diagnosis": ("Che cosa non torna in questa occorrenza",
                         "What does not add up here"),
    # There is no heading "why it is a problem": several rules report a practice of
    # the corpus rather than a defect, and such a heading would tell the reader that
    # it is an error before the text underneath had a chance to say otherwise.
    "errors.field.form": ("Forma", "Form"),
    "errors.field.postag": ("PoS-tag", "PoS-tag"),
    "errors.field.lemma": ("Lemma", "Lemma"),
    "errors.field.relation": ("Relazione", "Relation"),
    "errors.field.head": ("Testa", "Head"),
    "errors.evidence": ("Le occorrenze nel corpus", "The occurrences in the corpus"),
    "errors.why": ("Che cosa cerca questa regola", "What this rule looks for"),
    "errors.grade": ("Come va letta", "How to read it"),
    "errors.suggestion": ("Correzione proposta", "Proposed correction"),
    "errors.select_row": ("Seleziona una riga per vederla nel suo contesto.",
                          "Select a row to see it in context."),
    "errors.levels_explained": ("Come sono classificate le segnalazioni",
                               "How findings are classified"),

    # ── Revised-corpus page ────────────────────────────────────────────
    "gold.title": ("La versione revisionata da te",
                   "The version you revised"),
    "gold.howto.1": (
        "Le tue decisioni producono una seconda versione del corpus: il "
        "corpus originale resta intatto e serve da termine di confronto. Da "
        "qui puoi esportarla, metterla da parte per riprenderla domani, e "
        "vedere che cosa cambia quando Stanza e UDPipe vengono misurati "
        "contro la tua versione invece che contro l'originale.\n\n"
        "Il programma non chiama questa versione «gold standard», e la parola "
        "non compare da nessun'altra parte nell'interfaccia. Un gold standard "
        "è un corpus di riferimento validato, e non è quello che esce da qui: "
        "quello che esce da qui è un corpus rivisto da una persona, con "
        "scritto che cosa ha cambiato e perché. Che diventi un riferimento è "
        "una decisione che si prende fuori dal programma.",
        "Your decisions produce a second version of the corpus: the original "
        "corpus stays untouched and serves as the point of comparison. From "
        "here you can export that version, put it aside for tomorrow, and see "
        "what changes when Stanza and UDPipe are measured against your "
        "version instead of the original.\n\n"
        "The program does not call this version a “gold standard”, and the "
        "phrase appears nowhere else in the interface. A gold standard is a "
        "validated reference corpus, and that is not what comes out of here: "
        "what comes out of here is a corpus revised by a person, with a "
        "record of what changed and why. Whether it becomes a reference is a "
        "decision taken outside the program."),

    "gold.metric.tokens": ("Record importati", "Imported records"),
    "gold.metric.manual": ("Correzioni manuali", "Manual corrections"),
    "gold.metric.changed": ("Record cambiati", "Records changed"),
    "gold.metric.share": ("Quota del corpus", "Share of the corpus"),

    "gold.state.identical": (
        "La versione revisionata al momento è identica all'originale: non è stata "
        "cambiata nessuna parola.",
        "The revised corpus is currently identical to the original: no word "
        "has been changed."),

    "gold.export.title": ("Esporta la versione revisionata",
                          "Export the revised corpus"),
    "gold.export.hint": (
        "Esce sempre la versione revisionata da te, mai l'originale. XML AGDT per "
        "chi resta nella tradizione Perseus, CSV per un foglio di calcolo, "
        "CoNLL-U per gli strumenti di Universal Dependencies.",
        "What is written out is always your revised corpus, never the "
        "original. AGDT XML for the Perseus tradition, CSV for a spreadsheet, "
        "CoNLL-U for Universal Dependencies tooling."),
    "gold.export.xml": ("Esporta in XML AGDT", "Export as AGDT XML"),
    "gold.export.csv": ("Esporta in CSV", "Export as CSV"),
    "gold.export.conllu": ("Esporta in CoNLL-U", "Export as CoNLL-U"),

    "gold.keep.title": ("Conserva la versione revisionata",
                        "Keep the revised corpus"),
    "gold.keep.hint": (
        "Un file solo, che contiene la versione revisionata e le decisioni che lo "
        "hanno prodotto. Si mette da parte, si manda a un collega, si "
        "ricarica più avanti senza perdere niente.",
        "A single file holding the revised corpus and the decisions that "
        "produced it. Put it aside, send it to a colleague, load it back "
        "later without losing anything."),
    "gold.keep.filter": ("Versione revisionata", "Revised corpus"),
    "gold.keep.save": ("Salva sul computer", "Save to disk"),
    "gold.keep.load": ("Ricarica una versione salvata", "Load a saved version"),

    "gold.compare.title": ("Confronta", "Compare"),
    "gold.compare.hint": (
        "Che cosa è cambiato fra l'originale e la tua versione, e quanto "
        "concordano Stanza e UDPipe con l'uno e con l'altro. Se l'accordo si "
        "sposta, non è il modello a essere cambiato: è il riferimento con cui "
        "lo misuri.",
        "What changed between the original and your version, and how much Stanza "
        "and UDPipe agree with each. If agreement moves, the model has not "
        "changed: the yardstick has."),
    "gold.compare.open": (
        "Apri il confronto fra originale, versione revisionata, Stanza e UDPipe",
        "Open the comparison of original, revised corpus, Stanza and UDPipe"),

    "gold.tab.diff": ("Che cosa è cambiato", "What changed"),
    "gold.tab.models": ("I modelli contro i due riferimenti",
                        "The models against both references"),
    "gold.tab.models.hint": (
        "Nessun modello è stato rieseguito: quello che il modello ha scritto "
        "era già salvato, e viene semplicemente riconfrontato con la versione "
        "revisionata. Il disaccordo con un modello è un segnale da guardare, non "
        "la prova che l'annotazione sia sbagliata.",
        "No model was re-run: what the model wrote was already saved, and is "
        "simply re-compared against the revised corpus. Disagreement with a "
        "model is a signal worth looking at, not proof that the annotation is "
        "wrong."),

    "gold.msg.identical_confirm": (
        "Non hai ancora cambiato nessuna parola: il file che esce sarà "
        "identico al corpus originale.\n\nVuoi esportarlo lo stesso?",
        "You have not changed a single word yet: the exported file will be "
        "identical to the original corpus.\n\nExport it anyway?"),
    "gold.msg.xml_done": ("Scritti {n} file XML in {path}",
                          "Wrote {n} XML files to {path}"),
    "gold.msg.csv_done": ("Scritte {n} parole in {path}",
                          "Wrote {n} words to {path}"),
    "gold.msg.conllu_done": ("Scritte {n} parole in {path}",
                             "Wrote {n} words to {path}"),
    "gold.msg.saved": ("Versione salvata in {path}", "Version saved to {path}"),
    "gold.msg.load_confirm": (
        "La versione salvata sostituirà il corpus revisionato e le correzioni "
        "di questa esecuzione. Il corpus originale non viene toccato.\n\n"
        "Vuoi procedere?",
        "The saved version will replace the revised corpus and the corrections "
        "of this run. The original corpus is left untouched.\n\nProceed?"),
    "gold.msg.loaded": ("Versione ricaricata: {n} parole cambiate, corpus {corpus}",
                        "Version loaded: {n} words changed, corpus {corpus}"),
    "gold.msg.compare_done": ("Confronto aggiornato.", "Comparison updated."),
    "gold.msg.no_models": (
        "Nessun modello è stato eseguito su questo corpus: esegui prima "
        "Stanza o UDPipe nella scheda «Confronta i modelli».",
        "No model has been run on this corpus: run Stanza or UDPipe first, in "
        "the «Compare the models» step."),

    "review.gold_ready.title": ("Versione revisionata",
                                "Revised corpus"),
    "review.gold_ready.open": ("Vai alla versione revisionata →",
                               "Go to the revised corpus →"),

    "review.select_all": ("Attiva tutte", "Turn all on"),
    "review.select_none": ("Disattiva tutte", "Turn all off"),
    "review.manual": ("Correzione manuale", "Manual correction"),
    "review.form": ("Forma", "Form"),
    "review.lemma": ("Lemma", "Lemma"),
    "review.postag": ("Etichetta", "Tag"),
    "review.relation": ("Relazione", "Relation"),
    "review.new_lemma": ("Lemma corretto", "Corrected lemma"),
    "review.new_postag": ("Etichetta corretta", "Corrected tag"),
    "review.use_suggestion": ("Usa la correzione proposta", "Use the proposed correction"),
    "review.save": ("Salva questa correzione", "Save this correction"),
    "review.saved": ("Correzione salvata.", "Correction saved."),
    "review.applied": ("Correzioni applicate.", "Corrections applied."),
    "review.my_corrections": ("Le mie correzioni", "My corrections"),
    "review.before_after": ("Prima e dopo", "Before and after"),
    "review.changed": ("Record modificati", "Changed records"),
    "review.export": ("Esporta la versione revisionata", "Export the revised corpus"),
    "overview.conllu": ("Esporta in CoNLL-U", "Export to CoNLL-U"),
    "overview.conllu.done": ("Scritti {n} file CoNLL-U in {path}",
                            "Wrote {n} CoNLL-U files to {path}"),
    "review.export_conllu": ("CoNLL-U", "CoNLL-U"),
    "review.export_conllu.hint": (
        "Formato standard di Universal Dependencies. L'annotazione AGDT resta "
        "invariata: la relazione va in DEPREL, il tag a nove caratteri in XPOS, "
        "la morfologia che contiene viene scritta per esteso in FEATS.",
        "The Universal Dependencies standard format. The AGDT annotation is kept "
        "as it is: the relation goes in DEPREL, the nine-character tag in XPOS, "
        "and the morphology it encodes is spelled out in FEATS."),
    "review.export_xml": ("XML AGDT", "AGDT XML"),
    "review.export_csv": ("CSV per frase", "One CSV per sentence"),
    "review.nothing_written": (
        "Scrivi almeno un lemma o un'etichetta prima di salvare.",
        "Write at least a lemma or a tag before saving."),

    # ── Search page ────────────────────────────────────────────────────
    "search.title": ("Cerca nel corpus", "Search the corpus"),
    "search.form": ("Forma", "Form"),
    "search.lemma": ("Lemma", "Lemma"),
    "search.mode": ("Come cercare", "How to match"),
    "search.ignore_accents": ("Ignora accenti e spiriti", "Ignore accents and breathings"),
    "search.morphology": ("Morfologia", "Morphology"),
    "search.any": ("qualsiasi", "any"),
    "search.relation": ("Funzione sintattica", "Syntactic function"),
    "search.head_lemma": ("Lemma della testa", "Head lemma"),
    "search.filters": ("Limita a…", "Restrict to…"),
    "search.go": ("Cerca", "Search"),
    "search.clear": ("Azzera", "Clear"),
    "search.results": ("Risultati", "Results"),
    "search.count": ("occorrenze trovate", "hits found"),
    "search.aggregate": ("Trasforma in tabella di frequenza", "Turn into a frequency table"),
    "search.group_by": ("Raggruppa per", "Group by"),
    "search.constructions": ("Costruzioni greche", "Greek constructions"),
    "search.constructions_hint": (
        "Ricerche già pronte per le costruzioni che si studiano in sintassi greca.",
        "Ready-made searches for the constructions a Greek syntax course covers."),
    "search.who_uses": ("Chi la usa di più", "Who uses it most"),
    "search.who_uses_hint": (
        "Il conteggio grezzo premia sempre l'autore di cui c'è più testo: qui "
        "accanto trovi anche la frequenza ogni diecimila record attivi, che è il numero "
        "confrontabile.",
        "A raw count always favours the author there is most of: next to it you also "
        "get the rate per ten thousand active records, which is the comparable figure."),
    "search.suspicious": ("Segnala i risultati sospetti", "Flag suspicious hits"),
    "search.suspicious_hint": (
        "Evidenzia le righe in cui questa ricerca incrocia una segnalazione del "
        "controllo errori: il modo più rapido per scoprire irregolarità nuove partendo "
        "da una domanda linguistica.",
        "Highlights rows where this search meets a finding from the error check: the "
        "quickest way to discover new irregularities starting from a linguistic question."),

    # ── Statistics page ────────────────────────────────────────────────
    "stats.dimension": ("Dimensione", "Dimension"),
    "stats.value": ("Valore", "Value"),
    "stats.dim.corpus": ("Intero corpus", "Whole corpus"),
    "stats.dim.documento": ("Documento", "Document"),
    "stats.dim.autore": ("Autore", "Author"),
    "stats.dim.opera": ("Opera", "Work"),
    "stats.dim.periodo": ("Periodo", "Period"),
    "stats.dim.genere": ("Genere", "Genre"),
    "stats.dim.dialetto": ("Dialetto", "Dialect"),
    "stats.dim.missing": ("Metadati non disponibili per: {0}.",
                          "Metadata not available for: {0}."),
    "stats.tab_morfologia": ("Morfologia", "Morphology"),
    "stats.tab_sintassi": ("Sintassi", "Syntax"),
    "stats.morf.hint": (
        "Quante volte ricorre ciascun valore delle sei posizioni morfologiche, "
        "nel gruppo scelto. Il denominatore è scritto sopra ogni tabella: i modi, "
        "i tempi, le diatesi e le persone si contano sui verbi, i casi sulle "
        "categorie che il caso lo portano.",
        "How often each value of the six morphological slots occurs in the "
        "chosen group. The denominator is written above each table: moods, "
        "tenses, voices and persons are counted on verbs, cases on the "
        "categories that can carry case."),
    "stats.sin.hint": (
        "Le funzioni sintattiche del gruppo scelto e le misure dell'albero. "
        "Entrano soltanto le frasi per cui il corpus ha calcolato gli archi.",
        "The syntactic functions of the chosen group and the tree measures. "
        "Only sentences whose arcs the corpus computed are included."),
    "stats.sin.misure": ("I legami di dipendenza", "The dependency links"),
    "stats.sin.esclusioni": (
        "Frasi entrate nel conto: {0}. Frasi lasciate fuori: {1}. {2}",
        "Sentences included: {0}. Sentences left out: {1}. {2}"),
    "stats.freq.hint": (
        "La lista del gruppo scelto, normalizzata ogni diecimila parole di "
        "quel gruppo.",
        "The list for the chosen group, normalised per ten thousand words of "
        "that group."),
    "stats.freq.tfidf": (
        "Ordinata per TF-IDF: un lemma presente in quasi tutti i documenti pesa "
        "meno di uno altrettanto frequente ma concentrato in pochi. Nessuna "
        "parola è stata tolta per questo, solo spostata più in basso.",
        "Ranked by TF-IDF: a lemma found in nearly every document weighs less "
        "than an equally frequent one concentrated in a few. No word is removed "
        "by this, only moved down."),
    "stats.freq.plain": (
        "Ordinata per frequenza. Con un documento solo la frequenza documentaria "
        "non distingue niente, e il peso TF-IDF non è stato usato.",
        "Ranked by frequency. With a single document, document frequency "
        "distinguishes nothing, and the TF-IDF weight was not used."),
    "stats.field.lemma": ("lemmi", "lemmas"),
    "stats.field.form": ("forme", "forms"),
    "stats.stop.advanced": ("Opzioni avanzate", "Advanced options"),
    "stats.stop.add": ("Aggiungi lemmi", "Add lemmas"),
    "stats.stop.remove": ("Togli lemmi", "Remove lemmas"),
    "stats.stop.reset": ("Ripristina", "Reset"),
    "stats.stop.export": ("Esporta lista", "Export list"),
    "stats.stop.import": ("Importa lista", "Import list"),
    "stats.stop.which": ("Quali lemmi? Separali con uno spazio o una virgola.",
                         "Which lemmas? Separate them with a space or a comma."),
    "stats.stop.excluded": ("Parole escluse", "Excluded words"),
    "stats.stop.report": ("Il profilo ha lasciato fuori {0} parole, il {1}% del gruppo.",
                          "The profile left out {0} words, {1}% of the group."),
    "stats.den.pos": ("Denominatore: le {0} parole analizzate del gruppo.",
                      "Denominator: the {0} analysed words of the group."),
    "stats.den.casi": ("Denominatore: le {0} parole che portano un caso.",
                       "Denominator: the {0} words that carry a case."),
    "stats.den.modi": ("Denominatore: le {0} parole verbali che portano un modo.",
                       "Denominator: the {0} verbal words that carry a mood."),
    "stats.den.tempi": ("Denominatore: le {0} parole verbali che portano un tempo.",
                        "Denominator: the {0} verbal words that carry a tense."),
    "stats.den.diatesi": ("Denominatore: le {0} parole verbali che portano una diatesi.",
                          "Denominator: the {0} verbal words that carry a voice."),
    "stats.den.persone": ("Denominatore: le {0} parole verbali che portano una persona.",
                          "Denominator: the {0} verbal words that carry a person."),
    "stats.par.associazioni": ("Associazioni", "Associations"),
    "stats.par.grafie": ("Grafie del lemma", "Spellings of the lemma"),
    "stats.par.forme": ("Forme", "Forms"),
    "stats.par.postag": ("Etichette", "Tags"),
    "stats.par.relazioni": ("Relazioni", "Relations"),
    "stats.par.teste": ("Da che cosa dipende", "What governs it"),
    "stats.par.dipendenti": ("Che cosa regge", "What it governs"),
    "stats.par.documenti": ("Documenti", "Documents"),
    "stats.par.esempi": ("Esempi", "Examples"),
    "stats.par.trovato": ("{0} occorrenze nel gruppo scelto.",
                          "{0} occurrences in the chosen group."),
    "stats.title": ("Il corpus in numeri", "The corpus in numbers"),
    "stats.intro": (
        "Le misure che un classicista riconosce, tutte calcolabili per autore, "
        "genere, periodo o dialetto.",
        "The measures a classicist recognises, all available by author, genre, "
        "period or dialect."),
    "stats.howto.1": (
        "Le misure che un classicista riconosce: distribuzione dei casi e dei "
        "modi, densità dell'articolo, rapporto participi/verbi finiti, indice di "
        "ottativo, ricchezza lessicale, complessità del periodo. Tutte calcolabili "
        "per autore, genere, periodo o dialetto.",
        "The measures a classicist recognises: case and mood distribution, article "
        "density, participles per finite verb, optative index, lexical richness, "
        "sentence complexity. All available by author, genre, period or dialect."),
    "stats.group_by": ("Confronta per", "Compare by"),
    "stats.tab_syntax": ("Sintassi", "Syntax"),
    "stats.tab_frequency": ("Liste di frequenza", "Frequency lists"),
    "stats.tab_sketch": ("Profilo di un lemma", "Lemma profile"),
    "stats.compute": ("Calcola", "Compute"),
    "stats.sketch_lemma": ("Lemma da profilare", "Lemma to profile"),
    "charts.title": ("Grafici", "Charts"),
    "charts.intro": (
        "Sintesi visive dei conteggi che il programma ha già prodotto: i grafici "
        "non calcolano niente per conto proprio.",
        "Visual summaries of the counts the program has already produced: the "
        "charts compute nothing of their own."),
    "charts.howto.1": (
        "Sintesi visive dei conteggi che il programma ha già prodotto: i grafici "
        "non calcolano niente per conto proprio. Ognuno si può ingrandire, "
        "salvare in PNG e copiare, e sotto ciascuno c'è scritto che cosa conta e "
        "su quale denominatore. Il pulsante in fondo li genera tutti a 300 dpi, "
        "con le didascalie già scritte.",
        "Visual summaries of the counts the program has already produced: the "
        "charts compute nothing of their own. Each can be enlarged, saved as PNG "
        "and copied, and under each is written what it counts and on which "
        "denominator. The button at the bottom generates them all at 300 dpi, "
        "with the captions already written."),
    "charts.pick": ("Quale grafico", "Which chart"),
    "charts.save": ("Salva questo grafico", "Save this chart"),
    "charts.export_all": ("Esporta tutti i grafici", "Export all charts"),
    "charts.export_all.hint": ("A 300 dpi, con le didascalie già scritte.",
                              "At 300 dpi, with the captions already written."),
    "charts.empty": ("Questo grafico non ha niente da mostrare",
                     "This chart has nothing to show"),
    "chart.needs.findings": (
        "Serve un giro di controlli: torna al passo «Trova le segnalazioni» e "
        "premi «Esegui i controlli».",
        "This needs a run of the checks: go back to «Diagnostic findings» and "
        "press «Run the checks»."),
    "chart.needs.arcs": (
        "Servono gli archi sintattici: eseguili con la famiglia «Struttura "
        "sintattica» al passo «Trova le segnalazioni».",
        "This needs the syntactic arcs: run them with the «Syntactic "
        "structure» family at the «Diagnostic findings» step."),
    "chart.needs.models": (
        "Serve almeno un modello: esegui Stanza o UDPipe al passo «Confronta i "
        "modelli».",
        "This needs at least one model: run Stanza or UDPipe at the «Compare "
        "the models» step."),
    "chart.needs.both_models": (
        "Servono tutt'e due i modelli: esegui Stanza e UDPipe al passo "
        "«Confronta i modelli».",
        "This needs both models: run Stanza and UDPipe at the «Compare the "
        "models» step."),
    "charts.failed.title": ("Questo grafico non si può disegnare",
                           "This chart cannot be drawn"),
    "charts.nothing_to_save": ("Non c'è nessun grafico da salvare",
                               "There is no chart to save"),
    "charts.nothing_to_copy": ("Non c'è nessun grafico da copiare",
                               "There is no chart to copy"),
    "charts.export_failed": ("L'esportazione non è riuscita: {0}",
                            "The export failed: {0}"),
    "charts.export_needs_run": ("Carica prima un corpus: non c'è niente da esportare.",
                                "Load a corpus first: there is nothing to export."),
    "charts.exported": ("Figure salvate in", "Figures saved in"),

    # ── Models page ────────────────────────────────────────────────────
    "models.title": ("Confronta il corpus con i modelli automatici",
                     "Compare the corpus with automatic models"),
    "models.intro": (
        "Stanza e UDPipe rianalizzano gli stessi record e il programma allinea i "
        "risultati. Nessuno dei due modelli è trattato come riferimento.",
        "Stanza and UDPipe re-analyse the same records and the program lines up the "
        "results. Neither model is treated as a reference."),
    "models.howto.1": (
        "Stanza e UDPipe rianalizzano gli stessi record e il programma allinea i "
        "risultati. Nessuno dei due modelli è trattato come riferimento: un "
        "modello che dice una cosa diversa dal corpus non dimostra che il corpus "
        "abbia torto. Dove i due modelli concordano fra loro e non con il corpus, "
        "il caso è mostrato come punto da rileggere, non come errore accertato.",
        "Stanza and UDPipe re-analyse the same records and the program lines up the "
        "results. Neither model is treated as a reference: a model that says "
        "something different from the corpus does not show that the corpus is "
        "wrong. Where the two models agree with each other and not with the "
        "corpus, the case is shown as a point to reread, not as an established "
        "error."),
    "models.run_stanza": ("Esegui Stanza", "Run Stanza"),
    "models.run_udpipe": ("Esegui UDPipe", "Run UDPipe"),
    "models.first_time": (
        "Al primo avvio il programma scarica i modelli linguistici: circa 60 MB, "
        "una volta sola.",
        "On first use the program downloads the language models: about 60 MB, once."),
    "models.not_installed": ("non installato", "not installed"),
    # The two notices that appear when a model is missing. They must name the installer
    # with which GCP itself is installed, not another one: whoever followed the
    # instruction literally would otherwise get nowhere.
    "models.err.stanza_missing": (
        "Stanza non è installato. Si aggiunge con `pip install -e \".[models]\"`, "
        "oppure da solo con `pip install stanza`.",
        "Stanza is not installed. Add it with `pip install -e \".[models]\"`, "
        "or on its own with `pip install stanza`."),
    "models.err.udpipe_missing": (
        "UDPipe non è installato. Si aggiunge con `pip install -e \".[models]\"`, "
        "oppure da solo con `pip install ufal.udpipe`.",
        "UDPipe is not installed. Add it with `pip install -e \".[models]\"`, "
        "or on its own with `pip install ufal.udpipe`."),
    "models.ready": ("pronto", "ready"),
    "models.tab_overview": ("Quadro d'insieme", "Overview"),
    "models.tab_three_way": ("Corpus, Stanza, UDPipe", "Corpus, Stanza, UDPipe"),
    "models.tab_slots": ("Posizione per posizione", "Slot by slot"),
    "models.tab_divergence": ("Disaccordi fra i modelli", "Model disagreements"),
    "models.tab_by_author": ("Per autore", "By author"),
    "models.needs_both": (
        "Esegui entrambi i modelli per vedere questo confronto.",
        "Run both models to see this comparison."),

    # ── Rules page ─────────────────────────────────────────────────────
    "rules.schema": ("Lo schema AGDT", "The AGDT scheme"),
    "rules.relations": ("Le funzioni sintattiche", "The syntactic functions"),

    # ── Shared table widget ────────────────────────────────────────────
    "page.howto": ("Come si legge questa pagina", "How to read this page"),
    "page.howto.close": ("Chiudi la spiegazione", "Close the explanation"),
    "table.filter": ("Filtra", "Filter"),
    "table.rows": ("righe", "rows"),
    "table.of": ("di", "of"),
    "table.export": ("Salva in CSV", "Save as CSV"),
    "table.columns": ("Colonne", "Columns"),
    "table.copy": ("Copia", "Copy"),
    "table.empty": ("Nessun dato da mostrare", "Nothing to show yet"),
    "empty.models": ("Nessun confronto con i modelli",
                     "No comparison with the models yet"),
    "empty.models.hint": (
        "Esegui Stanza o UDPipe qui sopra: il confronto compare qui.",
        "Run Stanza or UDPipe above: the comparison appears here."),
    "empty.findings": ("Nessuna segnalazione", "No findings"),
    "empty.findings.hint": (
        "Esegui i controlli qui sopra, oppure allarga i filtri.",
        "Run the checks above, or widen the filters."),
    "empty.variation": ("Nessun nucleo in questo piano",
                        "No nucleus in this plane"),
    "empty.variation.hint": (
        "O il corpus non ne ha, o il giro non li ha ancora cercati.",
        "Either the corpus has none, or the run has not looked for them yet."),
    "table.no_match": ("Il filtro non lascia passare nessuna riga",
                       "The filter matches no rows"),
    "table.no_match.hint": ("Svuota il campo di ricerca per rivedere tutte le righe.",
                            "Clear the search box to see every row again."),
    "table.computing": ("Calcolo in corso…", "Computing…"),
    "table.saved": ("Salvato in", "Saved to"),
    # The acknowledgement of the table commands: copying and saving must not finish in
    # silence, so that whoever pressed knows whether they succeeded.
    "table.copied": ("Copiate {0} righe", "{0} rows copied"),
    "table.copy_failed": ("Non sono riuscito a copiare: {0}",
                          "Could not copy: {0}"),
    "table.saved_to": ("Salvato: {0}", "Saved: {0}"),
    "table.save_failed": ("Non sono riuscito a salvare: {0}",
                          "Could not save: {0}"),
    "table.save_cancelled": ("Salvataggio annullato", "Save cancelled"),
    "table.nothing_to_copy": ("Non c'è niente da copiare",
                              "There is nothing to copy"),
    "table.nothing_to_save": ("Non c'è niente da salvare",
                              "There is nothing to save"),
    "table.nothing_to_do": ("La tabella è vuota: non c'è niente su cui agire.",
                            "The table is empty: there is nothing to act on."),
    "table.capped": ("mostrate le prime", "showing the first"),
    # ── Chart names (they fill the list on the Charts page) ────────────
    # ── the variation-nucleus page ─────────────────────────────────────
    "variation.title": ("Variation n-gram", "Variation n-gram"),
    "variation.intro": (
        "Qui GCP raccoglie forme, contesti o coppie che nel corpus ricevono "
        "più di un'annotazione: la tabella serve a vedere dove il corpus varia "
        "e quanto è frequente ciascuna alternativa.",
        "Here GCP groups forms, contexts, or pairs that receive more than one "
        "annotation in the corpus: the table shows where the corpus varies and "
        "how frequent each alternative is."),
    "variation.howto.1": (
        "Un nucleo di variazione nasce quando la stessa chiave analitica è "
        "associata nel corpus a più di un valore annotativo. Questo non "
        "significa automaticamente che una delle annotazioni sia sbagliata: "
        "serve a poter controllare i casi concreti.",
        "A variation nucleus arises when the same analytical key is associated "
        "in the corpus with more than one annotation value. This does not "
        "automatically mean that one annotation is wrong: it is there so that "
        "the individual cases can be inspected."),
    "variation.howto.2": (
        "Unità: il nucleo di variazione. La chiave cambia nei cinque piani, e "
        "con la chiave cambia il valore: una forma con la sua etichetta "
        "morfologica, una forma con una singola posizione dell'etichetta, un "
        "trigramma con l'etichetta della parola centrale, una coppia sintattica "
        "con la relazione e la direzione, una forma con il lemma. Si contano "
        "sulle parole del testo, e una chiave con un valore solo non è un "
        "nucleo. Il valore vuoto non conta come valore: l'annotazione mancante "
        "è un'altra cosa, e il catalogo la segnala per conto suo.",
        "Unit: the variation nucleus. The key changes across the five planes, "
        "and with the key the value changes too: a form with its morphological "
        "tag, a form with a single tag slot, a trigram with the tag of the "
        "central word, a syntactic pair with its relation and direction, a form "
        "with its lemma. They are counted on the words of the text, and a key "
        "with a single value is not a nucleus. An empty value does not count as "
        "a value: a missing annotation is a different thing, and the catalogue "
        "reports it on its own account."),
    "variation.howto.3": (
        "I cinque piani non vengono tutti dalla stessa fonte. Il piano della "
        "morfologia e quello del contesto derivano dal metodo della variation "
        "n-gram di Dickinson e Meurers (2003a); il piano delle dipendenze "
        "adatta la rappresentazione a coppie di Boyd et al. (2008), senza i "
        "nuclei NIL e senza le euristiche di contesto di quel lavoro; il piano "
        "delle posizioni dell'etichetta e quello dei lemmi sono estensioni di "
        "GCP, e non hanno una fonte. Nessuno dei cinque è una validazione "
        "indipendente dei controlli diagnostici: sono un'analisi separata, che "
        "guarda gli stessi dati da un'altra parte.",
        "The five planes do not all come from the same source. The morphology "
        "and context planes derive from the variation n-gram method of "
        "Dickinson and Meurers (2003a); the dependency plane adapts the "
        "pair-based representation of Boyd et al. (2008), without that work's "
        "NIL nuclei and context heuristics; the tag-slot and lemma planes are "
        "GCP extensions, and have no source. None of the five is an "
        "independent validation of the diagnostic checks: they are a separate "
        "analysis, looking at the same data from another side."),
    "variation.counts": ("Nuclei per piano", "Nuclei by plane"),
    "variation.total": ("in tutto", "in all"),
    "variation.compute": ("Cerca i nuclei", "Find the nuclei"),
    "variation.done": ("I nuclei vengono dal giro caricato.",
                       "The nuclei come from the loaded run."),
    "variation.empty": (
        "Nessun nucleo: o il corpus non ne ha, o il giro non li ha ancora cercati.",
        "No nuclei: either the corpus has none, or the run has not looked for "
        "them yet."),
    "variation.plane.morfologia": ("Morfologia", "Morphology"),
    "variation.plane.posizioni": ("Posizioni dell'etichetta", "Tag slots"),
    "variation.plane.contesto": ("Contesto", "Context"),
    "variation.plane.dipendenze": ("Dipendenze", "Dependencies"),
    "variation.plane.lemmi": ("Lemmi", "Lemmas"),

    # ══ The tables of the cores: headers and explanations, plane by plane ══
    #
    # Five tables share the names of the columns but not their meaning: in the lemma
    # plane the column “labels” contains lemmas, in the positions plane it contains a
    # single character.  A single translation would be false in three planes out of
    # five, and this is why the headers are per plane.  The name of the datum does not
    # change: what is read changes.
    #
    #   varhdr.<plane>.<column>   the header, where the general one is false
    #   varcol.<column>           the general explanation
    #   varcol.<plane>.<column>   the explanation, where the plane changes it


    # ── the values of the column “tipo” (type) of the tables of the cores ───
    #
    # The backend writes them in Italian, because they are data and not captions: they
    # are translated here, on a copy, just before they are drawn.
    "value.posizione 1 — Parte del discorso": ("posizione 1 — Parte del discorso",
        "tag position 1 — Part of speech"),
    "value.posizione 2 — Persona": ("posizione 2 — Persona",
        "tag position 2 — Person"),
    "value.posizione 3 — Numero": ("posizione 3 — Numero",
        "tag position 3 — Number"),
    "value.posizione 4 — Tempo": ("posizione 4 — Tempo",
        "tag position 4 — Tense"),
    "value.posizione 5 — Modo": ("posizione 5 — Modo",
        "tag position 5 — Mood"),
    "value.posizione 6 — Diatesi": ("posizione 6 — Diatesi",
        "tag position 6 — Voice"),
    "value.posizione 7 — Genere": ("posizione 7 — Genere",
        "tag position 7 — Gender"),
    "value.posizione 8 — Caso": ("posizione 8 — Caso",
        "tag position 8 — Case"),
    "value.posizione 9 — Grado": ("posizione 9 — Grado",
        "tag position 9 — Degree"),
    "value.contesto ±1": ("contesto ±1", "context ±1"),
    "value.contesto ±2": ("contesto ±2", "context ±2"),

    "vartab.howto": ("Come leggere la tabella", "How to read this table"),
    "vartab.howto.close": ("Chiudi", "Close"),
    "vartab.howto.title": ("Che cosa dice ogni colonna",
                              "What each column says"),

    # ── the headers that change from one plane to another ──────────────
    "varhdr.posizioni.tipo": ("posizione del tag", "tag position"),
    "varhdr.posizioni.n_etichette": ("valori distinti", "distinct values"),
    "varhdr.posizioni.etichette": ("valori", "values"),
    "varhdr.dipendenze.n_etichette": ("relazioni distinte", "distinct relations"),
    "varhdr.dipendenze.etichette": ("relazioni", "relations"),
    "varhdr.lemmi.n_etichette": ("lemmi distinti", "distinct lemmas"),
    "varhdr.lemmi.etichette": ("lemmi", "lemmas"),

    # ── the general explanations ───────────────────────────────────────
    "varcol.nucleo": (
        "È l'elemento che GCP sta confrontando. A seconda della scheda può "
        "essere una forma, un contesto, una coppia di parole o una "
        "combinazione forma–PoS. Compare qui perché nel corpus è associato a "
        "più di un valore annotativo.",
        "The item being compared by GCP. Depending on the tab, it may be a "
        "form, a context, a word pair, or a form–POS combination. It appears "
        "here because the corpus associates it with more than one annotation "
        "value."),
    "varcol.chiave": (
        "La rappresentazione con cui il programma raggruppa le occorrenze da "
        "confrontare: due occorrenze finiscono nello stesso nucleo quando "
        "hanno la stessa chiave.",
        "The representation the program uses to group together the "
        "occurrences that are to be compared: two occurrences fall into the "
        "same nucleus when they have the same key."),
    "varcol.n_etichette": (
        "Quanti valori annotativi diversi sono stati trovati per questo "
        "nucleo. Se il valore è 2, il corpus lo annota in due modi diversi.",
        "The number of different annotation values found for this nucleus. A "
        "value of 2 means that the corpus annotates it in two different ways."),
    "varcol.etichette": (
        "Quali sono, concretamente, le diverse annotazioni trovate nel corpus.",
        "The actual annotation values found in the corpus."),
    "varcol.occorrenze": (
        "Quante occorrenze del nucleo sono state considerate complessivamente "
        "in questo piano.",
        "The total number of occurrences of this nucleus considered in this "
        "analysis plane."),
    "varcol.distribuzione": (
        "Quante volte compare ciascuna delle annotazioni alternative. Permette "
        "di vedere subito se due analisi sono entrambe frequenti oppure se una "
        "è molto comune e l'altra rara.",
        "How often each alternative annotation occurs. This makes it possible "
        "to see whether both analyses are common or whether one is frequent "
        "and the other rare."),
    "varcol.esempi": (
        "Un caso concreto del corpus in cui compare questo nucleo, indicato "
        "con il documento e il numero della frase. Serve per tornare dalla "
        "statistica alla frase reale.",
        "A concrete corpus occurrence of this nucleus, given as document and "
        "sentence number, allowing the user to move from the summary back to "
        "the actual sentence."),
    "varcol.tipo": (
        "Da quale piano viene la riga.",
        "Which plane the row comes from."),

    # ── core: what it is, tab by tab ───────────────────────────────────
    "varcol.morfologia.nucleo": (
        "Qui il nucleo è una stessa forma del testo che compare con più di "
        "un'etichetta morfologica completa, cioè con più di una stringa di "
        "nove caratteri.",
        "Here the nucleus is one and the same form of the text appearing with "
        "more than one complete morphological tag, that is with more than one "
        "nine-character string."),
    "varcol.posizioni.nucleo": (
        "Qui il nucleo è una stessa forma osservata in una sola posizione "
        "dell'etichetta morfologica, quando in quella posizione il corpus "
        "mette più di un valore. La colonna «posizione del tag» dice di quale "
        "delle nove posizioni parla la riga.",
        "Here the nucleus is one and the same form observed in a single "
        "position of the morphological tag, when the corpus puts more than one "
        "value in that position. The “tag position” column says which of the "
        "nine positions the row is about."),
    "varcol.contesto.nucleo": (
        "Qui il nucleo è la parola centrale di un trigramma: le tre parole "
        "consecutive sono le stesse e la parola in mezzo riceve più di "
        "un'etichetta. È il piano più stretto, e di solito il più utile.",
        "Here the nucleus is the central word of a trigram: the three "
        "consecutive words are the same and the middle word receives more than "
        "one tag. It is the narrowest plane, and usually the most useful."),
    "varcol.dipendenze.nucleo": (
        "Qui il nucleo è una stessa coppia di parole legate da un arco di "
        "dipendenza, quando fra le due il corpus annota più di una "
        "combinazione di relazione e direzione. La lettera finale dice dove "
        "sta la testa: L a sinistra, R a destra.",
        "Here the nucleus is one and the same pair of words linked by a "
        "dependency arc, when the corpus annotates more than one combination "
        "of relation and direction between them. The final letter says where "
        "the head is: L to the left, R to the right."),
    "varcol.lemmi.nucleo": (
        "Qui il nucleo è una stessa combinazione di forma e parte del "
        "discorso — la forma del testo e la prima posizione dell'etichetta — "
        "quando il corpus le associa più di un lemma.",
        "Here the nucleus is one and the same combination of form and part of "
        "speech — the form of the text and the first position of the tag — "
        "when the corpus associates more than one lemma with it."),

    # ── key: when it repeats the core, it says so ──────────────────────
    "varcol.morfologia.chiave": (
        "In questa scheda la chiave è la forma stessa, quindi ripete il "
        "nucleo. Resta perché è la chiave con cui il piano raggruppa, ed è la "
        "stessa colonna in tutt'e cinque le schede.",
        "In this tab the key is the form itself, so it repeats the nucleus. It "
        "stays because it is the key the plane groups by, and it is the same "
        "column in all five tabs."),
    "varcol.posizioni.chiave": (
        "In questa scheda la chiave è la forma stessa, quindi ripete il "
        "nucleo: quello che cambia da riga a riga è la posizione del tag "
        "esaminata, non la chiave.",
        "In this tab the key is the form itself, so it repeats the nucleus: "
        "what changes from row to row is the tag position examined, not the "
        "key."),
    "varcol.contesto.chiave": (
        "Il trigramma per esteso: la parola prima, quella centrale e quella "
        "dopo. È questo che il piano tiene fermo, e il nucleo ne è solo la "
        "parola di mezzo.",
        "The trigram in full: the word before, the central one and the word "
        "after. This is what the plane holds fixed, and the nucleus is only "
        "its middle word."),
    "varcol.dipendenze.chiave": (
        "Le due parole della coppia, nella forma interna con cui il programma "
        "raggruppa. Porta la stessa informazione del nucleo, scritta con un "
        "altro separatore.",
        "The two words of the pair, in the internal form the program groups "
        "by. It carries the same information as the nucleus, written with a "
        "different separator."),
    "varcol.lemmi.chiave": (
        "La forma e la parte del discorso, che è quello che il piano tiene "
        "fermo: «λόγος / n» sono la forma λόγος analizzata come sostantivo. "
        "Il nucleo ne è la sola forma.",
        "The form and the part of speech, which is what the plane holds fixed: "
        "“λόγος / n” is the form λόγος analysed as a noun. The nucleus is its "
        "form alone."),

    # ── the values, where they are not morphological labels ────────────
    "varcol.posizioni.n_etichette": (
        "Quanti valori diversi il corpus mette in quella posizione "
        "dell'etichetta per questa forma. Se è 2, la stessa forma porta lì due "
        "caratteri diversi.",
        "How many different values the corpus puts in that position of the tag "
        "for this form. If it is 2, the same form carries two different "
        "characters there."),
    "varcol.posizioni.etichette": (
        "I caratteri concretamente trovati in quella posizione: un carattere "
        "solo per valore, non l'etichetta intera.",
        "The characters actually found in that position: a single character "
        "per value, not the whole tag."),
    "varcol.dipendenze.n_etichette": (
        "Quante combinazioni diverse di relazione e direzione il corpus "
        "annota fra le due parole.",
        "How many different combinations of relation and direction the corpus "
        "annotates between the two words."),
    "varcol.dipendenze.etichette": (
        "Le relazioni concretamente trovate, con la direzione: la lettera "
        "finale dice dove sta la testa, L a sinistra e R a destra.",
        "The relations actually found, with their direction: the final letter "
        "says where the head is, L to the left and R to the right."),
    "varcol.lemmi.n_etichette": (
        "Quanti lemmi diversi il corpus associa a questa combinazione di "
        "forma e parte del discorso.",
        "How many different lemmas the corpus associates with this "
        "combination of form and part of speech."),
    "varcol.lemmi.etichette": (
        "I lemmi concretamente trovati per questa forma.",
        "The lemmas actually found for this form."),
    "varcol.posizioni.tipo": (
        "Quale delle nove posizioni dell'etichetta morfologica esamina questa "
        "riga: parte del discorso, persona, numero, tempo, modo, diatesi, "
        "genere, caso, grado.",
        "Which of the nine positions of the morphological tag this row "
        "examines: part of speech, person, number, tense, mood, voice, gender, "
        "case, degree."),
    "varcol.contesto.occorrenze": (
        "Quante volte il trigramma compare nel corpus in tutto, sommando le "
        "occorrenze di ciascuna etichetta della parola centrale.",
        "How many times the trigram occurs in the corpus in all, adding up "
        "the occurrences of each tag of the central word."),
    "varcol.dipendenze.occorrenze": (
        "Quante volte la coppia di parole compare legata da un arco, sommando "
        "le occorrenze di ciascuna relazione.",
        "How many times the word pair occurs linked by an arc, adding up the "
        "occurrences of each relation."),

    "chart.famiglia": ("Segnalazioni per famiglia", "Findings by family"),
    # ── what each chart counts, and on what ────────────────────────────
    "chartunit.famiglia": (
        "Conta: segnalazioni. Denominatore: nessuno, sono conteggi.",
        "Counts: findings. Denominator: none, these are counts."),
    "chartunit.famiglia.gruppo": (
        "Conta: segnalazioni. Denominatore: il totale delle segnalazioni di "
        "ciascun gruppo, perché fra gruppi di dimensione diversa un conteggio "
        "confronta la lunghezza dei testi.",
        "Counts: findings. Denominator: each group's own total, because across "
        "groups of different size a count compares the length of the texts."),
    "chartunit.livello": (
        "Conta: segnalazioni, per classe diagnostica. Denominatore: nessuno.",
        "Counts: findings, by diagnostic class. Denominator: none."),
    "chartunit.livello.gruppo": (
        "Conta: segnalazioni, per classe diagnostica. Denominatore: il totale "
        "di ciascun gruppo.",
        "Counts: findings, by diagnostic class. Denominator: each group's own total."),
    "chartunit.regola": (
        "Conta: segnalazioni, controllo per controllo. Denominatore: nessuno.",
        "Counts: findings, check by check. Denominator: none."),
    "chartunit.regola.gruppo": (
        "Conta: segnalazioni, controllo per controllo. Denominatore: il totale "
        "di ciascun gruppo.",
        "Counts: findings, check by check. Denominator: each group's own total."),
    "chartunit.densita": (
        "Conta: segnalazioni ogni 10.000 record attivi. Denominatore: i record "
        "attivi del documento. È il tasso che il giro dichiara, sulla stessa "
        "unità e con lo stesso fattore.",
        "Counts: findings per 10,000 active records. Denominator: the "
        "document's active records. It is the rate the run declares, on the "
        "same unit and with the same factor."),
    "chartunit.densita.gruppo": (
        "Conta: segnalazioni ogni 10.000 record attivi. Denominatore: i record "
        "attivi di ciascun gruppo.",
        "Counts: findings per 10,000 active records. Denominator: each group's "
        "active records."),
    "chartunit.accordo": (
        "Conta: parole su cui il corpus e il modello dicono la stessa cosa. "
        "Denominatore: le parole valutabili, dichiarato nella pagina dei modelli.",
        "Counts: words on which the corpus and the model agree. Denominator: "
        "the evaluable words, stated on the models page."),
    "chartunit.treway": (
        "Conta: parole, divise per chi è d'accordo con chi. Denominatore: le "
        "parole allineate a tutti e due i modelli.",
        "Counts: words, split by who agrees with whom. Denominator: the words "
        "aligned to both models."),
    "chart.livello": ("Segnalazioni per classe diagnostica",
                      "Findings by diagnostic class"),
    "chart.regola": ("Controlli che segnalano di più", "Checks that report most"),
    "chart.densita": ("Densità di segnalazioni per documento",
                      "Finding density by document"),
    "chart.casi": ("Distribuzione dei casi", "Case distribution"),
    "chart.modi": ("Distribuzione dei modi", "Mood distribution"),
    "chart.tempi": ("Distribuzione dei tempi", "Tense distribution"),
    "chart.pos": ("Parti del discorso", "Parts of speech"),
    "chart.relazioni": ("Funzioni sintattiche", "Syntactic functions"),
    "chart.frasi": ("Lunghezza delle frasi", "Sentence length"),
    "chart.distanze": ("Distanza testa-dipendente", "Head-dependent distance"),
    "chart.profilo": ("Profilo morfologico per gruppo",
                      "Morphological profile by group"),
    "chart.composizione": ("Composizione del corpus", "Corpus composition"),
    "chart.accordo": ("Accordo fra corpus e modelli",
                      "Agreement between corpus and models"),
    "chart.treway": ("Corpus, Stanza e UDPipe", "Corpus, Stanza and UDPipe"),
    "chart.rumore": ("Il modello riproduce il rumore?",
                     "Does the model reproduce the noise?"),
    "chart.posizioni": ("Accordo posizione per posizione",
                        "Agreement position by position"),
    "chart.unavailable": ("non disponibile", "not available"),
    "chart.split_by": ("Ogni grafico è diviso per {0}.",
                       "Every chart is split by {0}."),
    "chart.no_metadata": (
        "Questo corpus non porta colonne di metadato: i grafici restano "
        "sull'intero corpus.",
        "This corpus carries no metadata columns: the charts stay on the "
        "whole corpus."),

    # ── Metadata columns, as shown in the grouping menus ───────────────
    "group.autore": ("autore", "author"),
    "group.opera": ("opera", "work"),
    "group.genere": ("genere", "genre"),
    "group.periodo": ("periodo", "period"),
    "group.dialetto": ("dialetto", "dialect"),
    "group.secolo": ("secolo", "century"),
    "group.documento": ("documento", "document"),
    "group.corpus": ("corpus", "corpus"),

    # ── Review page: what the decision log needs ───────────────────────
    "review.new_relation": ("Relazione corretta", "Corrected relation"),
    "review.postag.hint": ("nove caratteri, es. n-s---mn-",
                           "nine characters, e.g. n-s---mn-"),
    "review.relation.hint": ("es. ATR, ADV, OBJ", "e.g. ATR, ADV, OBJ"),
    "review.decided_by": ("Chi decide", "Decided by"),
    "review.decided_by.hint": ("nome o sigla di chi corregge",
                               "name or initials of the annotator"),
    "review.reason": ("Perché", "Reason"),
    "review.reason.hint": ("una riga: perché questa correzione",
                           "one line: why this correction"),
    "review.saved_count": ("({0} correzioni in tutto)", "({0} corrections in all)"),
    "review.log_saved": ("Correzione salvata: {0} → {1}",
                         "Correction saved: {0} → {1}"),
    "review.postag_length": ("L'etichetta deve avere esattamente nove caratteri.",
                             "The tag must be exactly nine characters long."),
    "review.already_corrected": ("Questo record è già stato corretto una volta.",
                                 "This record has already been corrected once."),
    "review.export_gold": ("Esporta il dizionario delle decisioni",
                           "Export the decision dictionary"),
    "review.remove": ("Rimuovi una correzione", "Remove a correction"),
    "review.only_uncorrected": ("Solo quelle non ancora corrette",
                                "Only the ones not yet corrected"),
    "review.dictionary": ("Dizionario di forme", "Form dictionary"),
    "review.dictionary.hint": ("Assegna un lemma a ogni occorrenza di una forma.",
                               "Assigns a lemma to every occurrence of a form."),
    "review.dictionary.placeholder": (
        "CSV con due colonne: form, lemma (facoltativo)",
        "CSV with two columns: form, lemma (optional)"),

    # ── Search page filters ────────────────────────────────────────────
    "search.filter.autore": ("Autore", "Author"),
    "search.filter.genere": ("Genere", "Genre"),
    "search.filter.periodo": ("Periodo", "Period"),
    "search.filter.dialetto": ("Dialetto", "Dialect"),

    # ── Models page ───────────────────────────────────────────────────
    "models.confusion": ("Matrice di confusione su una posizione",
                         "Confusion matrix on one position"),
    "models.position": ("Posizione", "Position"),

    # ── Small shared strings ──────────────────────────────────────────
    "common.copied": ("Copiato negli appunti", "Copied to the clipboard"),
    "common.not_applicable": ("Non valutabile per questo record",
                              "Not applicable to this record"),
    "stats.whole_corpus": ("tutto il corpus", "the whole corpus"),
    "review.findings_count": ("({0} segnalazioni)", "({0} findings)"),
    "treatment.automatica": ("automatica", "automatic"),
    "treatment.normalizzazione": ("normalizzazione", "normalisation"),
    "treatment.manuale": ("manuale", "manual"),

    # ── Titles drawn inside the charts ────────────────────────────────
    "fig.by": ("{0}, per {1}", "{0}, by {1}"),
    "fig.family_by": ("Segnalazioni per famiglia e per {0}",
                      "Findings by family and by {0}"),
    "fig.class_by": ("Segnalazioni per classe e per {0}",
                     "Findings by class and by {0}"),
    "fig.rule_by": ("Controlli che segnalano di più, per {0}",
                    "Checks that report most, by {0}"),
    "fig.density_by": ("Densità di segnalazioni per {0}", "Findings density by {0}"),
    "fig.relations_by": ("Funzioni sintattiche, per {0}", "Syntactic functions, by {0}"),
    "fig.relations": ("Frequenza delle funzioni sintattiche",
                      "Frequency of syntactic functions"),
    "fig.shape_by": ("Forma della frase, per {0}", "Sentence shape, by {0}"),
    "fig.distance_by": ("Distanza media testa-dipendente, per {0}",
                        "Mean head-dependent distance, by {0}"),
    "fig.profile_by": ("Profilo morfologico per {0}", "Morphological profile by {0}"),
    "fig.composition_by": ("Composizione del corpus per {0}",
                           "Corpus composition by {0}"),
    "fig.threeway_by": ("Corpus, Stanza e UDPipe, per {0}",
                        "Corpus, Stanza and UDPipe, by {0}"),
    "fig.noise_by": ("Il modello riproduce il rumore? Per {0}",
                     "Does the model reproduce the noise? By {0}"),
    "fig.slots_by": ("Accordo posizione per posizione, per {0}",
                     "Agreement position by position, by {0}"),
    "fig.axis.findings": ("segnalazioni", "findings"),
    "fig.axis.occurrences": ("occorrenze", "occurrences"),
    "fig.axis.mean": ("media", "mean"),
    "fig.axis.ratio": ("rapporto", "ratio"),

    # ── Status bar and window messages ────────────────────────────────
    "app.error_details": (
        "I dettagli sono nel file pipeline_errors.log, nella cartella del programma.",
        "The details are in pipeline_errors.log, in the program's folder."),
    "app.error_prefix": ("ERRORE, {0}", "ERROR, {0}"),
    "app.view_failed": (
        "Una vista non si è potuta aggiornare ({0}). Il resto del programma "
        "continua a funzionare e i risultati salvati sono intatti.",
        "One view could not be refreshed ({0}). The rest of the program keeps "
        "working and the saved results are intact."),
    "app.closing_title": ("C'è un'elaborazione in corso", "Work is still running"),
    "app.closing_body": (
        "Un'elaborazione è ancora in corso. Chiudere adesso la interrompe: "
        "il lavoro già salvato resta, quello in corso va perso.\n\nChiudere lo stesso?",
        "Work is still running. Closing now interrupts it: what has already "
        "been saved stays, what is running is lost.\n\nClose anyway?"),
    "app.closing": ("Chiusura in corso…", "Closing…"),
    "app.retranslate_failed": ("Ricostruzione della pagina fallita: {0}",
                              "Could not rebuild the page: {0}"),

    # ── Load page: the ready-made examples ────────────────────────────
    "load.example.gorman": (
        "Gorman, prosa attica e storiografia (≈ 625.000 record)",
        "Gorman, Attic prose and historiography (≈ 625,000 records)"),
    "load.example.pedalion": (
        "Pedalion, prosa, poesia e papiri (≈ 280.000 record)",
        "Pedalion, prose, poetry and papyri (≈ 280,000 records)"),
    "load.example.glaux_campione": (
        "GLAUx, campione dichiarato, annotazione automatica (≈ 300.000 record)",
        "GLAUx, declared sample, automatic annotation (≈ 300,000 records)"),
    "load.example.glaux_conferma": (
        "GLAUx, campione di conferma (≈ 270.000 record)",
        "GLAUx, confirmation sample (≈ 270,000 records)"),
    "load.example.glaux_campione_manuale": (
        "GLAUx, campione dichiarato, annotazione a mano (≈ 22.000 record)",
        "GLAUx, declared sample, manual annotation (≈ 22,000 records)"),
    "load.example.glaux_conferma_manuale": (
        "GLAUx, campione di conferma, annotazione a mano (≈ 29.000 record)",
        "GLAUx, confirmation sample, manual annotation (≈ 29,000 records)"),
    "load.missing_folder": ("La cartella non esiste:\n{0}",
                            "That folder does not exist:\n{0}"),
    "load.log_loading": ("Carico «{0}» da {1}", "Loading “{0}” from {1}"),
    "load.mark.checked": ("controllato", "checked"),
    "load.mark.corrected": ("corretto", "corrected"),
    "load.delete_confirm": (
        "Eliminare definitivamente «{0}» e tutti i suoi risultati?\n"
        "I file XML originali non vengono toccati.",
        "Permanently delete “{0}” and all of its results?\n"
        "The original XML files are left untouched."),
    "load.log_deleted": ("Eliminato {0}", "Deleted {0}"),

    # ── Overview page: the headline numbers ───────────────────────────
    "overview.metric.sentences": ("Frasi", "Sentences"),
    "overview.metric.forms": ("Forme distinte", "Distinct forms"),
    "overview.metric.lemmas": ("Lemmi distinti", "Distinct lemmas"),

    # ── Errors page: the summary ──────────────────────────────────────
    "errors.metric.findings": ("Segnalazioni", "Findings"),
    "errors.metric.tokens_touched": ("Record interessati", "Records involved"),
    "errors.metric.share": ("% del corpus", "% of the corpus"),
    "errors.metric.violations": ("Violazioni dello schema", "Scheme violations"),
    "errors.metric.variants": ("Varianti e casi da verificare",
                               "Variants and cases to check"),
    "errors.metric.auto": ("Correggibili in automatico", "Automatically correctable"),
    "errors.metric.rules": ("Regole scattate", "Rules that fired"),

    # ── Errors page: inconsistencies between similar passages ─────────
    "errors.variation_intro": (
        "Qui GCP raccoglie forme, contesti o coppie che nel corpus ricevono "
        "più di un'annotazione. Questo non significa automaticamente che una "
        "delle annotazioni sia sbagliata: la tabella serve a vedere dove il "
        "corpus varia e quanto è frequente ciascuna alternativa, così da poter "
        "controllare i casi concreti. Più i contesti sono simili, più conviene "
        "guardare.",
        "Here GCP groups forms, contexts, or pairs that receive more than one "
        "annotation in the corpus. This does not automatically mean that one "
        "annotation is wrong. The table shows where the corpus varies and how "
        "frequent each alternative is, so that the individual cases can be "
        "inspected. The more alike the contexts, the more it is worth "
        "looking."),
    "errors.var.morfologia": ("Stessa parola, etichette diverse",
                              "Same word, different tags"),
    "errors.var.morfologia.hint": (
        "La stessa forma compare nel corpus con etichette morfologiche diverse.",
        "The same form appears in the corpus with different morphological tags."),
    "errors.var.posizioni": ("Una posizione alla volta", "One position at a time"),
    "errors.var.posizioni.hint": (
        "La stessa verifica ripetuta per ciascuna delle nove posizioni "
        "dell'etichetta: quasi tutti gli errori morfologici reali sono errori "
        "di una posizione, non dell'intera stringa.",
        "The same check repeated for each of the nine positions of the tag: "
        "almost every real morphological error is an error in one position, "
        "not in the whole string."),
    "errors.var.contesto": ("Con contesto identico", "With identical context"),
    "errors.var.contesto.hint": (
        "I casi in cui anche le parole immediatamente prima e dopo sono le "
        "stesse: il filtro che trasforma un elenco rumoroso in uno utilizzabile.",
        "The cases where the words immediately before and after are the same "
        "too: the filter that turns a noisy list into a usable one."),
    "errors.var.dipendenze": ("Stessa coppia, relazione diversa",
                              "Same pair, different relation"),
    "errors.var.dipendenze.hint": (
        "La stessa coppia di parole è legata da relazioni sintattiche diverse. "
        "La lettera finale indica dove sta la testa: L a sinistra, R a destra, "
        "così un errore di etichetta si distingue da un errore di attacco.",
        "The same pair of words is linked by different syntactic relations. "
        "The final letter says where the head is: L to the left, R to the "
        "right, so a labelling error can be told from an attachment error."),

    # ── Errors page: the right-hand panel ─────────────────────────────
    "errors.grade.error": ("Errore", "Error"),
    "errors.grade.error.note": (
        "Qui c'è qualcosa che nello schema AGDT non può stare così.",
        "There is something here that the AGDT scheme does not allow."),
    "errors.grade.suspect": ("Sospetto", "Suspect"),
    "errors.grade.suspect.note": (
        "Non è detto che sia un errore: è un punto da guardare. "
        "Va deciso leggendo la frase.",
        "It is not necessarily an error: it is a place to look at. It has to "
        "be decided by reading the sentence."),
    "errors.grade.check.note": (
        " Questo controllo non conta come errore in nessun totale: "
        "serve a trovare il posto dove guardare, non a dire che "
        "lì c'è uno sbaglio.",
        " This check counts as an error in no total: it is there to find the "
        "place to look at, not to say that something is wrong there."),
    "errors.grade.variant.note": (
        " Quello che trova non è un errore ma una convenzione del "
        "corpus: normalizzarla ha senso solo se questi dati devono "
        "servire per addestrare o per confrontare due annotazioni.",
        " What it finds is not an error but a convention of the corpus: "
        "normalising it makes sense only if these data are to be used for "
        "training or for comparing two annotations."),
    "errors.empty_field": ("campo vuoto", "empty field"),
    "errors.evidence.intro": (
        "Tutte le letture che {0}, <b>{1}</b>, riceve nel corpus, dalla più frequente alla più rara. È la tabella da guardare per decidere quale sia quella giusta.",
        "Every reading that {0}, <b>{1}</b>, receives in the corpus, from the most frequent to the rarest. This is the table to look at in order to decide which one is right."),
    "errors.evidence.this_lemma": ("questo lemma", "this lemma"),
    "errors.evidence.this_form": ("questa forma", "this form"),
    "errors.evidence.example": ("un esempio", "an example"),
    "errors.evidence.more": (
        "Altre {0} letture distinte non stanno in questa tabella: l'elenco "
        "completo è nell'esportazione CSV.",
        "Another {0} distinct readings do not fit in this table: the full "
        "list is in the CSV export."),
    "errors.suggest.postag": ("etichetta", "tag"),
    "errors.suggest.lemma": ("lemma", "lemma"),
    "errors.suggest.relation": ("relazione", "relation"),
    "errors.suggest.form": ("forma", "form"),

    # ── Review page ───────────────────────────────────────────────────
    "review.rules_active": ("{0} regole attive su {1}", "{0} rules on, out of {1}"),
    "review.dictionary_unreadable": ("Dizionario di forme illeggibile: {0}",
                                     "Form dictionary could not be read: {0}"),
    "review.metric.changed": ("Record modificati", "Changed records"),
    "review.metric.missing_before": ("Lemmi mancanti prima", "Missing lemmas before"),
    "review.metric.missing_after": ("Lemmi mancanti dopo", "Missing lemmas after"),
    "review.metric.unique_before": ("Lemmi distinti prima", "Distinct lemmas before"),
    "review.metric.unique_after": ("Lemmi distinti dopo", "Distinct lemmas after"),
    "review.export_gold.hint": (
        "Trasforma le tue decisioni in una tabella "
        "forma → lemma / etichetta: la puoi versionare, mandare a un collega "
        "o riusare su un altro corpus.",
        "Turns your decisions into a form → lemma / tag table: you can "
        "version it, send it to a colleague or reuse it on another corpus."),
    "review.gold_title": ("Dizionario delle decisioni", "Decision dictionary"),
    "review.gold_none": (
        "Non ci sono ancora correzioni manuali da esportare.\n"
        "Correggi qualche record, poi riprova.",
        "There are no manual corrections to export yet.\n"
        "Correct a few records, then try again."),
    "review.gold_save": ("Salva il dizionario", "Save the dictionary"),
    "review.gold_exported": ("Dizionario esportato: {0} ({1} forme)",
                             "Dictionary exported: {0} ({1} forms)"),
    "review.gold_done": (
        "Salvate {0} forme in:\n{1}\n\n"
        "È il registro delle tue decisioni: puoi versionarlo, mandarlo a "
        "un collega, discuterlo, riusarlo su un altro corpus.",
        "Saved {0} forms to:\n{1}\n\n"
        "It is the record of your decisions: you can version it, send it to "
        "a colleague, argue about it, reuse it on another corpus."),

    # ── Search page ───────────────────────────────────────────────────
    "search.mode.esatto": ("esatto", "exact"),
    "search.mode.inizia con": ("inizia con", "starts with"),
    "search.mode.contiene": ("contiene", "contains"),
    "search.mode.espressione regolare": ("espressione regolare", "regular expression"),
    "construction.genitivo assoluto": ("genitivo assoluto", "genitive absolute"),
    "construction.accusativo assoluto": ("accusativo assoluto", "accusative absolute"),
    "construction.accusativo con infinito": ("accusativo con infinito",
                                             "accusative and infinitive"),
    "construction.infinito articolare": ("infinito articolare", "articular infinitive"),
    "construction.participio sostantivato": ("participio sostantivato",
                                             "substantivised participle"),
    "construction.participio predicativo": ("participio predicativo",
                                            "predicative participle"),
    "construction.perifrastica con εἰμί": ("perifrastica con εἰμί",
                                           "periphrastic with εἰμί"),
    "construction.schema attico": ("schema attico", "Attic schema"),
    "construction.ἄν + modo": ("ἄν + modo", "ἄν + mood"),
    "construction.soggetto sottinteso": ("soggetto sottinteso", "unexpressed subject"),
    "group.forma": ("forma", "form"),
    "group.postag": ("postag", "tag"),
    "group.analisi morfologica": ("analisi morfologica", "morphological analysis"),
    "group.relazione": ("relazione", "relation"),
    "group.funzione sintattica": ("funzione sintattica", "syntactic function"),
    "group.document_id": ("documento", "document"),

    # ── Statistics page ───────────────────────────────────────────────
    "stats.slot.casi": ("Casi", "Cases"),
    "stats.slot.modi": ("Modi", "Moods"),
    "stats.slot.tempi": ("Tempi", "Tenses"),
    "stats.slot.diatesi": ("Diatesi", "Voices"),
    "stats.slot.persone": ("Persone", "Persons"),
    "stats.slot.pos": ("Parti del discorso", "Parts of speech"),
    "stats.stopword_profile": ("Escludi parole frequenti", "Exclude frequent words"),
    "stats.syn.relazioni": ("Funzioni sintattiche", "Syntactic functions"),
    "stats.syn.relazioni.hint": ("L'impronta sintattica del corpus.",
                                 "The syntactic fingerprint of the corpus."),
    "stats.count_the": ("Conta le", "Count the"),
    "stats.sketch.hint": (
        "Invece di chiedere «quali parole compaiono vicino a λέγω», un "
        "treebank permette la domanda giusta: qual è il soggetto tipico di "
        "λέγω, quale il suo oggetto, in quale caso. La misura di associazione "
        "è logDice, che essendo normalizzata sulle frequenze dei due lemmi "
        "regge il confronto fra corpora di dimensione diversa meglio di una "
        "misura basata sul rapporto di verosimiglianza; resta comunque una "
        "misura calcolata su questo corpus, e va confrontata con prudenza. "
        "Accanto al punteggio c'è sempre il numero di co-occorrenze: un "
        "punteggio alto su una sola osservazione va letto per quello che è.",
        "Instead of asking \u201cwhich words occur near \u03bb\u03ad\u03b3\u03c9\u201d, a treebank allows "
        "the right question: what is the typical subject of \u03bb\u03ad\u03b3\u03c9, what its "
        "object, in which case. The association measure is logDice, which, "
        "being normalised on the frequencies of the two lemmas, withstands "
        "comparison across corpora of different size better than a "
        "likelihood-ratio measure; it remains a figure computed on this "
        "corpus, and should be compared with care. The joint frequency is "
        "always shown next to the score: a high score on a single observation "
        "should be read as such."),
    "stats.sketch.unita": (
        "Le occorrenze del lemma si contano fra le parole del testo, non fra i "
        "record: punteggiatura e nodi tecnici restano fuori. Le co-occorrenze "
        "sono archi fra due parole. Le grafie che il corpus usa per lo stesso "
        "lemma — λέγω, λέγω1, λέγω2, λέγω3 — contano insieme, e la scheda "
        "«Grafie del lemma» le mostra una per una.",
        "Occurrences of the lemma are counted among the words of the text, not "
        "among the records: punctuation and technical nodes stay out. Joint "
        "frequencies are links between two words. The spellings the corpus uses "
        "for one lemma \u2014 \u03bb\u03ad\u03b3\u03c9, \u03bb\u03ad\u03b3\u03c91, \u03bb\u03ad\u03b3\u03c92, \u03bb\u03ad\u03b3\u03c93 \u2014 count together, and the "
        "\u201cSpellings of the lemma\u201d tab lists them one by one."),
    "stats.sketch.troncate": (
        "{0} associazioni in più non entrano nella tabella: per ogni relazione "
        "si mostrano le prime {1} per punteggio.",
        "{0} further associations are not shown: each relation lists its top "
        "{1} by score."),
    "stats.sketch.absent": ("Questo lemma non compare nel corpus.",
                            "This lemma does not occur in the corpus."),
    "stats.sketch.choose": (
        "Trovate più forme accentate per questo lemma. Quale vuoi profilare?",
        "Several accented forms match this lemma. Which one do you want to profile?"),
    "stats.sketch.nothing": (
        "Questo lemma non ha dipendenti né teste nel corpus: "
        "controlla la grafia, accenti compresi.",
        "This lemma has neither dependents nor heads in the corpus: check "
        "the spelling, accents included."),

    # ── Charts page ───────────────────────────────────────────────────
    "charts.failed": ("Grafico «{0}» non disegnabile: {1}",
                      "Chart “{0}” could not be drawn: {1}"),
    "charts.none_for_group": ("Nessuna segnalazione per questo raggruppamento",
                              "No findings for this grouping"),
    "charts.no_group_big_enough": ("Nessun gruppo abbastanza grande",
                                   "No group is large enough"),
    "charts.no_data_for_group": ("Nessun dato per questo raggruppamento",
                                 "No data for this grouping"),
    "charts.no_sentences": ("Nessun gruppo con almeno venti frasi",
                            "No group with at least twenty sentences"),
    "charts.no_arcs_for_group": ("Nessun arco per questo raggruppamento",
                                 "No arcs for this grouping"),
    "charts.no_arcs": ("Nessun gruppo con almeno cento archi",
                       "No group with at least a hundred arcs"),
    "charts.axis.per_ten_thousand": ("segnalazioni ogni 10.000 record attivi",
                                     "findings per 10,000 active records"),
    "charts.axis.head_distance": ("parole fra testa e dipendente",
                                  "words between head and dependent"),
    "charts.axis.tag_position": ("posizione del tag", "tag position"),
    "charts.axis.agreement_share": ("% di accordo", "% agreement"),

    # ── Charts page: the captions of the grouped charts ───────────────
    "charts.cap.findings_by_group": (
        "La stessa ripartizione delle segnalazioni, gruppo per gruppo ({0}). "
        "Ogni valore è una percentuale del proprio gruppo: i conteggi grezzi "
        "confronterebbero la lunghezza dei testi, non il loro comportamento.",
        "The same breakdown of the findings, group by group ({0}). Every "
        "value is a percentage of its own group: raw counts would compare the "
        "length of the texts, not their behaviour."),
    "charts.cap.density": (
        "Segnalazioni ogni 10.000 record attivi, per {0}. È lo stesso tasso, "
        "sulla stessa unità e con lo stesso fattore, che il programma usa "
        "dappertutto. La densità è l'unico confronto lecito fra gruppi di "
        "dimensione diversa; i gruppi sotto i 200 record non compaiono.",
        "Findings per 10,000 active records, by {0}. It is the same rate, on "
        "the same unit and with the same factor, that the program uses "
        "everywhere. Density is the only legitimate comparison between groups "
        "of different size; groups under 200 records are left out."),
    "charts.cap.slot_by_group": (
        "{0} confrontata gruppo per gruppo ({1}), in percentuale sul totale "
        "di ciascun gruppo. È la forma in cui la distribuzione di un gruppo "
        "piccolo resta leggibile accanto a quella di uno grande.",
        "{0} compared group by group ({1}), as a percentage of each group's "
        "own total. It is the shape in which a small group's distribution "
        "stays readable next to a large one's."),
    "charts.cap.relations_by_group": (
        "L'impronta sintattica di ciascun gruppo ({0}): quanto pesa ogni "
        "funzione sul totale delle relazioni di quel gruppo.",
        "The syntactic fingerprint of each group ({0}): how much each "
        "function weighs in that group's total of relations."),
    "charts.cap.shape_by_group": (
        "Lunghezza media della frase e profondità massima media dell'albero, "
        "per {0}. Sono le due misure che separano il periodo costruito dalla "
        "paratassi. I gruppi con meno di venti frasi sono esclusi: su quei "
        "numeri la media non dice niente.",
        "Mean sentence length and mean maximum tree depth, by {0}. They are "
        "the two measures that separate the built period from parataxis. "
        "Groups with fewer than twenty sentences are excluded: on those "
        "numbers the mean says nothing."),
    "charts.cap.distance_by_group": (
        "Quanto lontano sta in media un dipendente dalla propria testa, per "
        "{0}. È la misura standard del carico di lettura in una lingua a "
        "ordine libero: più alta, più l'ordine delle parole si allontana dal "
        "contiguo.",
        "How far a dependent stands on average from its own head, by {0}. It "
        "is the standard measure of processing load in a free word-order "
        "language: the higher it is, the further word order departs from the "
        "contiguous."),
    "charts.cap.profile_by_group": (
        "Profilo morfologico per {0}. Il rapporto genitivi/dativi e "
        "l'indice di ottativo sono i due marcatori che si muovono più "
        "nettamente. Ogni gruppo va letto accanto alla propria "
        "numerosità: un gruppo piccolo produce rapporti instabili.",
        "Morphological profile by {0}. The genitive/dative ratio and the "
        "optative index are the two markers that move most clearly. Every "
        "group has to be read next to its own size: a small group produces "
        "unstable ratios."),
    "charts.cap.composition_by_group": (
        "Quante parole porta ciascun gruppo, raggruppando per {0}. "
        "È la figura da guardare prima di ogni altra: nessun confronto "
        "fra gruppi vuol dire niente senza le rispettive dimensioni.",
        "How many words each group brings, grouping by {0}. It is the "
        "figure to look at before any other: no comparison between groups "
        "means anything without their respective sizes."),
    "charts.cap.agreement_by_group": (
        "Accordo fra l'annotazione del corpus e quella dei due modelli, "
        "per {0}.",
        "Agreement between the corpus annotation and that of the two models, "
        "by {0}."),
    "charts.cap.threeway_by_group": (
        "Chi è d'accordo con chi, gruppo per gruppo ({0}). La colonna da "
        "guardare è «i due modelli contro il corpus»: dove è più alta, "
        "l'annotazione del corpus è più isolata.",
        "Who agrees with whom, group by group ({0}). The column to look at "
        "is “the two models against the corpus”: where it is highest, the "
        "corpus annotation is most isolated."),
    "charts.cap.noise_by_group": (
        "Sulle parole che una regola ha riscritto, che cosa fa il modello: ripete l'annotazione originale, converge sulla correzione o propone un terzo valore: per {0}.",
        "On the words a rule rewrote, what the model does: it repeats the original annotation, converges on the correction, or proposes a third value: by {0}."),
    "charts.cap.slots_by_group": (
        "Accordo fra corpus e modello posizione per posizione del tag, per "
        "{0}. I gruppi con meno di cinquecento parole allineate sono esclusi.",
        "Agreement between corpus and model position by position of the tag, "
        "by {0}. Groups with fewer than five hundred aligned words are "
        "excluded."),

    # ── Models page ───────────────────────────────────────────────────
    "models.custom_model": ("Modello UDPipe personalizzato (facoltativo)",
                            "Custom UDPipe model (optional)"),
    "models.custom_model.hint": ("lascia vuoto per usare ancient_greek-perseus",
                                 "leave empty to use ancient_greek-perseus"),
    "models.mismatches": ("Parole in cui il modello si discosta dal corpus",
                          "Words where the model departs from the corpus"),
    "models.model": ("Modello", "Model"),
    "models.not_run": ("non ancora eseguito", "not run yet"),
    "models.not_here": (
        "non disponibile in questo ambiente",
        "not available in this environment"),
    "models.not_on_this_corpus": (
        "non ancora eseguito sul corpus caricato",
        "not run on the loaded corpus yet"),
    "models.stale": (
        "il confronto salvato riguarda un altro giro e non viene mostrato: {0}",
        "the saved comparison belongs to another run and is not shown: {0}"),
    "models.stale.short": ("da rifare su questo corpus", "to be run on this corpus"),
    "models.state.available": ("modello disponibile", "model available"),
    "models.state.done": ("eseguito su questo corpus", "run on this corpus"),
    "models.postag_suspended": (
        "Confronto delle etichette sospeso: {0}",
        "Tag comparison suspended: {0}"),
    "models.field.model": ("Modello", "Model"),
    "models.field.version": ("Versione", "Version"),
    "models.field.resources": ("Risorse", "Resources"),
    "models.field.corpus": ("Corpus", "Corpus"),
    "models.field.when": ("Eseguito il", "Run on"),
    "models.field.words": ("Parole valutabili", "Evaluable words"),
    "models.field.coverage": ("Copertura", "Coverage"),
    "models.field.lemma": ("Lemmi uguali", "Lemmas equal"),
    "models.field.postag": ("Etichette uguali", "Tags equal"),
    "models.field.excluded": ("Esclusi", "Excluded"),
    "models.field.definition": ("Definizione della valutazione",
                                "Evaluation definition"),
    "models.units.hint": (
        "Al modello va il testo: le parole e la punteggiatura vera, perché un "
        "tagger legge anche i segni. La misura invece si fa sulle sole parole, "
        "e ogni tasso dichiara il proprio denominatore. Una parola per cui il "
        "modello non produce niente resta nel denominatore e conta come "
        "disaccordo; quante siano si legge nella copertura.",
        "The model receives the text: the words and the real punctuation, "
        "because a tagger reads the marks too. The measurement is made on the "
        "words alone, and every rate states its own denominator. A word for "
        "which the model produces nothing stays in the denominator and counts "
        "as a disagreement; how many those are is what coverage says."),
    "models.three_way.hint": (
        "Le cinque categorie sono mutuamente esclusive. Quella da leggere per "
        "prima è «i due modelli contro il corpus»: due sistemi addestrati "
        "indipendentemente che convergono su una lettura diversa da quella "
        "annotata sono un segnale di revisione più forte degli altri quattro. "
        "Più forte non vuol dire probante: il confronto non tratta nessuno dei "
        "due modelli automatici come gold standard, e due modelli possono "
        "sbagliare insieme sullo stesso costrutto.",
        "The five categories are mutually exclusive. The one to read first is "
        "“the two models against the corpus”: two independently trained "
        "systems converging on a reading different from the annotated one are "
        "a stronger review signal than the other four. Stronger does not mean "
        "conclusive: the comparison does not treat either automatic model as a "
        "gold standard, and two models can be wrong together on the same "
        "construction."),
    "models.recurring": ("Le sostituzioni ricorrenti", "The recurring substitutions"),
    "models.recurring.hint": (
        "Una parola isolata è un aneddoto; la stessa sostituzione ripetuta "
        "duecento volte è una divergenza sistematica fra le convenzioni del "
        "corpus e ciò che i modelli hanno imparato.",
        "One isolated word is an anecdote; the same substitution repeated "
        "two hundred times is a systematic divergence between the corpus's "
        "conventions and what the models have learned."),
    "models.affected_tokens": ("Le parole interessate", "The words involved"),
    "models.slots.hint": (
        "Due annotazioni che coincidono nell'82 % dei casi possono coincidere "
        "quasi perfettamente sulla parte del discorso e crollare sul caso. "
        "La media nasconde proprio la cosa che vale la pena sapere. "
        "L'accordo è calcolato solo sulle parole in cui almeno una delle due "
        "fonti marca quel tratto.",
        "Two annotations that coincide in 82 % of cases may coincide almost "
        "perfectly on part of speech and collapse on case. The average hides "
        "precisely the thing worth knowing. Agreement is computed only on the "
        "words where at least one of the two sources marks that feature."),
    "models.compare": ("Confronta", "Compare"),
    "models.compare_with": ("con", "with"),
    "models.divergence.hint": (
        "Le forme su cui i due modelli sbagliano, o comunque si contraddicono, più spesso. È una classifica di dove l'annotazione automatica del greco è oggi più debole: utile a chi costruisce corpora, per sapere che cosa controllare per primo, e a chi costruisce modelli, per sapere su che cosa lavorare.",
        "The forms on which the two models get it wrong, or at any rate contradict each other, most often. It is a ranking of where automatic annotation of Greek is weakest today: useful to those who build corpora, to know what to check first, and to those who build models, to know what to work on."),
    "models.by_author.hint": (
        "Una percentuale di accordo complessiva è una media su un corpus che "
        "non è omogeneo: modelli addestrati soprattutto su attico classico si "
        "comportano diversamente sulla κοινή di Polibio, e l'unico modo per "
        "vederlo è smettere di fare la media.",
        "An overall agreement percentage is an average over a corpus that is "
        "not homogeneous: models trained mostly on classical Attic behave "
        "differently on Polybius's κοινή, and the only way to see it is to "
        "stop averaging."),

    # ── Rules page ────────────────────────────────────────────────────
    "rules.schema.hint": (
        "L'etichetta morfologica AGDT è una stringa di nove caratteri in cui "
        "ogni posizione ha un significato fisso. Il trattino significa «questa "
        "categoria non si applica». Così <span style='font-family:monospace'>"
        "a-s---mn-</span> si legge: aggettivo, singolare, maschile, nominativo.",
        "The AGDT morphological tag is a nine-character string in which every "
        "position has a fixed meaning. The hyphen means “this category does "
        "not apply”. So <span style='font-family:monospace'>a-s---mn-</span> "
        "reads: adjective, singular, masculine, nominative."),

    # ── Tables: the two answers of a boolean column ───────────────────

    # ── What the background work says while it works ──────────────────
    "work.source": ("Individuo la sorgente…", "Locating the source…"),
    "work.glaux_sample": (
        "Campione GLAUx «{0}», strato «{1}»: {2} testi ({3} record dichiarati)",
        "GLAUx sample “{0}”, layer “{1}”: {2} texts ({3} declared records)"),
    "work.downloading_one": ("Scarico {0} ({1}/{2})", "Downloading {0} ({1}/{2})"),
    "work.downloading": ("Scarico {0}", "Downloading {0}"),
    "work.reading_xml": ("Leggo i file XML da {0}", "Reading the XML files from {0}"),
    "work.no_xml": (
        "Nessun file XML trovato nella sorgente indicata. "
        "Controlla che la cartella contenga file .xml in formato AGDT.",
        "No XML file was found in the source given. Check that the folder "
        "holds .xml files in AGDT format."),
    "work.read_done": ("Letti {0} record · {1} documenti · {2} frasi in {3} s",
                       "Read {0} records · {1} documents · {2} sentences in {3} s"),
    "work.loading_tokens_table": ("Carico la tabella dei record…",
                                  "Loading the record table…"),
    "work.filtered_out": ("Filtro: {0} record esclusi dall'analisi.",
                          "Filter: {0} records left out of the analysis."),
    "work.filtered": ("Filtro: {0} record esclusi.", "Filter: {0} records left out."),
    "work.nfc_applied": (
        "Codifica: {0} record riportati alla forma normale NFC.",
        "Encoding: {0} records brought back to Unicode NFC."),
    "work.check_morphology": ("Controllo le etichette morfologiche",
                              "Checking the morphological tags"),
    "work.found_morphology": ("Morfologia: {0} segnalazioni.",
                              "Morphology: {0} findings."),
    "work.check_lemma": ("Controllo i lemmi", "Checking the lemmas"),
    "work.found_lemma": ("Lemmi: {0} segnalazioni.", "Lemmas: {0} findings."),
    "work.check_syntax": ("Controllo la struttura degli alberi sintattici",
                          "Checking the shape of the syntactic trees"),
    "work.found_syntax": ("Sintassi: {0} segnalazioni.", "Syntax: {0} findings."),
    "work.check_text": ("Controllo il testo e la codifica",
                        "Checking the text and its encoding"),
    "work.found_text": ("Testo: {0} segnalazioni.", "Text: {0} findings."),
    "work.check_agreement": ("Controllo accordo e reggenza",
                             "Checking agreement and government"),
    "work.found_agreement": ("Accordo: {0} segnalazioni.", "Agreement: {0} findings."),
    # The two lines that step 3 writes while it works. A core is a point where the
    # annotation varies, not an established inconsistency, and the lines must not say
    # more than the program knows.
    "work.check_variation": (
        "Confronto le annotazioni (è l'analisi più lenta)",
        "Comparing annotations (the slowest analysis)"),
    "work.found_variation": ("Confronti «{0}»: {1} nuclei.",
                             "Comparisons “{0}”: {1} nuclei."),
    "work.gathering": ("Metto insieme i risultati", "Gathering the results"),
    # ── how much is left, in numbers ──────────────────────────────────
    #
    # “Loading…” says nothing: whoever waits wants to know how much is left, and on a
    # corpus of six hundred thousand records the difference between “working” and “51
    # checks run out of 77” is the difference between waiting and closing.
    "work.checks_done": ("eseguiti {0} controlli su {1}",
                         "{0} of {1} checks done"),
    "work.planes_done": ("calcolati {0} piani su {1}", "{0} of {1} planes computed"),
    "work.percent": ("{0}%", "{0}%"),
    "work.of": ("{0} su {1}", "{0} of {1}"),
    "work.loading_findings": ("Carico record e segnalazioni…",
                              "Loading records and findings…"),
    "work.no_findings_saved": (
        "Non ci sono segnalazioni salvate per questo corpus. "
        "Esegui prima il controllo degli errori.",
        "There are no findings saved for this corpus. Run the error check "
        "first."),
    "work.applying_auto": ("Applico le correzioni automatiche…",
                           "Applying the automatic corrections…"),
    "work.active_rules": ("Regole attive: {0}.", "Active rules: {0}."),
    "work.applying_dictionary": ("Applico il dizionario di forme…",
                                 "Applying the form dictionary…"),
    "work.dictionary_entries": ("Dizionario di forme: {0} voci.",
                                "Form dictionary: {0} entries."),
    "work.manual_applied": ("Correzioni manuali: {0}.", "Manual corrections: {0}."),
    "work.computing_diff": ("Calcolo che cosa è cambiato…",
                            "Working out what changed…"),
    "work.changed_tokens": ("Record modificati: {0}.", "Changed records: {0}."),
    "work.lemma_inventory": ("Aggiorno l'inventario dei lemmi…",
                             "Updating the lemma inventory…"),
    "work.export_sentence_csv": ("Esporto i CSV per frase…",
                                 "Exporting one CSV per sentence…"),
    "work.csv_written": ("CSV esportati in {0}", "CSVs exported to {0}"),
    "work.export_xml": ("Esporto l'XML AGDT corretto…",
                        "Exporting the corrected AGDT XML…"),
    "work.xml_written": ("Scritti {0} file XML in {1}", "Wrote {0} XML files to {1}"),
    "work.export_conllu": ("Esporto in formato CoNLL-U…", "Exporting to CoNLL-U…"),
    "work.conllu_fallback": (
        "Colonne chiave assenti: il CoNLL-U è scritto dalla tabella filtrata.",
        "Key columns missing: the CoNLL-U is written from the filtered table."),
    "work.conllu_written": ("Esportati {0} file CoNLL-U in {1} ({2} record).",
                            "Exported {0} CoNLL-U files to {1} ({2} records)."),
    "work.stanza_models": (
        "Verifico i modelli di Stanza (al primo avvio li scarica)…",
        "Checking the Stanza models (the first run downloads them)…"),
    "work.udpipe_model": (
        "Verifico il modello UDPipe (al primo avvio lo scarica)…",
        "Checking the UDPipe model (the first run downloads it)…"),
    "work.udpipe_subprocess": (
        "UDPipe: avvio processo isolato e caricamento modello (1–2 min)…",
        "UDPipe: starting isolated process and loading model (1–2 min)…"),
    "work.udpipe_subprocess_ready": (
        "UDPipe: modello caricato, elaborazione in corso…",
        "UDPipe: model loaded, starting analysis…"),
    "work.loading_tokens": ("Carico i record…", "Loading the records…"),
    "work.model_running": ("{0} analizza {1} record…", "{0} is analysing {1} records…"),
    "work.detection_done": ("Controllo completato: {0}.",
                            "Checks complete: {0}."),
    "work.model_prepare": ("{0}: verifico il modello…", "{0}: checking the model\u2026"),
    "work.model_tokens": ("Preparo il testo per il modello…",
                          "Preparing the text for the model\u2026"),
    "work.model_cached": (
        "{0}: il confronto salvato vale per questo corpus e per questa "
        "configurazione, e non serve rifarlo.",
        "{0}: the saved comparison applies to this corpus and this "
        "configuration, so it does not need to be run again."),
    "work.model_cancelled": (
        "{0}: interrotto su richiesta. Quello che era già salvato resta.",
        "{0}: stopped on request. Whatever was already saved stays."),
    "work.model_recount": (
        "{0}: le previsioni salvate valgono ancora; cambia solo il modo di "
        "contarle, e i conti si rifanno senza rieseguire il modello.",
        "{0}: the saved predictions still hold; only the way of counting them "
        "has changed, so the figures are recomputed without running the model "
        "again."),
    "work.model_stale": (
        "{0}: il confronto salvato non vale per questo giro e viene rifatto. {1}",
        "{0}: the saved comparison does not apply to this run and is being "
        "recomputed. {1}"),
    "work.model_comparing": ("{0}: confronto le annotazioni…",
                             "{0}: comparing the annotations\u2026"),
    "work.model_done": (
        "{0} · lemmi uguali {1}% delle parole valutabili · copertura {2}%",
        "{0} \u00b7 lemmas equal on {1}% of evaluable words \u00b7 coverage {2}%"),
    "work.model_postag": ("{0} · etichette uguali {1}% delle parole valutabili",
                          "{0} \u00b7 tags equal on {1}% of evaluable words"),
    "work.model_postag_suspended": (
        "{0} · confronto delle etichette sospeso: {1}",
        "{0} \u00b7 tag comparison suspended: {1}"),
    "work.model_finished": ("{0}: fatto.", "{0}: done."),
    "work.model_sentence": ("{0} · frase {1} di {2} ({3})",
                            "{0} · sentence {1} of {2} ({3})"),
    "work.preparing": ("Preparo i dati…", "Preparing the data…"),
    "work.figures_written": ("Esportate {0} figure in {1}",
                             "Exported {0} figures to {1}"),
    "work.figures_done": ("Figure esportate.", "Figures exported."),


    # ── The line that summarises the search just made ─────────────────
    "query.form": ("forma {0} «{1}»", "form {0} “{1}”"),
    "query.lemma": ("lemma {0} «{1}»", "lemma {0} “{1}”"),
    "query.postag": ("postag {0}", "tag {0}"),
    "query.relation": ("relazione {0}", "relation {0}"),
    "query.head_lemma": ("testa con lemma «{0}»", "head with lemma “{0}”"),
    "query.head_relation": ("testa con relazione {0}", "head with relation {0}"),
    "query.none": ("nessun filtro", "no filter"),

    # ── The Greek constructions, explained ───────────────────────────
    "construction.genitivo assoluto.help": (
        "Participio al genitivo con relazione avverbiale che regge un soggetto "
        "anch'esso al genitivo: la costruzione assoluta per eccellenza.",
        "A genitive participle in an adverbial relation governing a subject "
        "that is also in the genitive: the absolute construction par excellence."),
    "construction.accusativo assoluto.help": (
        "Participio neutro all'accusativo in funzione avverbiale, tipico dei "
        "verbi impersonali (δέον, ἐξόν).",
        "A neuter accusative participle used adverbially, typical of impersonal "
        "verbs (δέον, ἐξόν)."),
    "construction.accusativo con infinito.help": (
        "Infinito che regge un soggetto all'accusativo: la proposizione "
        "infinitiva del greco.",
        "An infinitive governing a subject in the accusative: the Greek "
        "infinitival clause."),
    "construction.infinito articolare.help": (
        "Infinito preceduto dall'articolo, sostantivato.",
        "An infinitive preceded by the article, used as a noun."),
    "construction.participio sostantivato.help": (
        "Participio preceduto dall'articolo: «coloro che…».",
        "A participle preceded by the article: “those who…”."),
    "construction.participio predicativo.help": (
        "Participio in relazione ATV o AtvV, predicativo del soggetto o "
        "dell'oggetto.",
        "A participle in the ATV or AtvV relation, predicative of the subject "
        "or of the object."),
    "construction.perifrastica con εἰμί.help": (
        "Forma finita di εἰμί che regge un participio: perifrastica.",
        "A finite form of εἰμί governing a participle: the periphrastic."),
    "construction.schema attico.help": (
        "Soggetto neutro plurale con verbo al singolare: il σχῆμα Ἀττικόν. "
        "Utile due volte, come figura e come controllo dell'annotazione.",
        "A neuter plural subject with a singular verb: the σχῆμα Ἀττικόν. "
        "Useful twice over, as a figure and as a check on the annotation."),
    "construction.ἄν + modo.help": (
        "Tutte le occorrenze della particella modale: incrociandole con il modo "
        "del verbo reggente si ottiene la tabella dei periodi ipotetici.",
        "Every occurrence of the modal particle: crossed with the mood of the "
        "governing verb it yields the table of conditional sentences."),
    "construction.soggetto sottinteso.help": (
        "Verbi finiti privi di un soggetto espresso: la misura del pro-drop, "
        "che varia molto per genere e per persona.",
        "Finite verbs with no expressed subject: the measure of pro-drop, "
        "which varies a great deal by genre and by person."),


    # ── Category values that end up in a table and in a legend ────────
    #
    # They are data, not labels: they stay in Italian inside the DataFrame — the code
    # compares and filters on them — and are translated only at the moment they are
    # drawn.
    "value.tutti e tre d'accordo": ("tutti e tre d'accordo", "all three agree"),
    "value.corpus e Stanza contro UDPipe": ("corpus e Stanza contro UDPipe",
                                            "corpus and Stanza against UDPipe"),
    "value.corpus e UDPipe contro Stanza": ("corpus e UDPipe contro Stanza",
                                            "corpus and UDPipe against Stanza"),
    "value.i due modelli contro il corpus": ("i due modelli contro il corpus",
                                             "the two models against the corpus"),
    "value.tutti e tre diversi": ("tutti e tre diversi", "all three different"),
    "value.TOTALE allineati": ("TOTALE allineati", "TOTAL aligned"),
    "value.riproduce l'annotazione originale": (
        "riproduce l'annotazione originale", "reproduces the original annotation"),
    "value.converge sulla correzione": ("converge sulla correzione",
                                        "converges on the correction"),
    "value.propone un terzo valore": ("propone un terzo valore",
                                      "proposes a third value"),
    "value.TOTALE token modificati": ("TOTALE record modificati",
                                      "TOTAL changed records"),
    "value.Corpus corretto": ("Versione revisionata", "Revised corpus"),
    "value.Sconosciuto": ("Sconosciuto", "Unknown"),
    "value.Unknown": ("Sconosciuto", "Unknown"),


    # ── Messages that the engine sends to a warning window ────────────
    "gold.err.nothing_to_save": (
        "Non c'è nessuna versione revisionata da salvare. Applica prima le "
        "correzioni nella scheda «Correggi».",
        "There is no revised corpus to save. Apply the corrections in the "
        "«Correct» step first."),
    "gold.err.not_a_bundle": (
        "Questo file non sembra un pacchetto prodotto da GCP: manca {0}.",
        "This file does not look like a bundle produced by GCP: {0} is "
        "missing."),
    "gold.err.incomplete": (
        "Il file non contiene la versione revisionata: il pacchetto è "
        "incompleto.",
        "The file does not hold the revised corpus: the bundle is "
        "incomplete."),
    "github.err.download": (
        "Non riesco a scaricare {0} da {1}: {2}. Controlla la connessione, "
        "oppure scarica il repository a mano e caricalo come cartella.",
        "Could not download {0} from {1}: {2}. Check the connection, or "
        "download the repository by hand and load it as a folder."),
    "conllu.err.udapi": (
        "La conversione allo schema Universal Dependencies richiede il "
        "pacchetto udapi-agldt, che non risulta installato. "
        "L'esportazione in formato CoNLL-U con l'annotazione AGDT "
        "originale è comunque disponibile e non richiede nulla.",
        "Converting to the Universal Dependencies scheme needs the "
        "udapi-agldt package, which does not appear to be installed. Export "
        "to CoNLL-U with the original AGDT annotation is available anyway and "
        "needs nothing."),

    "table.true": ("Corretto", "Correct"),
    "table.false": ("Errato", "Wrong"),

    # ── Texts drawn inside the figures (figures.py) ───────────────────
    "fig.title.family": ("Segnalazioni per famiglia di controllo",
                         "Findings by family of check"),
    "fig.title.class": ("Segnalazioni per classe diagnostica",
                        "Findings by diagnostic class"),
    "fig.title.rule": ("I {0} controlli che segnalano di più",
                       "The {0} checks that report most"),
    "fig.title.density": ("Densità di segnalazioni per documento",
                          "Anomaly density by document"),
    "fig.title.profile_by": ("Profilo morfologico per {0}",
                             "Morphological profile by {0}"),
    "fig.title.slot_agreement": ("Accordo per posizione dell'etichetta",
                                 "Agreement by position of the tag"),
    "fig.title.model_agreement": ("Accordo fra corpus e modelli",
                                  "Agreement between corpus and models"),
    "fig.title.three_way": ("Corpus, Stanza e UDPipe sulle stesse parole",
                            "Corpus, Stanza and UDPipe on the same words"),
    "fig.title.noise": ("Sulle parole corrette dalle regole, che cosa fa {0}?",
                        "On the words the rules corrected, what does {0} do?"),
    "fig.title.sentence_length": ("Distribuzione della lunghezza delle frasi",
                                  "Distribution of sentence length"),
    "fig.title.distance": ("Distanza fra testa e dipendente",
                           "Distance between head and dependent"),
    "fig.title.cases": ("Distribuzione dei casi", "Case distribution"),
    "fig.title.moods": ("Distribuzione dei modi verbali", "Verbal mood distribution"),
    "fig.title.tenses": ("Distribuzione dei tempi verbali", "Verbal tense distribution"),
    "fig.axis.findings_count": ("numero di segnalazioni", "number of findings"),
    "fig.axis.per_ten_thousand": ("segnalazioni ogni 10.000 record attivi",
                                  "findings per 10,000 active records"),
    "fig.axis.token_share": ("% delle parole", "% of the words"),
    "fig.axis.aligned_share": ("% delle parole allineate", "% of the aligned words"),
    "fig.axis.changed_share": ("% dei record modificati", "% of the changed records"),
    "fig.axis.tokens_per_sentence": ("parole per frase", "words per sentence"),
    "fig.axis.distance_tokens": ("record di distanza", "records of distance"),
    "fig.axis.arcs": ("archi", "arcs"),
    "fig.axis.sentences": ("frasi", "sentences"),
    "fig.axis.tokens_read": ("record letti", "records read"),
    "fig.axis.distinct_lemmas": ("lemmi distinti", "distinct lemmas"),
    "fig.axis.lemma_rank": ("rango del lemma", "lemma rank"),
    "fig.axis.frequency": ("frequenza", "frequency"),
    "fig.axis.agreement_share": ("% di accordo", "% agreement"),
    "fig.axis.own_share": ("% del proprio {0}", "% of its own {0}"),
    "fig.empty.no_findings_yet": ("Nessuna segnalazione: esegui prima il controllo",
                                  "No findings: run the check first"),
    "fig.empty.no_findings": ("Nessuna segnalazione", "No findings"),
    "fig.empty.run_models": ("Esegui prima i modelli", "Run the models first"),
    "fig.empty.run_both": ("Esegui Stanza e UDPipe per vedere questo grafico",
                           "Run Stanza and UDPipe to see this chart"),
    "fig.empty.need_analysis": ("Servono l'analisi e almeno un modello",
                                "The analysis and at least one model are needed"),
    "fig.empty.no_data": ("Nessun dato", "No data"),
    "fig.empty.no_group_for_curve": (
        "Nessun gruppo abbastanza grande per questa curva",
        "No group is large enough for this curve"),
    "fig.median": ("mediana {0}", "median {0}"),
    "fig.progress": ("Figura {0}", "Figure {0}"),
    "fig.the_model": ("il modello", "the model"),

    # ── Captions of the figures of the article ────────────────────────
    "figcap.01-anomalie-per-famiglia": (
        "Segnalazioni prodotte dai controlli diagnostici, raggruppate per "
        "famiglia. Le famiglie corrispondono ai cinque piani su cui la pipeline "
        "interroga un treebank: morfologia, lemmatizzazione, struttura "
        "sintattica, testo e codifica, accordo e reggenza.",
        "Findings produced by the diagnostic checks, grouped by family. The "
        "families correspond to the five levels at which the pipeline "
        "interrogates a treebank: morphology, lemmatisation, syntactic "
        "structure, text and encoding, agreement and government."),
    "figcap.02-anomalie-per-livello": (
        "Le stesse segnalazioni ordinate per classe diagnostica. La classe dice "
        "che cosa il programma può affermare: una violazione verificabile "
        "contraddice una regola esplicita dello schema, una variante sistematica "
        "segue una convenzione regolare del corpus, un caso da verificare è un "
        "punto sospetto su cui decide il contesto.",
        "The same findings ordered by diagnostic class. The class says what the "
        "program can assert: a verifiable violation breaks an explicit rule of "
        "the scheme, a systematic variant follows a regular convention of the "
        "corpus, a case to check is a suspicious point the context decides."),
    "figcap.03-anomalie-per-regola": (
        "I controlli che segnalano di più, uno per uno.",
        "The checks that report most, one by one."),
    "figcap.04-densita-per-documento": (
        "Densità di segnalazioni per documento, ogni 10.000 record attivi. È il "
        "tasso che il giro dichiara, sulla stessa unità e con lo stesso "
        "fattore. La normalizzazione è necessaria: senza di essa la classifica "
        "misura la lunghezza dei testi, non la qualità dell'annotazione.",
        "Findings per document, per 10,000 active records. It is the rate the "
        "run declares, on the same unit and with the same factor. The "
        "normalisation is necessary: without it the ranking measures the "
        "length of the texts, not the quality of the annotation."),
    "figcap.05-distribuzione-casi": (
        "Distribuzione dei casi sui nominali del corpus.",
        "Distribution of the cases over the nominals of the corpus."),
    "figcap.06-distribuzione-modi": (
        "Distribuzione dei modi verbali.",
        "Distribution of the verbal moods."),
    "figcap.07-distribuzione-tempi": (
        "Distribuzione dei tempi verbali.",
        "Distribution of the verbal tenses."),
    "figcap.08-relazioni-sintattiche": (
        "Frequenza delle funzioni sintattiche: l'impronta sintattica del corpus.",
        "Frequency of the syntactic functions: the syntactic fingerprint of "
        "the corpus."),
    "figcap.09-lunghezza-frasi": (
        "Distribuzione della lunghezza delle frasi, esclusa la punteggiatura.",
        "Distribution of sentence length, punctuation excluded."),
    "figcap.10-distanza-dipendenze": (
        "Distribuzione della distanza lineare fra testa e dipendente. Su una "
        "lingua a ordine libero questa distribuzione è la misura quantitativa "
        "dell'iperbato.",
        "Distribution of the linear distance between head and dependent. In a "
        "free word-order language this distribution is the quantitative "
        "measure of hyperbaton."),
    "figcap.11-profilo-per-periodo": (
        "Profilo morfologico per periodo linguistico. Il rapporto "
        "genitivi/dativi e l'indice di ottativo sono i due marcatori diacronici "
        "più netti fra quelli calcolabili da un treebank.",
        "Morphological profile by linguistic period. The genitive/dative "
        "ratio and the optative index are the two sharpest diachronic markers "
        "among those a treebank can compute."),
    "figcap.12-accordo-modelli": (
        "Accordo fra corpus, Stanza e UDPipe, per autore. La scala è centrata "
        "sulla media osservata, così gli scarti si leggono come direzioni e non "
        "come sfumature.",
        "Agreement between corpus, Stanza and UDPipe, by author. The scale is "
        "centred on the observed mean, so that departures read as directions "
        "rather than as shades."),
    "figcap.13-tre-vie": (
        "Corpus, Stanza e UDPipe sulle stesse parole. La categoria «i due "
        "modelli contro il corpus» è il segnale non supervisionato più forte "
        "che l'annotazione meriti una seconda lettura.",
        "Corpus, Stanza and UDPipe on the same words. The category “the two "
        "models against the corpus” is the strongest unsupervised signal that "
        "the annotation deserves a second reading."),
    "figcap.14-rumore-replicato": (
        "Sulle parole che le regole automatiche hanno modificato: il modello "
        "riproduce l'annotazione originale, converge sulla correzione, oppure "
        "propone un terzo valore.",
        "On the words the automatic rules changed: the model reproduces the "
        "original annotation, converges on the correction, or proposes a "
        "third value."),
    "figcap.15-accordo-per-posizione": (
        "Accordo fra le due fonti su ciascuna delle nove posizioni "
        "dell'etichetta, calcolato sulle sole parole in cui almeno una delle due "
        "marca quel tratto.",
        "Agreement between the two sources on each of the nine positions of "
        "the tag, computed only on the words where at least one of the two "
        "marks that feature."),

    # ── Field names: table headers and list entries ───────────────────
    #
    # The analysis engine names its columns in Italian; these names are internal data
    # identifiers. Translating them here — at the moment they are drawn, and not in the
    # data — leaves the rest intact: the filter, the order and the export continue to
    # see the original name of the column.
    #
    # ── the syntactic measures, as the backend names them ─────────────
    "column.legami utilizzabili": (
        "legami utilizzabili", "usable links"),
    "column.legami misurati": (
        "legami di cui si è misurata la proiettività",
        "links whose projectivity was measured"),
    "column.relazioni distinte": ("etichette di relazione distinte",
                                  "distinct relation labels"),
    "column.funzioni distinte (suffisso tolto)": (
        "funzioni distinte, suffisso tolto", "distinct functions, suffix stripped"),
    "column.legami non proiettivi": ("legami non proiettivi", "non-projective links"),
    "column.% legami non proiettivi": (
        "% legami non proiettivi, sui legami utilizzabili",
        "% non-projective links, out of the usable links"),
    "column.frasi con almeno un legame non proiettivo": (
        "frasi con almeno un legame non proiettivo",
        "sentences with at least one non-projective link"),
    "column.% frasi con almeno un legame non proiettivo": (
        "% frasi non proiettive, sulle frasi con archi utilizzabili",
        "% non-projective sentences, out of sentences with usable links"),
    "column.frasi nel gruppo": ("frasi nel gruppo", "sentences in the group"),
    "column.frasi con archi": ("frasi con archi utilizzabili",
                               "sentences with usable links"),
    "column.frasi senza archi": ("frasi senza archi utilizzabili",
                                 "sentences without usable links"),
    "column.n_etichette": ("etichette distinte", "distinct labels"),
    "column.%": ("%", "%"),
    "column.% cumulativa": ("% cumulativa", "cumulative %"),
    "column.per 10.000": ("per 10.000", "per 10,000"),
    "column.grafia": ("grafia", "spelling"),
    "column.grafie": ("grafie", "spellings"),
    "column.direzione": ("direzione", "direction"),
    "column.co-occorrenze": ("co-occorrenze", "joint occurrences"),
    "column.lemma associato": ("lemma associato", "associated lemma"),
    "column.occorrenze del lemma associato": (
        "occorrenze del lemma associato", "occurrences of the associated lemma"),
    "column.occorrenze lemma": ("occorrenze del lemma", "occurrences of the lemma"),
    "column.logDice": ("logDice", "logDice"),

    # ── the values that the backend uses as keys and the interface shows ───
    "value.dipendente": ("dipendente", "dependent"),
    "value.testa": ("testa", "head"),
    "value.morfologia": ("morfologia", "morphology"),
    "value.posizione": ("posizione", "tag slot"),
    "value.dipendenza": ("dipendenza", "dependency"),
    "value.lemma": ("lemma", "lemma"),
    "value.nessun filtro": ("nessun filtro", "no filter"),
    "value.senza parole funzionali": ("senza parole funzionali",
                                      "without function words"),
    "value.solo parole di contenuto": ("solo parole di contenuto",
                                       "content words only"),
    "value.lista personalizzata": ("lista personalizzata", "custom list"),
    "value.senza_archi": ("nessun arco calcolato per queste frasi",
                          "no links computed for these sentences"),
    "value.corpus_senza_archi": (
        "il corpus non ha archi calcolati: senza di quelli la proiettività non si misura",
        "the corpus has no computed links: without them projectivity cannot be measured"),
    "value.frasi_non_utilizzabili": (
        "frasi di un solo record, o con la testa mancante o fuori frase: senza un "
        "legame utilizzabile non entrano nel conto",
        "one-record sentences, or sentences whose head is missing or outside the "
        "sentence: without a usable link they do not enter the count"),

    "stats.universo.morfologia": (
        "Si conta sulle parole del testo: i record attivi meno la punteggiatura "
        "e i record tecnici. Sotto ogni tabella c'è il totale su cui la "
        "distribuzione è calcolata, che cambia da posizione a posizione perché "
        "una posizione vale solo per le parti del discorso che la usano.",
        "Counted on the words of the text: the active records minus punctuation "
        "and technical records. Under each table is the total the distribution "
        "is computed on, which differs from slot to slot because a slot only "
        "applies to the parts of speech that use it."),
    "stats.universo.sintassi": (
        "Il denominatore sono i legami utilizzabili, cioè i record attivi la cui "
        "testa esiste come record della stessa frase. È la stessa unità con cui "
        "il programma conta i legami dappertutto. La proiettività si legge nella "
        "tabella degli archi, che non copre ogni legame utilizzabile: quanti ne "
        "ha guardati lo dice «legami di cui si è misurata la proiettività».",
        "The denominator is the usable links, that is the active records whose "
        "head exists as a record of the same sentence. It is the same unit the "
        "program counts links with everywhere. Projectivity is read from the arc "
        "table, which does not cover every usable link: how many it looked at is "
        "what “links whose projectivity was measured” says."),
    "stats.universo.frequenza": (
        "Si conta sulle parole del testo, non sui record importati: la "
        "punteggiatura e i record tecnici restano fuori dagli elenchi di "
        "frequenza.",
        "Counted on the words of the text, not on the imported records: "
        "punctuation and technical records stay out of the frequency lists."),
    "stats.universo.parola": (
        "Le occorrenze del lemma si contano fra le parole; le co-occorrenze "
        "sono archi fra due parole.",
        "Occurrences of the lemma are counted among the words; joint "
        "frequencies are links between two words."),

    "column.famiglia": ("famiglia", "family"),
    "column.livello": ("livello", "level"),
    "column.classe diagnostica": ("classe diagnostica", "diagnostic class"),
    "column.classe": ("classe", "class"),
    "column.trattamento": ("trattamento", "treatment"),
    "column.controllo diagnostico": ("controllo diagnostico", "diagnostic check"),
    "column.che cosa controlla": ("che cosa controlla", "what it checks"),
    "column.gravità": ("gravità", "severity"),
    # The three columns of the diagnosis in the export. “issue” is the sentence, in the
    # language in which it is exported; the other two are the same thing in a form
    # readable by a program, and do not change language because they are data and not
    # text.
    "column.issue": ("che cosa non torna", "what does not add up"),
    "column.issue_key": ("chiave della diagnosi", "diagnosis key"),
    "column.issue_params": ("valori della diagnosi", "diagnosis values"),
    "column.motivo della segnalazione": ("motivo della segnalazione",
                                         "reason for the finding"),
    "column.segnalazioni": ("segnalazioni", "findings"),
    "column.regola": ("regola", "rule"),
    "column.documenti": ("documenti", "documents"),
    "column.opere": ("opere", "works"),
    "column.lemmi": ("lemmi", "lemmas"),
    "column.ragione": ("ragione", "reason"),
    "value.non è una parola": ("non è una parola", "not a word"),
    "value.elenco dei lemmi grammaticali": ("elenco dei lemmi grammaticali",
                                            "list of grammatical lemmas"),
    "value.parte del discorso": ("parte del discorso", "part of speech"),
    "column.documento": ("documento", "document"),
    "column.forme": ("forme", "forms"),
    "column.forme_uniche": ("forme uniche", "unique forms"),
    "column.lemmi_unici": ("lemmi unici", "unique lemmas"),
    "column.data_inizio": ("data inizio", "start date"),
    "column.data_fine": ("data fine", "end date"),
    "column.fonte_metadati": ("fonte metadati", "metadata source"),
    "column.nota_metadati": ("nota metadati", "metadata note"),
    "column.autore_en": ("autore en", "author (English)"),
    "column.opera_en": ("opera en", "work (English)"),
    "column.forma": ("forma", "form"),
    "column.parola": ("parola", "word"),
    "column.sinistra": ("sinistra", "left"),
    "column.destra": ("destra", "right"),
    "column.analisi": ("analisi", "analysis"),
    "column.relazione": ("relazione", "relation"),
    "column.funzione": ("funzione", "function"),
    "column.testa": ("testa", "head"),
    "column.frase": ("frase", "sentence"),
    "column.frasi": ("frasi", "sentences"),
    "column.autore": ("autore", "author (Italian)"),
    "column.opera": ("opera", "work (Italian)"),
    "column.datazione": ("datazione", "date"),
    "column.secolo": ("secolo", "century"),
    "column.periodo": ("periodo", "period"),
    "column.dialetto": ("dialetto", "dialect"),
    "column.genere": ("genere", "genre"),
    "column.provenienza": ("provenienza", "provenance"),
    "column.editore": ("editore", "editor"),
    "column.note": ("note", "notes"),
    "column.token": ("parole", "words"),
    "column.token (tutto)": ("record importati", "imported records"),
    "column.token (parole)": ("parole", "words"),
    "column.token allineati": ("parole allineate", "aligned words"),
    "column.token confrontati": ("parole confrontate", "compared words"),
    "column.token per frase": ("parole per frase", "words per sentence"),
    "column.per 1.000 token": ("per 1.000 parole", "per 1,000 words"),
    "column.forme distinte": ("forme distinte", "distinct forms"),
    "column.lemmi distinti": ("lemmi distinti", "distinct lemmas"),
    "column.lemmi mancanti": ("lemmi mancanti", "missing lemmas"),
    "column.postag mancanti": ("postag mancanti", "missing tags"),
    "column.lunghezza mediana frase": ("lunghezza mediana frase",
                                       "median sentence length"),
    "column.frase più lunga": ("frase più lunga", "longest sentence"),
    "column.occorrenze": ("occorrenze", "occurrences"),
    "column.etichetta": ("etichetta", "tag"),
    "column.etichetta A": ("etichetta A", "tag A"),
    "column.etichetta B": ("etichetta B", "tag B"),
    "column.etichette": ("etichette", "tags"),
    "column.nucleo": ("nucleo", "nucleus"),
    "column.nuclei": ("nuclei", "nuclei"),
    "column.chiave": ("chiave", "key"),
    "column.varianti": ("varianti", "variants"),
    "column.esempio": ("esempio", "example"),
    "column.esempi": ("esempi", "examples"),
    "column.un esempio": ("un esempio", "an example"),
    "column.categoria": ("categoria", "category"),
    "column.valore": ("valore", "value"),
    "column.tipo": ("tipo", "kind"),
    "column.tipi": ("tipi", "types"),
    "column.campo": ("campo", "field"),
    "column.posizione": ("posizione", "position"),
    "column.tratto": ("tratto", "feature"),
    "column.carattere": ("carattere", "character"),
    "column.significato": ("significato", "meaning"),
    "column.totale": ("totale", "total"),
    "column.caso": ("caso", "case"),
    "column.preposizione": ("preposizione", "preposition"),
    "column.verbo": ("verbo", "verb"),
    "column.congiunzione": ("congiunzione", "conjunction"),
    "column.modo": ("modo", "mood"),
    "column.distribuzione": ("distribuzione", "distribution"),
    "column.rango": ("rango", "rank"),
    "column.frequenza": ("frequenza", "frequency"),
    "column.frequenza corretta": ("frequenza corretta", "adjusted frequency"),
    "column.copertura del testo": ("copertura del testo", "text coverage"),
    "column.hapax interni": ("hapax interni", "internal hapax"),
    "column.hapax del corpus": ("hapax del corpus", "corpus hapax"),
    "column.hapax interni / tipi": ("hapax interni / tipi", "internal hapax / types"),
    "column.hapax corpus per 10.000": ("hapax corpus per 10.000",
                                       "corpus hapax per 10,000"),
    "column.hapax / tipi": ("hapax / tipi", "hapax / types"),
    "column.hapax / token": ("hapax ÷ parole", "hapax ÷ words"),
    "column.verbi finiti": ("verbi finiti", "finite verbs"),
    "column.verbi finiti subordinati": ("verbi finiti subordinati",
                                        "subordinate finite verbs"),
    "column.congiunzioni subordinanti per frase": (
        "congiunzioni subordinanti per frase",
        "subordinating conjunctions per sentence"),
    "column.coordinanti per frase": ("coordinanti per frase",
                                     "coordinators per sentence"),
    "column.coordinante": ("coordinante", "coordinator"),
    "column.subordinato": ("subordinato", "subordinate"),
    "column.finito": ("finito", "finite"),
    "column.clausole": ("clausole", "clauses"),
    "column.profondità massima": ("profondità massima", "maximum depth"),
    "column.profondità media": ("profondità media", "mean depth"),
    "column.profondità massima media": ("profondità massima media",
                                        "mean maximum depth"),
    "column.distanza media testa-dipendente": ("distanza media testa-dipendente",
                                               "mean head-dependent distance"),
    "column.distanza media": ("distanza media", "mean distance"),
    "column.distanza massima": ("distanza massima", "maximum distance"),
    "column.archi": ("archi", "arcs"),
    "column.archi non proiettivi": ("archi non proiettivi", "non-projective arcs"),
    "column.ordine": ("ordine", "order"),
    "column.dipendenti": ("dipendenti", "dependents"),
    "column.teste": ("teste", "heads"),
    "column.modello": ("modello", "model"),
    "column.esito": ("esito", "outcome"),
    "column.accordo": ("accordo", "agreement"),
    "column.accordo con il gold %": ("accordo con il gold %", "agreement with gold %"),
    "column.accordo con l'originale %": ("accordo con l'originale %",
                                         "agreement with the original %"),
    "column.valore nel corpus": ("valore nel corpus", "value in the corpus"),
    "column.valore dei modelli": ("valore dei modelli", "value in the models"),
    "column.originale": ("originale", "original"),
    "column.corretto": ("corretto", "corrected"),
    "column.differenza": ("differenza", "difference"),
    "column.n nel target": ("n nel target", "n in the target"),
    "column.n nel riferimento": ("n nel riferimento", "n in the reference"),
    "column.range (parti)": ("range (parti)", "range (parts)"),
    "column.% lemmi uguali": ("% lemmi uguali", "% identical lemmas"),
    "column.lemmi diversi": ("lemmi diversi", "differing lemmas"),
    "column.% postag uguali": ("% postag uguali", "% identical tags"),
    "column.postag diversi": ("postag diversi", "differing tags"),
    "column.a (pendenza)": ("a (pendenza)", "a (slope)"),

    # ── Rules page: the two axes of the taxonomy, in full ────────────
    "rules.levels_explained": ("""
Ogni controllo porta due etichette che rispondono a due domande diverse, e
tenerle separate è il punto: <b>che genere di segnalazione è</b>, e <b>che cosa
si può farne</b>.<br><br>
<b>La classe diagnostica.</b><br>
<b>1. Violazione verificabile.</b> Il dato infrange una regola esplicita dello
schema, oppure manca un campo necessario. Si verifica senza interpretare il
testo: un'etichetta di nove caratteri che ne ha otto, un valore fuori
dall'inventario dichiarato, un record senza testa, una frase senza radice.<br>
<b>2. Variante sistematica.</b> Il dato è sistematico e coerente, ma segue
una convenzione diversa da quella presa come riferimento. Non è
necessariamente un errore, e spesso porta un'informazione che lo schema di
riferimento non può contenere: ricondurlo è una decisione su che cosa il corpus
dovrà servire, e la prende chi legge.<br>
<b>3. Caso da verificare.</b> Il controllo ha trovato un punto su cui vale la
pena guardare, ma solo il contesto dice se qualcosa non va. Non conta come
errore in nessun totale.<br><br>
<b>Il trattamento.</b><br>
<b>Correzione automatica</b>: una sola risposta giusta, nota in anticipo; il
programma la scrive e chi legge può disfarla.<br>
<b>Normalizzazione su scelta</b>: una riconduzione allo schema di riferimento
che va decisa, perché costa qualcosa.<br>
<b>Revisione manuale</b>: nessun intervento automatico è possibile o
difendibile.<br><br>
I due assi si incrociano liberamente, ed è la ragione per cui sono due. Una
relazione sintattica assente è una violazione certa dello schema e <i>non</i> è
correggibile automaticamente, perché non c'è modo di indovinare quale relazione
ci fosse; un lemma con il numero del lemmatizzatore in coda non è un errore
affatto e si normalizza senza pensarci.
""", """
Every check carries two labels answering two different questions, and keeping
them apart is the point: <b>what kind of finding it is</b>, and <b>what can be
done about it</b>.<br><br>
<b>The diagnostic class.</b><br>
<b>1. Verifiable violation.</b> The data breaks an explicit rule of the
scheme, or a required field is missing. It can be verified without
interpreting the text: a nine-character tag that has eight, a value outside
the declared inventory, a record with no head, a sentence with no root.<br>
<b>2. Systematic variant.</b> The data is systematic and coherent, but it
follows a convention other than the one taken as the reference. It is not
necessarily an error, and it often carries information the reference scheme
cannot hold: bringing it into line is a decision about what the corpus is to
serve, and the reader is the one who takes it.<br>
<b>3. Case to check.</b> The check has found a place worth looking at, but
only the context says whether anything is wrong. It counts as an error in no
total.<br><br>
<b>The treatment.</b><br>
<b>Automatic correction</b>: one right answer, known in advance; the program
writes it and the reader can undo it.<br>
<b>Normalisation by choice</b>: a mapping onto the reference scheme that has
to be decided, because it costs something.<br>
<b>Manual review</b>: no automatic action is possible or defensible.<br><br>
The two axes cross freely, and that is the reason there are two of them. A
missing syntactic relation is a certain violation of the scheme and is
<i>not</i> automatically correctable, because there is no way to guess which
relation was there; a lemma with the lemmatiser's number trailing after it is
not an error at all and is normalised without a second thought.
"""),
}


class Translator:
    """Holds the current language and hands out strings."""

    def __init__(self, language: str = "en") -> None:
        self.language = language if language in LANGUAGES else "en"
        self._listeners: list[Callable[[str], None]] = []

    def set_language(self, language: str) -> None:
        if language not in LANGUAGES or language == self.language:
            return
        self.language = language
        for listener in list(self._listeners):
            try:
                listener(language)
            except Exception:
                # A misbehaving page must not stop the others from re-rendering.
                pass

    def on_change(self, callback: Callable[[str], None]) -> None:
        self._listeners.append(callback)

    def __call__(self, key: str, *args: object) -> str:
        entry = _STRINGS.get(key)
        if entry is None:
            return key
        text = entry[0] if self.language == "it" else entry[1]
        if args:
            try:
                return text.format(*args)
            except Exception:
                return text
        return text


#: The single translator the whole interface shares.
T = Translator()


def tr(key: str, *args: object) -> str:
    return T(key, *args)


def pick(pair: tuple[str, str] | list) -> str:
    """Italian or English, from a pair declared elsewhere.

    The AGDT scheme — names of the positions, admitted values, relations — already
    carries its labels in two languages, as ``(Italian, English)`` pairs. The interface
    must take the element that matches the chosen language, otherwise dropdowns and
    tables would stay in Italian after the language is changed. This function is the
    point where that choice is made once only.
    """
    if not isinstance(pair, (tuple, list)) or len(pair) < 2:
        return str(pair)
    return str(pair[0] if T.language == "it" else pair[1])


# ── Entries added by the page modules ───────────────────────────────────────
#
# The large pages keep their own entries in separate files, so that this one stays of a
# manageable size. Each module exposes a dictionary ``STRINGS`` with the same shape as
# ``_STRINGS``: dotted key -> (Italian, English).
_MODULI_EXTRA = ("i18n_panoramica", "i18n_correggi", "i18n_cerca", "i18n_struttura")
for _nome in _MODULI_EXTRA:
    try:
        _modulo = __import__(f"gui_qt.{_nome}", fromlist=["STRINGS"])
    except ModuleNotFoundError:
        continue
    _STRINGS.update(getattr(_modulo, "STRINGS", {}))


#: The singular and plural of what the program counts, in the two languages.
#:
#: It is needed because a count without number agreement (“1 documents”, “2 documento”)
#: is wrong in both languages, and because the name of the unit cannot be “token”: a
#: token is none of the five units with which the program counts, and writing it leaves
#: the reader without knowing what they are looking at.
_PLURALI: dict[str, tuple[tuple[str, str], tuple[str, str]]] = {
    "documento": (("documento", "documenti"), ("document", "documents")),
    "frase": (("frase", "frasi"), ("sentence", "sentences")),
    "parola": (("parola", "parole"), ("word", "words")),
    "record_importato": (("record importato", "record importati"),
                         ("imported record", "imported records")),
    "record_attivo": (("record attivo", "record attivi"),
                      ("active record", "active records")),
    "legame": (("legame utilizzabile", "legami utilizzabili"),
               ("usable link", "usable links")),
    "nucleo": (("nucleo", "nuclei"), ("nucleus", "nuclei")),
    "segnalazione": (("segnalazione", "segnalazioni"), ("finding", "findings")),
    "controllo": (("controllo", "controlli"), ("check", "checks")),
    "riga": (("riga", "righe"), ("row", "rows")),
}


def number(value: object) -> str:
    """A number as written by the chosen language.

    Italian separates the thousands with a full stop, English with a comma. Writing the
    thousands with a full stop whatever the language would make an English reader read
    “16.191” as sixteen point one.
    """
    try:
        intero = int(value)
    except (TypeError, ValueError):
        return str(value)
    testo = f"{intero:,}"
    return testo.replace(",", ".") if T.language == "it" else testo


def decimal(value: object) -> str:
    """A number written with a full stop, as the chosen language writes its decimals.

    Italian puts a comma between the integer and the fraction; English keeps the
    full stop.  The argument is text or a number already formatted with a full stop.
    """
    text = str(value)
    return text.replace(".", ",") if T.language == "it" else text


def counted(kind: str, value: object) -> str:
    """“2 documenti” in Italian, “2 documents” in English, and “1 documento”.

    *kind* is a key of :data:`_PLURALI`. A key that is not there comes back as a
    bare number, visibly incomplete instead of silently wrong.
    """
    forme = _PLURALI.get(kind)
    quanti = number(value)
    if forme is None:
        return quanti
    singolare, plurale = forme[0] if T.language == "it" else forme[1]
    try:
        uno = int(value) == 1
    except (TypeError, ValueError):
        uno = False
    return f"{quanti} {singolare if uno else plurale}"


def data_label(name: object) -> str:
    """The name of a field — table column or list entry — translated.

    Tables come from the analysis, and the analysis names its columns in Italian.
    Translating here, at the moment the header is drawn, leaves the data intact: the
    filter, the sorting and the CSV export continue to see the original name of the
    column, and only what is read changes language. A name for which there is no entry
    comes back as it was.
    """
    text = str(name)
    entry = _STRINGS.get("column." + text)
    if entry is None:
        return text
    return entry[0] if T.language == "it" else entry[1]


def value_label(value: object) -> str:
    """A category value as it is read, not as it is written in the data.

    Twin of :func:`data_label`, and for the same reason: the categories that the
    comparison between models produces — “the two models against the corpus” — are keys
    on which the code filters, and translating them in the data would break the filter.
    They are translated here, on a copy, just before they are drawn.
    """
    text = str(value)
    entry = _STRINGS.get("value." + text)
    if entry is None:
        return _schema_label(text)
    return entry[0] if T.language == "it" else entry[1]


_SCHEMA_EN: dict[str, str] | None = None
_NOT_IN_SCHEME = re.compile(r"^valore non previsto \((.*)\)$")


def _schema_label(text: str) -> str:
    """The English name of a label of the AGDT scheme, when the language is English.

    The statistics name the values of the tag in Italian (the data language of the
    analysis); ``agdt_schema`` holds the English twin of every label, and this is where
    the two are put side by side.  No label of the scheme is ambiguous: the table is
    built once.
    """
    global _SCHEMA_EN
    if T.language == "it":
        return text
    if _SCHEMA_EN is None:
        from greek_corpus_pipeline.agdt_schema import POSITION_NAMES, POSITION_VALUES
        table: dict[str, str] = {}
        for names in POSITION_VALUES.values():
            for italiano, inglese in names.values():
                table[italiano] = inglese
        for italiano, inglese in POSITION_NAMES.values():
            table[italiano] = inglese
        _SCHEMA_EN = table
    translated = _SCHEMA_EN.get(text)
    if translated is not None:
        return translated
    match = _NOT_IN_SCHEME.match(text)
    if match:
        return f"value not in the scheme ({match.group(1)})"
    return text
