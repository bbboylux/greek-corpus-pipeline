# -*- coding: utf-8 -*-
"""The entries of the page on the AGDT 2.0 scheme, in Italian and in English.

It is kept apart from ``i18n.py`` for the reason given at the end of that file:
the large pages keep their own entries in separate modules, so that the general
dictionary stays of a manageable size. ``i18n.py`` imports this module by itself
and pours its content into the general dictionary; each key is written in one
place only.

What is in here:

``step.rules``    the name of the step in the left-hand bar, which speaks of the
                  scheme and not of rules;
``rules.*``       the title and the introduction of the page;
``schema.*``      the extended explanations — one for each of the nine positions
                  of the morphological label, one for each syntactic function,
                  plus the suffixes and the infix;
``column.*``      the names of the additional columns, translated at the moment
                  they are drawn (:func:`gui_qt.i18n.data_label`).

The explanations are written for whoever reads Greek and has never programmed:
no “string”, no “slot”, no “token”. The text says what a position records and
what a label marks, with the Greek example beside it.

The *inventory* is not here: the admitted values, their short meanings and the
list of relations are read from ``greek_corpus_pipeline.agdt_schema`` when the
page is drawn. Here there is only the prose that accompanies them, and a
relation that was added to the scheme would appear all the same, with its short
gloss in place of the extended explanation.
"""
from __future__ import annotations

STRINGS: dict[str, tuple[str, str]] = {

    # ══ The step in the left-hand bar ════════════════════════════════
    "step.rules": ("Lo schema AGDT 2.0", "The AGDT 2.0 scheme"),
    "step.rules.hint": ("L'etichetta e le funzioni, spiegate",
                        "The tag and the functions, explained"),

    # ══ Title and introduction of the page ═══════════════════════════
    "rules.title": ("Lo schema di annotazione AGDT 2.0",
                    "The AGDT 2.0 annotation scheme"),
    "rules.intro": (
        "Questo è lo schema con cui i treebank di greco antico sono annotati, ed "
        "è lo schema rispetto al quale il programma fa tutte le sue verifiche. "
        "Consta di due cose sole: un'etichetta morfologica di nove caratteri "
        "attaccata a ogni parola, e un inventario chiuso di funzioni sintattiche "
        "che dice, per ogni parola, che cosa fa per la parola da cui dipende. "
        "Le due schede qui sotto le spiegano una per una, dal principio.",
        "This is the scheme the Ancient Greek treebanks are annotated with, and "
        "it is the scheme against which the program does all of its checking. It "
        "consists of two things only: a nine-character morphological tag attached "
        "to every word, and a closed inventory of syntactic functions saying, for "
        "each word, what it does for the word it depends on. The two tabs below "
        "explain them one at a time, from the beginning."),

    # ══ The two tabs ═════════════════════════════════════════════════
    "schema.tab.tag": ("L'etichetta morfologica", "The morphological tag"),
    "schema.tab.relations": ("Le funzioni sintattiche", "The syntactic functions"),

    # ══ Card 1 — the morphological label ════════════════════════════════
    "schema.tag.intro": (
        "Nei file AGDT ogni parola porta un attributo <span "
        "style='font-family:monospace'>postag</span> lungo <b>esattamente nove "
        "caratteri</b>. Non è un'abbreviazione: è una griglia. Ogni posizione ha "
        "un significato fisso e non cambia mai di posto, così che il quarto "
        "carattere sia il tempo tanto in un verbo quanto in un sostantivo, dove però il tempo non ha senso e quella casella porta un trattino."
        "<br><br>"
        "Il vantaggio è che l'etichetta si legge senza conoscerne il contenuto: "
        "si conta fino alla posizione che interessa e si guarda che lettera c'è. "
        "Il prezzo è che una lettera fuori posto è invisibile all'occhio e "
        "cambia l'analisi — ed è per questo che il programma le conta.",
        "In AGDT files every word carries a <span "
        "style='font-family:monospace'>postag</span> attribute that is "
        "<b>exactly nine characters</b> long. It is not an abbreviation: it is a "
        "grid. Every position has a fixed meaning and never moves, so that the "
        "fourth character is the tense in a verb just as it is in a noun, where tense makes no sense and the slot therefore holds a hyphen."
        "<br><br>"
        "The gain is that the tag can be read without knowing what is in it: you "
        "count to the position you care about and look at the letter. The price "
        "is that a letter in the wrong place is invisible to the eye and changes "
        "the analysis — which is why the program counts them."),

    "schema.positions.card": ("Le nove posizioni, una per una",
                              "The nine positions, one by one"),
    "schema.positions.hint": (
        "Le ultime due colonne dicono chi ha diritto a riempire la casella. "
        "Un sostantivo <i>deve</i> avere numero, genere e caso e non può avere "
        "tempo; un verbo di modo finito deve avere persona, numero, tempo, modo "
        "e diatesi e non può avere caso. È da qui che nasce il disegno "
        "caratteristico delle etichette: i verbi hanno i trattini in fondo, i "
        "nomi ce li hanno nel mezzo.",
        "The last two columns say who is entitled to fill the slot. A noun "
        "<i>must</i> have number, gender and case and cannot have a tense; a "
        "finite verb must have person, number, tense, mood and voice and cannot "
        "have a case. This is where the characteristic shape of the tags comes "
        "from: verbs carry their hyphens at the end, nouns carry them in the "
        "middle."),

    "schema.values.card": ("Che cosa vuol dire ogni lettera",
                           "What every letter means"),
    "schema.values.hint": (
        "L'elenco completo, posizione per posizione. È chiuso: una lettera che "
        "non compare in questa tabella non è prevista dallo schema, e il "
        "programma la segnala per quello che è, un valore fuori inventario.",
        "The complete list, position by position. It is closed: a letter that "
        "does not appear in this table is not provided for by the scheme, and "
        "the program reports it for what it is, a value outside the inventory."),

    "schema.dash.card": ("Il trattino", "The hyphen"),
    "schema.dash.text": (
        "Il trattino <span style='font-family:monospace'>-</span> non è un "
        "valore mancante né un errore: è la dichiarazione che <i>quella "
        "categoria non si applica a questa parola</i>. Un sostantivo non ha "
        "diatesi, e la sua sesta casella porta un trattino; una congiunzione non "
        "ha nulla da dichiarare oltre alla parte del discorso, e la sua "
        "etichetta è <span style='font-family:monospace'>c--------</span>, una "
        "lettera e otto trattini."
        "<br><br>"
        "Un'eccezione sola, e va tenuta a mente: nella <b>nona</b> posizione, "
        "quella del grado, il trattino vale «grado positivo». "
        "<span style='font-family:monospace'>a-s---mn-</span> non è un aggettivo "
        "di cui non si sa il grado: è σοφός, un aggettivo di grado positivo. Il "
        "comparativo σοφώτερος scrive <span style='font-family:monospace'>c</span> "
        "e il superlativo σοφώτατος scrive <span style='font-family:monospace'>s</span>."
        "<br><br>"
        "Da qui la differenza fra due cose che si somigliano: una casella con il "
        "trattino <i>giusto</i> è un'informazione, una casella con il trattino "
        "dove ci vorrebbe un valore è un'etichetta incompleta.",
        "The hyphen <span style='font-family:monospace'>-</span> is neither a "
        "missing value nor a mistake: it is the statement that <i>this category "
        "does not apply to this word</i>. A noun has no voice, and its sixth "
        "slot holds a hyphen; a conjunction has nothing to declare beyond its "
        "part of speech, and its tag is <span "
        "style='font-family:monospace'>c--------</span>, one letter and eight "
        "hyphens."
        "<br><br>"
        "One exception, and it is worth remembering: in the <b>ninth</b> "
        "position, that of degree, the hyphen means “positive degree”. "
        "<span style='font-family:monospace'>a-s---mn-</span> is not an "
        "adjective whose degree is unknown: it is σοφός, an adjective in the "
        "positive. The comparative σοφώτερος writes <span "
        "style='font-family:monospace'>c</span> and the superlative σοφώτατος "
        "writes <span style='font-family:monospace'>s</span>."
        "<br><br>"
        "Hence the difference between two things that look alike: a slot with "
        "the <i>right</i> hyphen is information, a slot with a hyphen where a "
        "value belongs is an incomplete tag."),

    "schema.examples.card": ("Come si legge un'etichetta, carattere per carattere",
                             "Reading a tag, one character at a time"),
    "schema.examples.hint": (
        "Cinque etichette vere, sciolte una posizione alla volta. Le righe in "
        "grigio sono le caselle che portano un trattino.",
        "Five real tags, unpacked one position at a time. The grey rows are the "
        "slots holding a hyphen."),

    # What each position records. The keys are the index of the position counted from
    # zero, as it is counted in the scheme.
    "schema.pos.0": (
        "Che tipo di parola è. È l'unica posizione che non è mai vuota, e "
        "comanda su tutte le altre: è la parte del discorso a decidere quali "
        "delle otto caselle seguenti hanno diritto a un valore e quali devono "
        "restare col trattino.",
        "What kind of word it is. It is the only position that is never empty, "
        "and it commands all the others: the part of speech decides which of the "
        "eight following slots may carry a value and which must stay on a hyphen."),
    "schema.pos.1": (
        "Chi compie l'azione, rispetto a chi parla: io/noi, tu/voi, egli/essi. "
        "La riempiono le voci verbali di modo finito e i pronomi personali; il "
        "participio e l'infinito, che persona non hanno, portano il trattino.",
        "Who performs the action, relative to the speaker: I/we, you, he/they. "
        "Finite verb forms and personal pronouns fill it; the participle and the "
        "infinitive, which have no person, carry a hyphen."),
    "schema.pos.2": (
        "Quanti: uno, più d'uno, o esattamente due. Il duale è una casella a sé "
        "perché il greco lo distingue davvero, ed è raro abbastanza da rendere "
        "sospetta ogni sua occorrenza inattesa.",
        "How many: one, more than one, or exactly two. The dual has a slot of "
        "its own because Greek really does distinguish it, and it is rare enough "
        "that every unexpected occurrence of it is worth a second look."),
    "schema.pos.3": (
        "Il tema temporale del verbo: presente, imperfetto, futuro, aoristo, "
        "perfetto, piuccheperfetto, futuro anteriore. Vale per tutte le voci "
        "verbali, participi e infiniti compresi, perché anche loro hanno un tema.",
        "The verb's tense stem: present, imperfect, future, aorist, perfect, "
        "pluperfect, future perfect. It holds for every verbal form, participles "
        "and infinitives included, because they too have a stem."),
    "schema.pos.4": (
        "Che cosa fa la forma verbale: afferma (indicativo), sta in una "
        "subordinata o esprime eventualità (congiuntivo), esprime augurio o "
        "possibilità (ottativo), comanda (imperativo). Nella stessa casella lo "
        "schema mette anche le due forme che finite non sono, l'infinito e il "
        "participio: non sono modi in senso grammaticale, ma stanno qui perché "
        "è qui che si distinguono dalle altre.",
        "What the verbal form does: it asserts (indicative), stands in a "
        "subordinate clause or expresses eventuality (subjunctive), expresses a "
        "wish or a possibility (optative), commands (imperative). The scheme puts "
        "the two non-finite forms in the same slot, the infinitive and the "
        "participle: they are not moods in the grammatical sense, but this is "
        "where they are told apart from the rest."),
    "schema.pos.5": (
        "Attivo, medio o passivo. La casella «medio-passivo» esiste perché in "
        "greco moltissime forme sono le stesse per il medio e per il passivo, e "
        "dichiararle come tali è più onesto che scegliere a caso.",
        "Active, middle or passive. The “medio-passive” value exists because a "
        "great many Greek forms are identical for the middle and the passive, "
        "and declaring them as such is more honest than picking one at random."),
    "schema.pos.6": (
        "Maschile, femminile, neutro. C'è anche il genere «comune», per le "
        "parole che hanno la stessa forma al maschile e al femminile (ὁ/ἡ θεός): "
        "non sta nelle linee guida pubblicate, ma i treebank annotati a mano lo "
        "usano regolarmente, e lo schema del programma lo dichiara invece di "
        "fingere che non esista.",
        "Masculine, feminine, neuter. There is also the “common” gender, for "
        "words with the same form in the masculine and the feminine (ὁ/ἡ θεός): "
        "it is not in the published guidelines, but the hand-annotated treebanks "
        "use it regularly, and the program's scheme declares it instead of "
        "pretending it does not exist."),
    "schema.pos.7": (
        "Il caso della parola declinata: nominativo, genitivo, dativo, "
        "accusativo, vocativo. Il locativo è previsto per i relitti (οἴκοι, "
        "Ἀθήνησι) e in un corpus di prosa attica non dovrebbe quasi comparire.",
        "The case of the declined word: nominative, genitive, dative, "
        "accusative, vocative. The locative is provided for the surviving relics "
        "(οἴκοι, Ἀθήνησι) and should hardly ever turn up in a corpus of Attic "
        "prose."),
    "schema.pos.8": (
        "Comparativo e superlativo, per gli aggettivi, gli avverbi che si "
        "confrontano (θᾶσσον, τάχιστα) e i participi usati come aggettivi. Qui "
        "il trattino non vuol dire «non si applica» ma «grado positivo»: è "
        "l'unica posizione in cui il trattino porta un'informazione.",
        "Comparative and superlative, for adjectives, for adverbs that compare "
        "(θᾶσσον, τάχιστα) and for participles used adjectivally. Here the hyphen "
        "does not mean “not applicable” but “positive degree”: it is the one "
        "position in which the hyphen carries information."),

    "schema.always": ("sempre", "always"),
    "schema.never": ("mai", "never"),
    "schema.verb_prefix": ("verbo", "verb"),

    # ══ Tab 2 — the syntactic functions ══════════════════════════════
    "schema.rel.intro": (
        "Nell'annotazione AGDT una frase non è una fila di parole ma un albero: ogni parola pende da un'altra parola, la sua <b>testa</b>, e l'arco che le unisce porta scritto <b>che cosa la parola fa per la sua testa</b>. Quella scritta è la funzione sintattica, e l'inventario delle funzioni possibili è chiuso: sono queste e non altre.<br><br>Due cose sorprendono chi viene dalla grammatica scolastica. La prima è che le parole di servizio (preposizioni, congiunzioni subordinanti, coordinanti) <i>reggono</i> invece di essere rette: in ἄνευ ὅρκου è ἄνευ la testa, e ὅρκου pende da lei portando la funzione dell'intero sintagma. La seconda è che la punteggiatura è parte dell'albero, con etichette sue. Sono scelte della scuola di Praga, da cui AGDT deriva.",
        "In AGDT annotation a sentence is not a row of words but a tree: every word hangs from another word, its <b>head</b>, and the arc joining them says <b>what the word does for its head</b>. That is the syntactic function, and the inventory of possible functions is closed: these and no others.<br><br>Two things surprise anyone coming from school grammar. The first is that function words (prepositions, subordinating conjunctions, coordinators) <i>govern</i> rather than being governed: in ἄνευ ὅρκου it is ἄνευ that is the head, and ὅρκου hangs from it carrying the function of the whole phrase. The second is that punctuation is part of the tree, with labels of its own. Both are choices of the Prague school, from which AGDT descends."),

    "schema.rel.card": ("L'inventario delle funzioni", "The inventory of functions"),

    "schema.group.core": ("Il nucleo della frase", "The core of the sentence"),
    "schema.group.modifier": ("Quello che si aggiunge al nucleo",
                              "What is added to the core"),
    "schema.group.structure": ("Coordinazione, apposizione, ellissi",
                               "Coordination, apposition, ellipsis"),
    "schema.group.aux": ("Le parole di servizio", "Function words"),
    "schema.group.punct": ("La punteggiatura", "Punctuation"),
    "schema.group.absent": ("Quando l'analisi manca", "When the analysis is missing"),
    "schema.group.other": ("Altre", "Other"),

    # What each function marks. The keys are the labels of the scheme: a relation
    # added there and not explained here appears all the same, with its own short
    # gloss in place of the explanation.
    "schema.rel.PRED": (
        "Il verbo reggente della frase, quello da cui pende tutto il resto. "
        "Non dipende da nessuna parola: è attaccato alla radice dell'albero. "
        "Una frase ne ha di norma uno; ne ha più d'uno quando i predicati sono "
        "coordinati, e in quel caso portano il suffisso _CO.",
        "The governing verb of the sentence, the one everything else hangs from. "
        "It depends on no word: it is attached to the root of the tree. A "
        "sentence normally has one; it has more than one when the predicates are "
        "coordinated, and then they carry the _CO suffix."),
    "schema.rel.SBJ": (
        "Il soggetto del verbo da cui dipende. In greco il soggetto sta spesso "
        "nella sola desinenza: se nessuna parola lo esprime, l'etichetta "
        "semplicemente non compare nella frase, e non è un errore.",
        "The subject of the verb it depends on. In Greek the subject is often in "
        "the ending alone: if no word expresses it, the label simply does not "
        "occur in the sentence, and that is not an error."),
    "schema.rel.OBJ": (
        "L'oggetto, o più in generale il complemento che il verbo «richiede»: "
        "l'accusativo, ma anche il genitivo e il dativo quando è il verbo a "
        "chiederli (ἐπιθυμῶ + genitivo, πείθομαι + dativo). Il confine con "
        "l'avverbiale non è netto, e le linee guida stesse lo lasciano al "
        "giudizio dell'annotatore.",
        "The object, or more generally the complement the verb “requires”: "
        "the accusative, but also the genitive and the dative when the verb calls "
        "for them (ἐπιθυμῶ + genitive, πείθομαι + dative). The line between this "
        "and the adverbial is not sharp, and the guidelines themselves leave it "
        "to the annotator's judgement."),
    "schema.rel.ATR": (
        "L'attributo: qualunque parola qualifichi un nome: l'aggettivo, il genitivo di appartenenza, l'articolo, il participio attributivo, la proposizione relativa. Il segno che si tratta di un attributo e non di altro è che dipende dal nome, non dal verbo.",
        "The attribute: any word qualifying a noun: an adjective, a possessive genitive, the article, an attributive participle, a relative clause. The sign that it is an attribute and not something else is that it depends on the noun, not on the verb."),
    "schema.rel.ADV": (
        "L'avverbiale: tempo, luogo, modo, causa, mezzo, fine, condizione. Dice le circostanze dell'azione e dipende dal verbo: o da un aggettivo, o da un altro avverbio. Ci finiscono anche i sintagmi preposizionali circostanziali e le subordinate avverbiali intere.",
        "The adverbial: time, place, manner, cause, means, purpose, condition. It states the circumstances of the action and depends on the verb: or on an adjective, or on another adverb. Circumstantial prepositional phrases and whole adverbial clauses end up here too."),
    "schema.rel.PNOM": (
        "Il nome del predicato: quello che sta dopo εἰμί, γίγνομαι, φαίνομαι e simili: σοφός in Σωκράτης σοφός ἐστιν. Dipende dalla copula, non dal soggetto con cui concorda.",
        "The predicate nominal: what stands after εἰμί, γίγνομαι, φαίνομαι and the like: σοφός in Σωκράτης σοφός ἐστιν. It depends on the copula, not on the subject it agrees with."),
    "schema.rel.OCOMP": (
        "Il predicativo dell'oggetto: in «lo elessero stratego» è στρατηγόν, la "
        "parola che dice che cosa l'oggetto diventa o come viene giudicato. "
        "Dipende dal verbo, non dall'oggetto.",
        "The object complement: in “they elected him general” it is στρατηγόν, "
        "the word saying what the object becomes or how it is judged. It depends "
        "on the verb, not on the object."),
    "schema.rel.ATV": (
        "Il participio predicativo, o l'aggettivo in funzione di participio, che concorda con il soggetto o con l'oggetto e ne descrive lo stato mentre l'azione avviene: ἦλθε γελῶν, «arrivò ridendo». Con questa etichetta si attacca alla parola con cui concorda.",
        "The predicative participle, or an adjective doing a participle's work, agreeing with the subject or the object and describing its state while the action takes place: ἦλθε γελῶν, “he arrived laughing”. Under this label it attaches to the word it agrees with."),
    "schema.rel.AtvV": (
        "La stessa funzione di ATV, ma appesa al verbo anziché al nome "
        "con cui il participio concorda. Lo schema tiene distinte le due "
        "possibilità, e i treebank annotati a mano usano ora l'una ora l'altra.",
        "The same function as ATV, but hanging from the verb instead of "
        "from the noun the participle agrees with. The scheme keeps the two "
        "apart, and the hand-annotated treebanks use now one, now the other."),
    "schema.rel.COORD": (
        "Il coordinante: καί, δέ, ἀλλά, τε, ἤ, e anche la virgola quando unisce. "
        "In AGDT il coordinante non è una parolina appesa al primo membro: è lui "
        "il nodo, e i membri coordinati pendono da lui, ciascuno con la propria "
        "funzione seguita dal suffisso _CO.",
        "The coordinator: καί, δέ, ἀλλά, τε, ἤ, and the comma too when it joins. "
        "In AGDT the coordinator is not a small word hanging off the first "
        "conjunct: it is the node, and the conjuncts hang from it, each with its "
        "own function followed by the _CO suffix."),
    "schema.rel.APOS": (
        "Il nodo dell'apposizione, costruito come quello della coordinazione: il nodo è il segno che introduce l'apposizione, di norma la virgola o i due punti, e i membri che vi pendono portano la propria funzione seguita dal suffisso _AP.",
        "The apposition node, built like the coordination node: the node is the mark introducing the apposition, usually a comma or a colon, and the members hanging from it carry their own function followed by the _AP suffix."),
    "schema.rel.ExD": (
        "«Dipende da una testa che non c'è»: la parola da cui questa dovrebbe "
        "pendere è stata omessa dall'autore. Serve per le risposte ellittiche, "
        "le frasi nominali, i frammenti, i titoli. L'etichetta dice soltanto che "
        "il posto sopra è vuoto; quando si sa anche che funzione avesse la "
        "parola mancante, lo si scrive con l'infisso _ExD spiegato più sotto.",
        "“Depends on a head that is not there”: the word this one should hang "
        "from was left out by the author. It is used for elliptical answers, "
        "verbless sentences, fragments, titles. The label says only that the "
        "place above is empty; when the function of the missing word is known "
        "too, it is written with the _ExD infix explained below."),
    "schema.rel.MWE": (
        "Espressione polirematica: più parole che valgono come una sola e che "
        "non si possono analizzare pezzo per pezzo (καὶ γάρ, ὥστε scritto "
        "staccato, οὐ μήν). La prima parola regge, le altre le pendono da sotto "
        "con questa etichetta.",
        "Multi-word expression: several words that count as one and cannot be "
        "analysed piece by piece (καὶ γάρ, ὥστε written apart, οὐ μήν). The "
        "first word is the head, the others hang beneath it under this label."),
    "schema.rel.AuxP": (
        "La preposizione. In AGDT la preposizione è la testa del sintagma: "
        "l'etichetta AuxP dice soltanto «qui c'è una preposizione», mentre la "
        "funzione dell'intero sintagma sta scritta sul nome che le pende sotto. "
        "In καὶ ἄνευ ὅρκου la catena è καί (COORD) → ἄνευ (AuxP) → ὅρκου (ADV_CO).",
        "The preposition. In AGDT the preposition is the head of the phrase: the "
        "AuxP label says only “there is a preposition here”, while the function "
        "of the whole phrase is written on the noun hanging below it. In καὶ ἄνευ "
        "ὅρκου the chain runs καί (COORD) → ἄνευ (AuxP) → ὅρκου (ADV_CO)."),
    "schema.rel.AuxC": (
        "La congiunzione subordinante: ὅτι, ἵνα, ὡς, εἰ, ἐπεί. Come la "
        "preposizione, è una testa: il verbo della subordinata pende da lei, e "
        "la funzione della subordinata nella frase reggente sta scritta su quel "
        "verbo.",
        "The subordinating conjunction: ὅτι, ἵνα, ὡς, εἰ, ἐπεί. Like the "
        "preposition, it is a head: the verb of the subordinate clause hangs from "
        "it, and the function of the clause within the main sentence is written "
        "on that verb."),
    "schema.rel.AuxV": (
        "Il verbo ausiliare: εἰμί quando accompagna un participio o un aggettivo "
        "verbale a formare una perifrasi (λελυκὼς ἐστί).",
        "The auxiliary verb: εἰμί when it accompanies a participle or a verbal "
        "adjective to form a periphrasis (λελυκὼς ἐστί)."),
    "schema.rel.AuxR": (
        "Il riflessivo passivo: il pronome riflessivo quando il verbo non lo "
        "regge come oggetto ma se ne serve per formare un passivo. È un'etichetta "
        "ereditata dallo schema di Praga e in greco è rarissima.",
        "The reflexive passive: the reflexive pronoun when the verb does not "
        "govern it as an object but uses it to form a passive. It is a label "
        "inherited from the Prague scheme and is very rare in Greek."),
    "schema.rel.AuxY": (
        "Avverbio o particella che vale per la frase intera e non per una parola "
        "sola: ἄρα, δή, οὖν, e μέν e δέ quando non stanno coordinando niente. "
        "Pende dal nodo della frase su cui commenta.",
        "An adverb or particle that bears on the whole sentence rather than on a "
        "single word: ἄρα, δή, οὖν, and μέν and δέ when they are not coordinating "
        "anything. It hangs from the node of the clause it comments on."),
    "schema.rel.AuxZ": (
        "Particella enfatica che si attacca a una parola sola e la mette in "
        "rilievo: γε, περ, καί nel senso di «anche». Pende dalla parola che "
        "sottolinea, e cambiarne il posto cambia che cosa è enfatizzato.",
        "An emphasising particle attaching to a single word and putting it in "
        "relief: γε, περ, καί in the sense “even, also”. It hangs from the word "
        "it underlines, and moving it changes what is emphasised."),
    "schema.rel.AuxX": (
        "La virgola, quando non sta coordinando niente. La virgola che coordina "
        "è invece un COORD, e quella che introduce un'apposizione è un APOS: la "
        "stessa parola scritta porta tre etichette diverse a seconda di che cosa "
        "sta facendo.",
        "The comma, when it is not coordinating anything. A comma that "
        "coordinates is a COORD instead, and one introducing an apposition is an "
        "APOS: the same written mark carries three different labels depending on "
        "what it is doing."),
    "schema.rel.AuxG": (
        "La punteggiatura interna alla frase che non sia la virgola: parentesi, "
        "due punti, trattini, punto in alto.",
        "Sentence-internal punctuation other than the comma: brackets, colons, "
        "dashes, the raised point."),
    "schema.rel.AuxK": (
        "Il segno che chiude la frase: punto, punto interrogativo. Come il "
        "predicato, pende dalla radice dell'albero e non da una parola.",
        "The mark closing the sentence: full stop, question mark. Like the "
        "predicate, it hangs from the root of the tree and not from a word."),
    "schema.rel.UNDEFINED": (
        "Nessuna funzione assegnata. Non è una funzione sintattica: è la "
        "dichiarazione che l'analisi manca, e la parola resta nell'albero senza "
        "dire che cosa ci fa.",
        "No function assigned. It is not a syntactic function: it is the "
        "statement that the analysis is missing, and the word stays in the tree "
        "without saying what it is doing there."),

    # ── The suffixes and the infix ──────────────────────────────────────
    "schema.affix.card": ("I suffissi _CO e _AP, e l'infisso _ExD",
                          "The _CO and _AP suffixes, and the _ExD infix"),
    "schema.affix.intro": (
        "Un'etichetta letta in un file non è sempre nuda. Tre aggiunte possono "
        "comparirvi attaccate, e nessuna delle tre sostituisce la funzione: la "
        "<i>accompagnano</i>, e la funzione resta quella scritta davanti.",
        "A label read in a file is not always bare. Three additions can turn up "
        "attached to it, and none of the three replaces the function: they "
        "<i>accompany</i> it, and the function remains the one written in front."),
    "schema.affix.co": (
        "<b>_CO</b>, «e questo è un membro di una coordinazione». Si aggiunge alla funzione che il membro ha nella frase: due soggetti coordinati sono <span style='font-family:monospace'>SBJ_CO</span> e <span style='font-family:monospace'>SBJ_CO</span>, appesi entrambi al καί, che è COORD. Se quel καί è a sua volta membro di un'altra coordinazione, il suffisso si ripete: <span style='font-family:monospace'>SBJ_CO_CO</span>.",
        "<b>_CO</b>, “and this is a member of a coordination”. It is added to the function the member has in the sentence: two coordinated subjects are <span style='font-family:monospace'>SBJ_CO</span> and <span style='font-family:monospace'>SBJ_CO</span>, both hanging from the καί, which is COORD. If that καί is itself a member of another coordination, the suffix repeats: <span style='font-family:monospace'>SBJ_CO_CO</span>."),
    "schema.affix.ap": (
        "<b>_AP</b>, la stessa cosa per l'apposizione: i membri appesi a un nodo APOS portano la propria funzione seguita da _AP. I due suffissi si sommano quando le due costruzioni si annidano: <span style='font-family:monospace'>ADV_AP_CO</span> è un avverbiale che è membro di una coordinazione dentro un'apposizione.",
        "<b>_AP</b>, the same for apposition: the members hanging from an APOS node carry their own function followed by _AP. The two suffixes stack when the constructions nest: <span style='font-family:monospace'>ADV_AP_CO</span> is an adverbial that is a member of a coordination inside an apposition."),
    "schema.affix.exd": (
        "<b>_ExD</b>, non un suffisso ma un <i>infisso</i>, e dice due cose in un'etichetta sola quando la testa è stata omessa: prima la funzione della parola, poi _ExD con un numero, poi la funzione che aveva la parola mancante. <span style='font-family:monospace'>SBJ_ExD0_ADV</span> si legge: «soggetto di un verbo sottinteso, e quel verbo sottinteso faceva da avverbiale». Il numero distingue le teste omesse quando in una stessa frase ce n'è più d'una.",
        "<b>_ExD</b>, not a suffix but an <i>infix</i>, and it says two things in one label when the head has been left out: first the function of the word, then _ExD with a number, then the function the missing word had. <span style='font-family:monospace'>SBJ_ExD0_ADV</span> reads: “subject of an understood verb, and that understood verb was an adverbial”. The number tells omitted heads apart when a sentence has more than one."),
    "schema.affix.demo": (
        "Tolte le aggiunte, resta la funzione. È l'operazione che il programma "
        "compie prima di qualunque confronto, perché altrimenti la stessa "
        "funzione si conterebbe sotto una dozzina di nomi diversi:",
        "Strip the additions and the function is what is left. This is the "
        "operation the program performs before any comparison, because otherwise "
        "the same function would be counted under a dozen different names:"),

    # ══ The additional columns ═══════════════════════════════════════
    "column.che cosa registra": ("che cosa registra", "what it records"),
    "column.valori ammessi": ("valori ammessi", "admitted values"),
    "column.obbligatoria per": ("obbligatoria per", "required for"),
    "column.facoltativa per": ("facoltativa per", "optional for"),
    "column.gruppo": ("gruppo", "group"),
    "column.etichetta AGDT": ("etichetta AGDT", "AGDT label"),
    "column.in breve": ("in breve", "in brief"),
    "column.che cosa segna": ("che cosa segna", "what it marks"),
    "column.etichetta nel file": ("etichetta nel file", "label in the file"),
    "column.funzione di base": ("funzione di base", "base function"),
}
