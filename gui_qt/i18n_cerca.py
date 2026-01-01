# -*- coding: utf-8 -*-
"""The entries of the “Search the corpus” tab.

They live here and not in :mod:`gui_qt.i18n` for the same reason as the entries of the
“Correct” tab: the general file would otherwise grow too large. ``i18n`` imports this
module by itself and adds its entries to the general dictionary; each key is written in
one place only.

The shape is the same as ``_STRINGS``: dotted key -> (Italian, English). All the keys
begin with ``search.`` — what the page says — or with ``column.`` — the name of a field,
which the tables and the right-hand panel translate at the moment they draw it, leaving
the data intact.
"""
from __future__ import annotations

STRINGS: dict[str, tuple[str, str]] = {

    # ── What this page is ──────────────────────────────────────────────
    "search.intro": (
        "Due ricerche, indipendenti l'una dall'altra: la forma per conto suo, "
        "il lemma per conto suo. Puoi scrivere in greco con gli accenti "
        "(ἄνθρωπος), in greco senza accenti né spiriti (ανθρωπος) o in "
        "caratteri latini (anthropos): sono la stessa parola e danno lo stesso "
        "risultato. Prima compare l'elenco di tutte le occorrenze con la frase "
        "in cui si trovano; poi, scegliendo una riga, si legge che parola è.",
        "Two searches, independent of each other: the form on its own, the "
        "lemma on its own. You can type Greek with accents (ἄνθρωπος), Greek "
        "without accents or breathings (ανθρωπος), or Latin letters "
        "(anthropos): they are the same word and they give the same result. "
        "First comes the list of every occurrence with the sentence it appears "
        "in; then, by choosing a row, you read what the word is."),

    # ── The search bar ─────────────────────────────────────────────────
    "search.form.placeholder": ("ἄνθρωπος · ανθρωπος · anthropos",
                                "ἄνθρωπος · ανθρωπος · anthropos"),
    "search.lemma.placeholder": ("λέγω · λεγω · lego",
                                 "λέγω · λεγω · lego"),
    "search.go_form": ("Cerca questa forma", "Search this form"),
    "search.go_lemma": ("Cerca questo lemma", "Search this lemma"),
    "search.independent": (
        "Le due righe non si sommano: il pulsante della forma cerca soltanto "
        "la forma, quello del lemma soltanto il lemma. Quello che è scritto "
        "nell'altra riga non entra nella ricerca.",
        "The two rows do not add up: the form button searches the form and "
        "nothing else, the lemma button the lemma and nothing else. Whatever "
        "is written in the other row plays no part in the search."),
    "search.typing_hint": (
        "Accenti, spiriti, iota sottoscritte, apostrofi e sigma finale non "
        "contano: ανθρωποσ trova ἄνθρωπος. In caratteri latini valgono th = θ, "
        "ph = φ, ch = χ, ps = ψ, x = ξ, y = υ; e ed o valgono sia breve sia "
        "lunga (anthropos trova ἄνθρωπος), a meno che tu non scriva ē oppure "
        "ō, e allora vale soltanto la lunga.",
        "Accents, breathings, iota subscripts, apostrophes and final sigma do "
        "not count: ανθρωποσ finds ἄνθρωπος. In Latin letters th = θ, ph = φ, "
        "ch = χ, ps = ψ, x = ξ, y = υ; e and o stand for both the short and "
        "the long vowel (anthropos finds ἄνθρωπος) unless you write ē or ō, "
        "and then only the long one counts."),
    "search.no_criteria": (
        "Scrivi una forma oppure un lemma, poi premi il pulsante che sta "
        "accanto a quello che hai scritto.",
        "Type a form or a lemma, then press the button beside the one you "
        "have typed."),
    "search.none": (
        "Nessuna occorrenza. Prova con «inizia con» o «contiene», oppure "
        "controlla di aver scritto la parola nella riga giusta: la forma è "
        "quella che sta nel testo, il lemma quello del dizionario.",
        "No occurrences. Try “starts with” or “contains”, or check that the "
        "word is in the right row: the form is the one in the text, the lemma "
        "the dictionary one."),
    "search.failed": ("La ricerca non è riuscita: {0}", "The search failed: {0}"),

    # ── How what was asked is read ─────────────────────────────────────
    "search.query.one": ("{0} {1} «{2}»", "{0} {1} “{2}”"),
    "search.query.none": ("nessuna ricerca", "no search"),
    "search.field.form": ("forma", "form"),
    "search.field.lemma": ("lemma", "lemma"),

    # ── The list of occurrences ────────────────────────────────────────
    "search.list": ("Le occorrenze, con la frase in cui compaiono",
                    "The occurrences, with the sentence they appear in"),
    "search.list_hint": (
        "Una riga per occorrenza. La parola cercata è fra virgolette basse; "
        "la frase si ferma dove finisce la frase del corpus.",
        "One row per occurrence. The word searched for is between guillemets; "
        "the sentence stops where the corpus's sentence stops."),
    "search.capped": ("mostrate le prime {0}", "showing the first {0}"),

    # ── The right-hand panel: which word it is ─────────────────────────
    "search.detail": ("Che parola è", "What this word is"),
    "search.context": ("Contesto", "Context"),
    "search.select_row": (
        "Scegli una riga dell'elenco: qui compaiono il contesto, la morfologia, "
        "la funzione sintattica, il lemma, il lemma della testa e l'autore.",
        "Choose a row from the list: its context, morphology, syntactic function, "
        "lemma, head lemma and author appear here."),

    # ── The names of the fields, as they are read ──────────────────────
    "column.n.": ("n.", "no."),
    "column.contesto": ("contesto", "context"),
    "column.morfologia": ("morfologia", "morphology"),
    "column.funzione sintattica": ("funzione sintattica", "syntactic function"),
    "column.lemma": ("lemma", "lemma"),
    "column.lemma della testa": ("lemma della testa", "lemma of the head"),
}
