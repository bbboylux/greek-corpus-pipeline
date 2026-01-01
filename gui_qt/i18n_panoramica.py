# -*- coding: utf-8 -*-
"""The entries of the overview and of the statistics, in Italian and in English.

It is kept apart from ``i18n.py`` for the reason given at the end of that file:
the large pages keep their own entries in separate modules, so that the general
dictionary stays of a manageable size. ``i18n.py`` imports this module by itself
and pours its content into the general dictionary; each key is written in one
place only.

Three groups of entries:

``overview.*``   the section “what the filter leaves out” and the labels of the
                 headline numbers, which say *what* they count;
``column.*``     the names of the columns and of the list entries. They are the
                 names that the analysis writes in the data, translated at the
                 moment they are drawn (:func:`gui_qt.i18n.data_label`): the
                 filter, the sorting and the export continue to see the
                 original name;
``stats.explain.*`` the extended explanation of a measure, the one that appears
                 when the mouse is moved over the row. It is written for whoever
                 has never done statistics: what is counted, divided by what,
                 and what a high value means.

The reason for so much insistence: “TTR lemmas” is not the name of anything for
someone who reads Greek, and a number without a unit — “mean sentence length:
12.4” — can neither be cited nor compared, because it is not known whether it
counts punctuation.
"""
from __future__ import annotations

STRINGS: dict[str, tuple[str, str]] = {

    # ══ Overview: what the filter leaves out ═════════════════════════════
    #
    # The three counts are always shown, with the filter on or off. Off, the number says
    # how many there are and stay in; on, how many are removed. A mute “0” would say
    # neither.
    "overview.excluded": ("Che cosa il filtro lascia fuori",
                          "What the filter leaves out"),
    "overview.excluded.hint": (
        "Le tre categorie che la pagina di caricamento permette di escludere, contate qui una per una sull'intero corpus. Le categorie si sovrappongono (un nodo ellittico vuoto non ha caratteri greci, e la punteggiatura nemmeno) quindi i tre numeri contano ciascuno la propria categoria per intero e non vanno sommati.",
        "The three categories the load page lets you exclude, counted here one by one over the whole corpus. The categories overlap (an empty elliptic node has no Greek letters, and neither has punctuation) so each of the three numbers counts its own category in full, and they are not meant to be added up."),
    "overview.excluded.total": (
        "In tutto la diagnosi lascia fuori {0} record sui {1} del corpus.",
        "In all, the diagnosis leaves out {0} records of the corpus's {1}."),
    "overview.excluded.none": (
        "Nessun filtro è attivo: la diagnosi guarda tutti i {0} record.",
        "No filter is on: the diagnosis looks at all {0} records."),

    "overview.excluded.elliptic.on": ("Nodi ellittici esclusi dall'analisi",
                                      "Elliptic nodes left out of the analysis"),
    "overview.excluded.elliptic.off": (
        "Nodi ellittici presenti (il filtro è spento: restano nell'analisi)",
        "Elliptic nodes present (the filter is off: they stay in the analysis)"),
    "overview.excluded.elliptic.tip": (
        "Record che il file dichiara come non-parole del testo: il segnaposto "
        "vuoto [0], i nodi con l'attributo artificial (anche quando portano la "
        "parola che l'annotatore ha aggiunto), l'etichetta morfologica che "
        "comincia per «z», il marcatore di lacuna «G» / «G?» e i record senza "
        "forma e senza etichetta. Sono gli stessi criteri che usa il filtro "
        "della diagnosi, quindi il numero qui e il numero là coincidono.",
        "Records the file declares not to be words of the text: the empty [0] "
        "placeholder, nodes carrying the artificial attribute (including those "
        "that carry the word the annotator supplied), tags beginning with 'z', "
        "the gap marker 'G' / 'G?', and records with neither form nor tag. "
        "These are the very criteria the diagnosis filter uses, so this number "
        "and that one agree."),

    "overview.excluded.punctuation.on": (
        "Punteggiatura esclusa dall'analisi",
        "Punctuation left out of the analysis"),
    "overview.excluded.punctuation.off": (
        "Punteggiatura presente (il filtro è spento: resta nell'analisi)",
        "Punctuation present (the filter is off: it stays in the analysis)"),
    "overview.excluded.punctuation.tip": (
        "Record la cui etichetta morfologica comincia per «u», che nello "
        "schema AGDT è la posizione della punteggiatura. Non si contano i "
        "segni dentro la parola, ma i record che il treebank tratta come segni "
        "a sé: virgole, punti in alto, punti fermi.",
        "Records whose tag begins with 'u', the punctuation value of the AGDT "
        "scheme. This does not count marks inside a word, but records the "
        "treebank treats as marks in their own right: commas, raised points, "
        "full stops."),

    "overview.excluded.non_greek.on": (
        "Record senza caratteri greci esclusi dall'analisi",
        "Records with no Greek letters left out of the analysis"),
    "overview.excluded.non_greek.off": (
        "Record senza caratteri greci presenti (il filtro è spento: restano nell'analisi)",
        "Records with no Greek letters present (the filter is off: they stay in the analysis)"),
    "overview.excluded.non_greek.tip": (
        "Record nella cui forma non compare nessuna lettera dell'alfabeto "
        "greco: cifre e numerali scritti in cifre, parole latine, sigle, "
        "segni, forme vuote. La punteggiatura rientra quasi sempre anche qui, "
        "ed è la ragione per cui i tre numeri non si sommano.",
        "Records whose form contains no letter of the Greek alphabet: figures "
        "and numerals written as digits, Latin words, sigla, marks, empty "
        "forms. Punctuation almost always falls in here too, which is why the "
        "three numbers do not add up."),

    # ══ Overview: the headline numbers, with the unit of measurement ═════
    #
    # “Mean sentence length: 12.4” cannot be cited: 12.4 of what? The computation is in
    # stats.basic_counts — the sentences are the groups (source_file, document_id,
    # sentence_index) and the tokens counted are those that stats._content lets through,
    # that is all except punctuation (label “u”) and the empty placeholders [0].
    "overview.metric.tokens": ("Record importati (tutti i record del file)",
                               "Imported records (every record in the file)"),
    "overview.metric.words": (
        "Parole (record senza punteggiatura né segnaposto vuoti)",
        "Words (records, punctuation and empty placeholders excluded)"),
    "overview.metric.mean_sentence": (
        "Lunghezza media frase (parole per frase, punteggiatura e segnaposto "
        "vuoti esclusi)",
        "Average sentence length (words per sentence, punctuation and empty "
        "placeholders excluded)"),
    "overview.metric.longest_sentence": (
        "Frase più lunga (parole, punteggiatura e segnaposto vuoti esclusi)",
        "Longest sentence (words, punctuation and empty placeholders excluded)"),

    # ══ Column and row names, stated plainly ═════════════════════════════
    #
    # Morphological profile. Each entry is a ratio between two counts, and the
    # denominator is always computed on the *words*, that is after removing punctuation
    # and empty placeholders.
    "column.genitivi / dativi": ("genitivi ÷ dativi", "genitives ÷ datives"),
    "column.indice di ottativo": ("ottativi ÷ verbi di modo finito",
                                  "optatives ÷ finite verbs"),
    "column.ottativi / congiuntivi": ("ottativi ÷ congiuntivi",
                                      "optatives ÷ subjunctives"),
    "column.participi / verbi finiti": ("participi ÷ verbi di modo finito",
                                        "participles ÷ finite verbs"),
    "column.infiniti / verbi finiti": ("infiniti ÷ verbi di modo finito",
                                       "infinitives ÷ finite verbs"),
    "column.densità dell'articolo (art./sost.)": ("articoli ÷ sostantivi",
                                                  "articles ÷ nouns"),
    "column.aggettivi / sostantivi": ("aggettivi ÷ sostantivi",
                                      "adjectives ÷ nouns"),
    "column.sostantivi / verbi": ("sostantivi ÷ verbi", "nouns ÷ verbs"),
    "column.densità lessicale": (
        "parole piene ÷ tutte le parole (sostantivi, verbi, aggettivi, avverbi)",
        "content words ÷ all words (nouns, verbs, adjectives, adverbs)"),
    "column.particelle per 1.000 token": ("particelle ogni 1.000 parole",
                                          "particles per 1,000 words"),
    "column.duali per 10.000 token": ("duali ogni 10.000 parole",
                                      "duals per 10,000 words"),
    "column.comparativi e superlativi / agg.+avv.": (
        "comparativi e superlativi ÷ aggettivi e avverbi",
        "comparatives and superlatives ÷ adjectives and adverbs"),

    # Richness of the lexicon.
    "column.token (N)": ("parole contate (N)", "words counted (N)"),
    "column.tipi (V)": ("lemmi diversi (V)", "distinct lemmas (V)"),
    "column.TTR (dipende dalla lunghezza)": (
        "TTR: lemmi diversi ÷ parole (cala nei testi lunghi)",
        "TTR: distinct lemmas ÷ words (falls in long texts)"),
    "column.TTR (lemmi)": ("TTR: lemmi diversi ÷ parole",
                           "TTR: distinct lemmas ÷ words"),
    "column.Yule K (concentrazione)": ("Yule K (quanto il lessico si concentra)",
                                       "Yule's K (how concentrated the vocabulary is)"),
    "column.MATTR (finestra 100)": ("MATTR: TTR medio su finestre di 100 parole",
                                    "MATTR: mean TTR over 100-word windows"),
    "column.Maas a² (più basso = più ricco)": (
        "Maas a² (più basso = lessico più ricco)",
        "Maas's a² (lower = richer vocabulary)"),
    "column.Herdan C": ("Herdan C (log dei lemmi ÷ log delle parole)",
                        "Herdan's C (log types ÷ log words)"),
    "column.Guiraud R": ("Guiraud R (lemmi diversi ÷ radice delle parole)",
                         "Guiraud's R (distinct lemmas ÷ square root of words)"),
    "column.Honoré H": ("Honoré H (quanto pesano le parole dette una volta sola)",
                        "Honoré's H (how much the once-only words weigh)"),
    "column.entropia (bit)": ("entropia in bit (quanto è imprevedibile la parola successiva)",
                              "entropy in bits (how unpredictable the next word is)"),
    "column.perplessità": ("perplessità (lemmi «equivalenti» a pari incertezza)",
                           "perplexity (equivalent number of equally likely lemmas)"),

    # Composition and syntax: the two columns that share a name but do not count the
    # same thing (see stats.counts_by_group).
    "column.token per lemma": ("occorrenze per lemma (parole ÷ lemmi diversi)",
                               "occurrences per lemma (words ÷ distinct lemmas)"),
    "column.lunghezza media frase (parole)": (
        "parole per frase (media, senza punteggiatura né segnaposto)",
        "words per sentence (mean, punctuation and placeholders excluded)"),
    "column.lunghezza media frase (token)": (
        "record per frase (media, punteggiatura compresa)",
        "records per sentence (mean, punctuation included)"),
    # This stays the name that ``stats.basic_counts`` writes in its own dictionary:
    # there the count goes through ``_content``, so it is the one without punctuation,
    # and if someone drew it as a column it must say so.
    "column.lunghezza media frase": (
        "parole per frase (media, senza punteggiatura né segnaposto)",
        "words per sentence (mean, punctuation and placeholders excluded)"),
    "column.indice di ipotassi": (
        "verbi finiti subordinati ÷ verbi finiti",
        "subordinate finite verbs ÷ finite verbs"),

    # ══ The extended explanations, those of the pop-up tooltip ═══════════
    #
    # The key carries the name that the analysis writes in the data, not the one that is
    # read: so the label can be rewritten without losing the explanation, and vice
    # versa.
    "stats.explain.genitivi / dativi": (
        "Quanti genitivi ci sono per ogni dativo. Si contano le forme in caso "
        "genitivo e si dividono per quelle in caso dativo. Valore alto = il "
        "testo usa molti genitivi e pochi dativi; il dativo si dirada dopo "
        "l'età classica, quindi questo numero tende a salire con il tempo.",
        "How many genitives there are for each dative: forms in the genitive "
        "divided by forms in the dative. A high value = the text uses many "
        "genitives and few datives; the dative thins out after the classical "
        "age, so this number tends to rise over time."),
    "stats.explain.indice di ottativo": (
        "Quanto è presente l'ottativo. Si contano i verbi all'ottativo e si "
        "dividono per tutti i verbi di modo finito (indicativo, congiuntivo, "
        "ottativo, imperativo). Valore alto = l'ottativo è vivo: prosa "
        "classica o atticismo. Valore vicino a zero = koiné.",
        "How present the optative is: verbs in the optative divided by all "
        "finite verbs (indicative, subjunctive, optative, imperative). A high "
        "value = the optative is alive: classical prose or Atticism. A value "
        "near zero = koine."),
    "stats.explain.ottativi / congiuntivi": (
        "Quanti ottativi per ogni congiuntivo. Si contano i verbi "
        "all'ottativo e si dividono per quelli al congiuntivo. Valore alto = "
        "dove ci si aspetterebbe un congiuntivo il testo mette un ottativo.",
        "How many optatives for each subjunctive: verbs in the optative "
        "divided by verbs in the subjunctive. A high value = where one would "
        "expect a subjunctive the text puts an optative."),
    "stats.explain.participi / verbi finiti": (
        "Quanti participi per ogni verbo di modo finito. Si contano i "
        "participi e si dividono per i verbi di modo finito. Valore alto = "
        "stile che appoggia il racconto sui participi invece che su una "
        "sequenza di proposizioni: è il tratto più riconoscibile della prosa "
        "greca elaborata.",
        "How many participles for each finite verb: participles divided by finite verbs. A high value = a style that hangs the narrative on participles rather than on a chain of clauses: the most recognisable feature of elaborate Greek prose."),
    "stats.explain.infiniti / verbi finiti": (
        "Quanti infiniti per ogni verbo di modo finito. Si contano gli "
        "infiniti e si dividono per i verbi di modo finito. Valore alto = "
        "molte completive all'infinito e molto discorso indiretto.",
        "How many infinitives for each finite verb: infinitives divided by "
        "finite verbs. A high value = many infinitive complements and much "
        "indirect speech."),
    "stats.explain.densità dell'articolo (art./sost.)": (
        "Quanti articoli per ogni sostantivo. Si contano le forme etichettate "
        "come articolo e si dividono per i sostantivi. Valore alto = quasi "
        "ogni sostantivo ha il suo articolo, come nella prosa attica. Valore "
        "basso = l'articolo manca spesso, come in Omero.",
        "How many articles for each noun: forms tagged as article divided by "
        "nouns. A high value = nearly every noun carries its article, as in "
        "Attic prose. A low value = the article is often absent, as in Homer."),
    "stats.explain.aggettivi / sostantivi": (
        "Quanti aggettivi per ogni sostantivo. Valore alto = testo "
        "descrittivo, ricco di qualificazioni; valore basso = testo che nomina "
        "le cose senza qualificarle.",
        "How many adjectives for each noun. A high value = a descriptive text, "
        "rich in qualification; a low value = a text that names things without "
        "qualifying them."),
    "stats.explain.sostantivi / verbi": (
        "Quanti sostantivi per ogni verbo. Valore alto = stile nominale, che "
        "dice le cose con i nomi (ἡ τῆς πόλεως σωτηρία); valore basso = stile "
        "verbale, che le dice con i verbi.",
        "How many nouns for each verb. A high value = a nominal style, saying "
        "things with nouns (ἡ τῆς πόλεως σωτηρία); a low value = a verbal "
        "style, saying them with verbs."),
    "stats.explain.densità lessicale": (
        "Quanta parte del testo porta un contenuto proprio. Si contano sostantivi, verbi, aggettivi e avverbi, le «parole piene», e si dividono per tutte le parole (punteggiatura e segnaposto già tolti). Il resto sono articoli, preposizioni, congiunzioni, particelle, pronomi. Valore alto (verso 1) = testo fitto di contenuto, da iscrizione o da catalogo; valore basso = testo pieno di connettivi, cioè un periodare articolato.",
        "How much of the text carries content of its own: nouns, verbs, adjectives and adverbs, the 'content words', divided by all words (punctuation and placeholders already removed). The remainder are articles, prepositions, conjunctions, particles, pronouns. A high value (towards 1) = a text dense with content, like an inscription or a catalogue; a low value = a text full of connectives, that is, an articulated period."),
    "stats.explain.particelle per 1.000 token": (
        "Quante particelle si incontrano ogni mille parole. Si contano le "
        "occorrenze delle particelle (μέν, δέ, γάρ, οὖν, τοίνυν…, riconosciute "
        "dal lemma), si dividono per il totale delle parole e si moltiplica "
        "per mille. Valore alto = prosa che lega continuamente una frase "
        "all'altra; le particelle sono rare nei testi tecnici e nelle "
        "iscrizioni.",
        "How many particles you meet every thousand words: occurrences of the "
        "particles (μέν, δέ, γάρ, οὖν, τοίνυν…, recognised by lemma) divided "
        "by the total number of words, times a thousand. A high value = prose "
        "that constantly ties one sentence to the next; particles are rare in "
        "technical texts and in inscriptions."),
    "stats.explain.duali per 10.000 token": (
        "Quante forme di numero duale si incontrano ogni diecimila parole. Il duale è raro dappertutto: di qui il moltiplicatore alto, che serve solo a non leggere una fila di zeri. Valore alto = attico antico, poesia arcaica, coppie (occhi, mani, i due Aiaci).",
        "How many dual forms you meet every ten thousand words. The dual is rare everywhere: hence the large multiplier, which exists only to avoid reading a row of zeros. A high value = older Attic, archaic poetry, pairs (eyes, hands, the two Ajaxes)."),
    "stats.explain.comparativi e superlativi / agg.+avv.": (
        "Quanta parte delle qualificazioni è di grado comparativo o "
        "superlativo. Si contano le forme di grado comparativo e superlativo e "
        "si dividono per il totale di aggettivi e avverbi. Valore alto = testo "
        "che confronta e gradua di continuo (encomio, oratoria epidittica).",
        "How much of the qualification is comparative or superlative: forms in "
        "the comparative and superlative degree divided by all adjectives and "
        "adverbs. A high value = a text that constantly compares and grades "
        "(encomium, epideictic oratory)."),

    "stats.explain.token (N)": (
        "Quante parole sono state contate per calcolare le misure di questa "
        "sezione: le occorrenze di lemma, punteggiatura e segnaposto esclusi. "
        "È il numero da guardare per sapere se le misure qui sotto sono "
        "sostenute da abbastanza testo.",
        "How many words were counted for the measures in this section: lemma "
        "occurrences, punctuation and placeholders excluded. This is the "
        "number to look at to know whether the measures below rest on enough "
        "text."),
    "stats.explain.tipi (V)": (
        "Quanti lemmi diversi compaiono. Se λέγω ricorre trecento volte, qui "
        "conta una volta sola. Valore alto rispetto alle parole = vocabolario "
        "ampio.",
        "How many distinct lemmas appear. If λέγω occurs three hundred times, "
        "it counts once here. A high value relative to the words = a wide "
        "vocabulary."),
    "stats.explain.TTR (dipende dalla lunghezza)": (
        "TTR sta per type/token ratio, «rapporto tipi su occorrenze». Si "
        "contano i lemmi diversi e si dividono per il numero di parole. Se su "
        "1.000 parole compaiono 400 lemmi diversi, il TTR è 0,40. Valore alto "
        "= lessico vario, poche ripetizioni. Attenzione: più lungo è il testo "
        "più il TTR scende, perché le parole comuni tornano; per confrontare "
        "testi di taglia diversa si guardano MATTR, Yule K o Maas a².",
        "TTR stands for type/token ratio. Distinct lemmas divided by the "
        "number of words: if 400 distinct lemmas appear in 1,000 words, the "
        "TTR is 0.40. A high value = varied vocabulary, few repetitions. "
        "Careful: the longer the text the lower the TTR, because common words "
        "keep coming back; to compare texts of different size use MATTR, "
        "Yule's K or Maas's a²."),
    "stats.explain.Yule K (concentrazione)": (
        "Quanto il testo si appoggia sempre alle stesse parole. Si guarda "
        "quante volte ciascun lemma ricorre e si misura quanto le occorrenze "
        "si ammassano su pochi lemmi. Valore alto = poche parole fanno gran "
        "parte del testo; valore basso = le occorrenze sono distribuite. A "
        "differenza del TTR non cambia con la lunghezza del testo, quindi si "
        "può usare per confrontare un frammento con un'opera intera.",
        "How far the text keeps leaning on the same words. It looks at how "
        "often each lemma recurs and measures how far the occurrences pile up "
        "on a few lemmas. A high value = a few words make up much of the text; "
        "a low value = the occurrences are spread out. Unlike TTR it does not "
        "change with the length of the text, so it can compare a fragment with "
        "a whole work."),
    "stats.explain.MATTR (finestra 100)": (
        "Il TTR, ma calcolato a pezzi. Si scorre il testo cento parole alla "
        "volta, si calcola il TTR di ogni finestra e si fa la media. Poiché "
        "ogni finestra è lunga uguale, il risultato non dipende più dalla "
        "lunghezza del testo: è il modo onesto di confrontare Saffo con "
        "Polibio. Valore alto = lessico vario.",
        "TTR, but computed piece by piece: the text is scanned a hundred words "
        "at a time, the TTR of each window is computed and the average taken. "
        "Since every window has the same length, the result no longer depends "
        "on the length of the text: it is the honest way to compare Sappho "
        "with Polybius. A high value = varied vocabulary."),
    "stats.explain.Maas a² (più basso = più ricco)": (
        "Un'altra correzione del TTR che non risente della lunghezza. Qui la "
        "direzione è rovesciata e conviene ricordarlo: più il valore è "
        "basso, più il lessico è ricco.",
        "Another length-independent correction of TTR. Here the direction is "
        "reversed and it is worth remembering: the lower the value, the richer "
        "the vocabulary."),
    "stats.explain.Herdan C": (
        "Come il TTR, ma calcolato sui logaritmi (il logaritmo dei lemmi "
        "diversi diviso il logaritmo delle parole), il che ne smorza molto la "
        "dipendenza dalla lunghezza. Valore alto = lessico vario.",
        "Like TTR, but computed on logarithms (log of distinct lemmas divided "
        "by log of words), which greatly damps its dependence on length. A "
        "high value = varied vocabulary."),
    "stats.explain.Guiraud R": (
        "I lemmi diversi divisi per la radice quadrata del numero di parole. "
        "La radice serve a compensare il fatto che il vocabolario cresce più "
        "lentamente del testo. Valore alto = lessico vario.",
        "Distinct lemmas divided by the square root of the number of words. "
        "The square root compensates for the fact that vocabulary grows more "
        "slowly than text. A high value = varied vocabulary."),
    "stats.explain.Honoré H": (
        "Quanto pesano le parole dette una volta sola (gli hapax) rispetto a "
        "tutto il vocabolario. Valore alto = il testo continua a introdurre "
        "parole nuove invece di riusare le proprie.",
        "How much the words said only once (the hapax) weigh against the whole "
        "vocabulary. A high value = the text keeps introducing new words "
        "instead of reusing its own."),
    "stats.explain.entropia (bit)": (
        "Quanto è difficile indovinare la parola successiva conoscendo solo la "
        "frequenza dei lemmi. Si misura in bit: 0 vorrebbe dire un testo fatto "
        "di una parola sola, ripetuta. Valore alto = lessico vario e ben "
        "distribuito.",
        "How hard it is to guess the next word knowing only how frequent each "
        "lemma is. Measured in bits: 0 would mean a text made of a single word "
        "repeated. A high value = a varied, evenly spread vocabulary."),
    "stats.explain.perplessità": (
        "L'entropia detta in parole: su quante parole diverse, tutte ugualmente "
        "probabili, si dovrebbe tirare a indovinare per avere la stessa "
        "incertezza. Perplessità 500 = è come scegliere fra cinquecento parole "
        "a caso. Valore alto = lessico vario.",
        "Entropy said in words: how many equally likely words one would have to "
        "guess among to face the same uncertainty. A perplexity of 500 = it is "
        "like choosing among five hundred words at random. A high value = "
        "varied vocabulary."),

    "stats.explain.indice di ipotassi": (
        "Quanta parte delle proposizioni è subordinata. Si contano i verbi di "
        "modo finito che dipendono da una congiunzione subordinante e si "
        "dividono per tutti i verbi di modo finito. Valore alto = stile "
        "periodico, a incastro; valore basso = stile paratattico, che accosta "
        "le proposizioni una dopo l'altra.",
        "How much of the clause structure is subordinate: finite verbs hanging "
        "from a subordinating conjunction divided by all finite verbs. A high "
        "value = a periodic, interlocking style; a low value = a paratactic "
        "style that sets clauses side by side."),

    # The title of the key-numbers card: the rows say what they are about.
    "stats.key_numbers": ("Numeri chiave (passa il mouse su una riga per la spiegazione)",
                          "Key numbers (hover a row for the explanation)"),
    "stats.richness": ("Ricchezza del lessico (passa il mouse su una riga per la spiegazione)",
                       "Vocabulary richness (hover a row for the explanation)"),
}
