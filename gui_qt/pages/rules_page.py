"""The last step: the AGDT 2.0 scheme, explained from the beginning.

The page computes nothing and does not need a loaded corpus. It contains only two
things, which are also the two things the scheme consists of: the nine-character
morphological label, unpacked position by position, and the inventory of syntactic
functions, one by one. It is written for whoever reads Greek and has never programmed:
one can arrive here without knowing what an XML attribute is and leave knowing how to
read ``v3piia---``.

The technical point that matters: **nothing that is seen here is written here**. The
inventory of the nine positions, the values that each admits, the meaning of every
letter, the list of the relations and their short glosses are read from
:mod:`greek_corpus_pipeline.agdt_schema` at the moment the page is drawn, and it is the
same module on which the checks are based. A letter added to the scheme appears here by
itself; a letter removed disappears. The page cannot therefore tell a scheme different
from the one the program verifies — which is the only way to make a page of
documentation inside a program honest.

The examples too are unpacked from the scheme and not transcribed by hand: for each one
only the label and the Greek word are written, and the character by character reading is
built by ``describe_value``. When the additions to the relations (``_CO``, ``_AP``,
``_ExD``) are to be shown at work, it is ``base_relation`` that shows them, that is the
real function that the rest of the program calls.
"""
from __future__ import annotations

import pandas as pd
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from ..i18n import pick, tr
from ..widgets import Card, DataTable, paragraph
from .base import Page

#: Five real labels and the word that carries them. Between them all five touch every
#: position at least once: the noun for number, gender and case; the verb of finite mood
#: for person, tense, mood and voice; the participle for the mood slot that is filled
#: without person but with case; the comparative for the degree, which otherwise would
#: never be seen; and the conjunction, which of all nine fills only the first.
#:
#: They are labels, not glosses: what they mean is said by the scheme when the page is
#: drawn, and if the scheme changed the reading would change.
EXAMPLES: tuple[tuple[str, str], ...] = (
    ("n-p---mg-", "ἀνθρώπων"),
    ("v3piia---", "ἐφύλαττον"),
    ("v-sppamn-", "λύων"),
    ("a-s---mnc", "σοφώτερος"),
    ("c--------", "καί"),
)

#: The functions gathered by family, because twenty-three labels in alphabetical order
#: cannot be learnt and in order of kinship they can. The families serve only to order
#: and to head: the real list is that of the scheme, and a relation that was added there
#: without appearing here would be seen all the same, at the end, under “other”.
RELATION_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("schema.group.core", ("PRED", "SBJ", "OBJ", "PNOM", "OCOMP")),
    ("schema.group.modifier", ("ATR", "ADV", "ATV", "AtvV")),
    ("schema.group.structure", ("COORD", "APOS", "ExD", "MWE")),
    ("schema.group.aux", ("AuxP", "AuxC", "AuxV", "AuxR", "AuxY", "AuxZ")),
    ("schema.group.punct", ("AuxX", "AuxG", "AuxK")),
    ("schema.group.absent", ("UNDEFINED",)),
)

#: Decorated labels as they are read in the files, to show what remains when the
#: additions are removed. All four are attested.
DECORATED_EXAMPLES: tuple[str, ...] = (
    "SBJ_CO", "PRED_CO_CO", "ADV_AP_CO", "SBJ_ExD0_ADV",
)

#: The grey of the empty boxes, the same as the caption under the titles.
_MUTED = "#8a8178"


class RulesPage(Page):
    """The two tabs: the morphological label and the syntactic functions."""

    title_key = "rules.title"
    intro_key = "rules.intro"

    # ── Building the page ──────────────────────────────────────────────
    def build(self) -> None:
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_tag_tab(), tr("schema.tab.tag"))
        self._tabs.addTab(self._build_relations_tab(), tr("schema.tab.relations"))
        self.add(self._tabs, 1)

    def _build_tag_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        self._tag_intro = self._rich(tr("schema.tag.intro"), "pageIntro")
        layout.addWidget(self._tag_intro)

        self._positions_card = Card(tr("schema.positions.card"))
        self._positions_hint = self._rich(tr("schema.positions.hint"), "hint")
        self._positions_card.add(self._positions_hint)
        self._positions = DataTable(min_height=340, column_picker=False)
        self._positions_card.add(self._positions, 1)
        layout.addWidget(self._positions_card, 1)

        self._values_card = Card(tr("schema.values.card"))
        self._values_hint = self._rich(tr("schema.values.hint"), "hint")
        self._values_card.add(self._values_hint)
        self._values = DataTable(min_height=380, column_picker=False)
        self._values_card.add(self._values, 1)
        layout.addWidget(self._values_card, 1)

        self._dash_card = Card(tr("schema.dash.card"))
        self._dash = self._rich(tr("schema.dash.text"))
        self._dash_card.add(self._dash)
        layout.addWidget(self._dash_card)

        self._examples_card = Card(tr("schema.examples.card"))
        self._examples_hint = self._rich(tr("schema.examples.hint"), "hint")
        self._examples_card.add(self._examples_hint)
        self._examples = self._rich("")
        self._examples_card.add(self._examples)
        layout.addWidget(self._examples_card)

        layout.addStretch(1)
        return page

    def _build_relations_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        self._relations_intro = self._rich(tr("schema.rel.intro"), "pageIntro")
        layout.addWidget(self._relations_intro)

        self._relations_card = Card(tr("schema.rel.card"))
        self._relations = DataTable(min_height=420, column_picker=False)
        self._relations_card.add(self._relations, 1)
        layout.addWidget(self._relations_card, 1)

        self._affix_card = Card(tr("schema.affix.card"))
        self._affix_intro = self._rich(tr("schema.affix.intro"))
        self._affix_card.add(self._affix_intro)
        self._affix_co = self._rich(tr("schema.affix.co"))
        self._affix_card.add(self._affix_co)
        self._affix_ap = self._rich(tr("schema.affix.ap"))
        self._affix_card.add(self._affix_ap)
        self._affix_exd = self._rich(tr("schema.affix.exd"))
        self._affix_card.add(self._affix_exd)
        self._affix_demo = self._rich(tr("schema.affix.demo"), "hint")
        self._affix_card.add(self._affix_demo)
        self._affixes = DataTable(min_height=170, column_picker=False,
                                  searchable=False)
        self._affix_card.add(self._affixes)
        layout.addWidget(self._affix_card)

        layout.addStretch(1)
        return page

    @staticmethod
    def _rich(text: str, object_name: str = "pageIntro"):
        """A paragraph that knows it is written in HTML.

        Without telling it, QLabel guesses the format from the first character and
        guesses wrong every time the text begins with a word instead of a tag: the bold
        type would show on the screen as it is written.
        """
        label = paragraph(text, object_name)
        label.setTextFormat(Qt.TextFormat.RichText)
        return label

    # ── Language ───────────────────────────────────────────────────────
    def retranslate(self) -> None:
        for index, key in enumerate(("schema.tab.tag", "schema.tab.relations")):
            self._tabs.setTabText(index, tr(key))
        # Everything else — paragraphs, titles of the tabs, tables — is rewritten in
        # ``refresh``, which ``super().retranslate`` calls at the end.
        super().retranslate()

    # ── Drawing the page ───────────────────────────────────────────────
    def refresh(self) -> None:
        self._positions_card.set_title(tr("schema.positions.card"))
        self._values_card.set_title(tr("schema.values.card"))
        self._dash_card.set_title(tr("schema.dash.card"))
        self._examples_card.set_title(tr("schema.examples.card"))
        self._relations_card.set_title(tr("schema.rel.card"))
        self._affix_card.set_title(tr("schema.affix.card"))

        self._tag_intro.setText(tr("schema.tag.intro"))
        self._positions_hint.setText(tr("schema.positions.hint"))
        self._values_hint.setText(tr("schema.values.hint"))
        self._dash.setText(tr("schema.dash.text"))
        self._examples_hint.setText(tr("schema.examples.hint"))
        self._relations_intro.setText(tr("schema.rel.intro"))
        self._affix_intro.setText(tr("schema.affix.intro"))
        self._affix_co.setText(tr("schema.affix.co"))
        self._affix_ap.setText(tr("schema.affix.ap"))
        self._affix_exd.setText(tr("schema.affix.exd"))
        self._affix_demo.setText(tr("schema.affix.demo"))

        self._positions.set_dataframe(self._positions_frame())
        self._values.set_dataframe(self._values_frame())
        self._examples.setText(self._examples_html())
        self._relations.set_dataframe(self._relations_frame())
        self._affixes.set_dataframe(self._affixes_frame())

    # ── The morphological label, read from the scheme ──────────────────
    def _positions_frame(self) -> pd.DataFrame:
        """The nine positions: what they are for and who has the right to fill them."""
        from greek_corpus_pipeline.agdt_schema import (
            NOT_APPLICABLE, POSITION_NAMES, POSITION_VALUES,
        )

        rows = []
        for index, names in POSITION_NAMES.items():
            admitted = [character
                        for character in POSITION_VALUES.get(index, {})
                        if character != NOT_APPLICABLE]
            required, optional = self._who_fills(index)
            rows.append({
                "posizione": index + 1,
                "tratto": pick(names),
                "che cosa registra": tr(f"schema.pos.{index}"),
                "valori ammessi": " ".join(admitted),
                "obbligatoria per": required,
                "facoltativa per": optional,
            })
        return pd.DataFrame(rows)

    @staticmethod
    def _who_fills(index: int) -> tuple[str, str]:
        """Which parts of speech must, and which may, fill the box.

        It comes out of the two profile tables of the scheme. The verb is the only one
        that does not have a single profile — the mood decides whether the form has
        person or case — and the moods that share the same profile are stated together,
        so that the person box turns out to be compulsory for “verb: indicative,
        subjunctive, optative, imperative” and not for the verb in general.
        """
        from greek_corpus_pipeline.agdt_schema import (
            MOOD_SLOT, POS_SLOT, POSITION_VALUES, SLOT_PROFILE,
            VERB_SLOT_PROFILE, describe_value,
        )

        from ..i18n import T

        if index == POS_SLOT:
            # The first position has no profile because it is what chooses it.
            return tr("schema.always"), "—"

        language = T.language
        required: list[str] = []
        optional: list[str] = []
        for character, profile in SLOT_PROFILE.items():
            name = describe_value(POS_SLOT, character, language)
            if index in profile["require"]:
                required.append(name)
            elif index in profile["optional"]:
                optional.append(name)

        # The moods that share the same profile are the same object in the table of the
        # scheme, and are recognised by that. The moods that the inventory of values
        # does not declare, and the profile without mood, stay out.
        families: dict[int, tuple[dict, list[str]]] = {}
        for mood, profile in VERB_SLOT_PROFILE.items():
            if mood is None or mood not in POSITION_VALUES.get(MOOD_SLOT, {}):
                continue
            families.setdefault(id(profile), (profile, []))[1].append(mood)

        verb_required: list[str] = []
        verb_optional: list[str] = []
        for profile, moods in families.values():
            label = ", ".join(describe_value(MOOD_SLOT, mood, language)
                              for mood in moods)
            if index in profile["require"]:
                verb_required.append(label)
            elif index in profile["optional"]:
                verb_optional.append(label)

        verb = tr("schema.verb_prefix")
        if verb_required:
            required.append(f"{verb}: {'; '.join(verb_required)}")
        if verb_optional:
            optional.append(f"{verb}: {'; '.join(verb_optional)}")
        return (" · ".join(required) or "—", " · ".join(optional) or "—")

    def _values_frame(self) -> pd.DataFrame:
        """The closed inventory: every admitted letter and what it means."""
        from greek_corpus_pipeline.agdt_schema import (
            POSITION_NAMES, POSITION_VALUES,
        )

        rows = []
        for index, names in POSITION_NAMES.items():
            for character, labels in POSITION_VALUES.get(index, {}).items():
                rows.append({
                    "posizione": index + 1,
                    "tratto": pick(names),
                    "carattere": character,
                    "significato": pick(labels),
                })
        return pd.DataFrame(rows)

    def _examples_html(self) -> str:
        """The example labels, unpacked one position at a time."""
        from greek_corpus_pipeline.agdt_schema import (
            NOT_APPLICABLE, POSITION_NAMES, describe_postag, describe_value,
        )

        from ..i18n import T

        language = T.language
        blocks: list[str] = []
        for tag, word in EXAMPLES:
            rows: list[str] = []
            for index, character in enumerate(tag):
                empty = character == NOT_APPLICABLE
                colour = f" style='color:{_MUTED}'" if empty else ""
                rows.append(
                    "<tr>"
                    f"<td align='right'{colour}>{index + 1}</td>"
                    "<td><span style='font-family:monospace; font-size:15px'>"
                    f"{character}</span></td>"
                    f"<td{colour}>{pick(POSITION_NAMES[index])}</td>"
                    f"<td{colour}>{describe_value(index, character, language)}</td>"
                    "</tr>")
            blocks.append(
                f"<p><b style='font-size:15px'>{word}</b>&nbsp;&nbsp;"
                "<span style='font-family:monospace; font-size:15px'>"
                f"{tag}</span><br><i>{describe_postag(tag, language)}</i></p>"
                "<table width='100%' cellspacing='0' cellpadding='3'>"
                f"{''.join(rows)}</table>")
        return "<br>".join(blocks)

    # ── The syntactic functions, read from the scheme ──────────────────
    def _relations_frame(self) -> pd.DataFrame:
        """The inventory of the relations, by family.

        The families order; the list is that of the scheme. Every relation declared
        there appears here exactly once: those that a family does not name end up at the
        end under “other”, and those that a family names but the scheme does not declare
        do not appear at all.
        """
        from greek_corpus_pipeline.agdt_schema import RELATIONS

        family = {name: key for key, names in RELATION_GROUPS for name in names}

        def _row(name: str) -> dict:
            glosses = RELATIONS[name]
            key = f"schema.rel.{name}"
            explanation = tr(key)
            if explanation == key:
                # A relation added to the scheme and not yet explained here: better the
                # short gloss than a missing row.
                explanation = pick(glosses)
            return {
                "gruppo": tr(family.get(name, "schema.group.other")),
                "etichetta AGDT": name,
                "in breve": pick(glosses),
                "che cosa segna": explanation,
            }

        named = [name for _key, names in RELATION_GROUPS for name in names]
        ordered = [name for name in named if name in RELATIONS]
        ordered += [name for name in RELATIONS if name not in set(named)]
        return pd.DataFrame([_row(name) for name in ordered])

    def _affixes_frame(self) -> pd.DataFrame:
        """The decorated labels and the function that remains when the additions are
        removed.

        The computation is done by ``base_relation``, that is the same function that the
        rest of the program calls before every comparison: the right-hand column is not
        an illustration of the operation, it is the operation.
        """
        from greek_corpus_pipeline.agdt_schema import base_relation

        return pd.DataFrame([
            {"etichetta nel file": label,
             "funzione di base": base_relation(label)}
            for label in DECORATED_EXAMPLES
        ])
