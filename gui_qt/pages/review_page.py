"""Step 5 — deciding what to correct, one case at a time.

This page offers no automatic corrections. A list of rules with ticks would
apply a rule to all its occurrences at once — thousands of words changed
without anybody having looked at a single sentence. That is not what a
philological revision is, and it is not what this program must encourage. Two
ways are offered, and neither writes anything that the user has not seen:

1. **the dictionary of forms**, the only mass correction on offer, because its
   content is written by the user on their own computer: a CSV with ``form``
   (mandatory) and ``postag`` and/or ``lemma``. The format is declared on the
   screen, beside the field, and a button downloads the template with its
   header already in place — because “a CSV with two columns” is not an answer
   to the question “which file does it want?”;

2. **the proposals, one at a time**: each finding that carries a proposed value
   appears in a row that shows the present value and the proposed one side by
   side — ``a-s---fgp-----`` → ``a-s---fgp-`` — and is accepted or refused on
   its own. Never a whole rule.

The register of decisions is a readable CSV, and nothing is written into the
corpus until “Apply” is pressed. The original corpus is never touched: the
corrections produce a second, separate version, which step 10 exports. The
export is all there, and here there is no copy of it.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QScrollArea, QSizePolicy, QSplitter, QTabWidget, QVBoxLayout,
    QWidget,
)

from ..style import ACCENT, CARD, LINE
from ..i18n import number, tr, value_label
from ..widgets import (
    GREEK_COLUMNS, Card, DataTable, LabeledField, ghost_button, greek_line_edit,
    heading, notice, paragraph, primary_button, separator,
)
from ..workers import apply_corrections
from .base import Page
from .errors_page import _sentence_with_marker

# The columns of this page that carry polytonic Greek. The name of the columns is the
# only thing that the shared table looks at to choose the font, and these are names that
# originate here.
GREEK_COLUMNS.update({"lemma_proposto", "lemma vecchio", "lemma nuovo"})

#: The separator between the present value and the proposed one. Only one, and declared
#: here, because the same arrow must appear in all the columns.
ARROW = "  →  "

#: The decisions that count as “position taken”: a refused proposal is as decided as an
#: accepted one, and must not return to the list of what remains to be looked at.
REJECTED = "respinta"

#: Below this number of words a comparison with the whole corpus costs less than a tenth
#: of a second and is done on the interface thread; above it, it is not.
SMALL_CORPUS = 60_000


def _text(values: pd.Series) -> pd.Series:
    """Any column as clean text, with no NaN and no edge spaces."""
    return values.astype("string").fillna("").astype(str).str.strip()


def _one(value: object) -> str:
    """A single value as text, whether it comes from pandas or from a CSV."""
    if value is None:
        return ""
    if not isinstance(value, str):
        try:
            if pd.isna(value):
                return ""
        except (TypeError, ValueError):                # noqa: BLE001
            pass
    return str(value).strip()


def _blank(frame: pd.DataFrame) -> pd.Series:
    return pd.Series([""] * len(frame), index=frame.index, dtype=str)


def _key_series(frame: pd.DataFrame) -> pd.Series:
    """The key of the token as text, immune to the int/str/float mixture.

    ``token_id`` arrives as 5 from the corpus, as "5" from the register of decisions and
    as 5.0 from a CSV that pandas has decided is decimal: without this the three never
    meet and a decision already taken turns out to be still to be taken.
    """
    pieces = []
    for column in ("document_id", "sentence_id", "token_id"):
        if column not in frame.columns:
            pieces.append(_blank(frame))
            continue
        values = frame[column]
        if pd.api.types.is_float_dtype(values):
            pieces.append(values.map(
                lambda value: "" if pd.isna(value)
                else (str(int(value)) if float(value).is_integer() else str(value))))
        else:
            pieces.append(_text(values))
    return pd.Series(["\x00".join(row) for row in zip(*pieces)], index=frame.index)


def _key_of(row) -> str:
    def one(name: str) -> str:
        value = row.get(name)
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return ""
        if isinstance(value, float) and float(value).is_integer():
            return str(int(value))
        return str(value).strip()
    return "\x00".join(one(name) for name in
                       ("document_id", "sentence_id", "token_id"))


class ReviewPage(Page):

    title_key = "review.title"
    intro_key = "review.intro"

    # ── Building the page ──────────────────────────────────────────────
    def build(self) -> None:
        self._current_row: pd.Series | None = None
        self._cases: pd.DataFrame | None = None
        self._cases_key: tuple | None = None
        self._cases_view: pd.DataFrame = pd.DataFrame()
        self._dictionary_path: str = ""
        self._dictionary_entries: pd.DataFrame = pd.DataFrame()
        self._coverage_key: tuple | None = None
        self._coverage = None

        self._locked = notice(tr("step.needs_analysis"), "info")
        self.add(self._locked)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_cases_tab(), tr("review.tab.cases"))
        self._tabs.addTab(self._build_dictionary_tab(), tr("review.tab.dictionary"))
        self._tabs.addTab(self._build_decisions_tab(), tr("review.tab.decisions"))
        self.add(self._tabs, 1)

        self.add(self._build_apply_card())

        # The pointer to step 10. It appears only when a gold really exists, because an
        # invitation to export something that is not there is a lie.
        self._gold_ready = Card(tr("review.gold_ready.title"))
        self._gold_ready_body = paragraph("", "hint")
        self._gold_ready.add(self._gold_ready_body)
        open_row = QHBoxLayout()
        self._open_gold = primary_button(tr("review.gold_ready.open"))
        self._open_gold.clicked.connect(lambda: self.requestNavigate.emit("gold"))
        open_row.addWidget(self._open_gold)
        open_row.addStretch(1)
        self._gold_ready.add_layout(open_row)
        self._gold_ready.setVisible(False)
        self.add(self._gold_ready)

    # ── Tab 1: the proposals, one at a time ────────────────────────────
    def _build_cases_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self._cases_hint = paragraph(tr("review.cases.hint"), "hint")
        layout.addWidget(self._cases_hint)

        filter_row = QHBoxLayout()
        self._rule_caption = QLabel(tr("errors.filter_rule"))
        self._rule_caption.setObjectName("hint")
        self._rule_filter = QComboBox()
        self._rule_filter.setMinimumWidth(300)
        self._rule_filter.currentIndexChanged.connect(self._filter_cases)
        self._only_proposals = QCheckBox(tr("review.cases.only_proposals"))
        self._only_proposals.setChecked(True)
        self._only_proposals.stateChanged.connect(self._filter_cases)
        self._only_undecided = QCheckBox(tr("review.cases.only_undecided"))
        self._only_undecided.stateChanged.connect(self._filter_cases)
        filter_row.addWidget(self._rule_caption)
        filter_row.addWidget(self._rule_filter)
        filter_row.addWidget(self._only_proposals)
        filter_row.addWidget(self._only_undecided)
        filter_row.addStretch(1)
        layout.addLayout(filter_row)

        self._cases_empty = notice(tr("review.cases.none"), "info")
        self._cases_empty.setVisible(False)
        layout.addWidget(self._cases_empty)

        self._cases_table = DataTable(min_height=340)
        self._cases_table.rowSelected.connect(self._select_case)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._cases_table)
        splitter.addWidget(self._build_editor())
        splitter.setSizes([720, 480])
        splitter.setMinimumHeight(480)
        layout.addWidget(splitter, 1)

        self._cases_count = QLabel("")
        self._cases_count.setObjectName("hint")
        layout.addWidget(self._cases_count)
        return page

    def _build_editor(self) -> QWidget:
        # The panel scrolls: the sentence at the top has no fixed height, and a long
        # period would push the fields of the correction off the bottom, where they
        # could no longer be reached.
        panel = QWidget()
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.Shape.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("page")
        area.setWidget(inner)
        outer.addWidget(area)
        self._editor_area = area

        layout = QVBoxLayout(inner)
        layout.setContentsMargins(16, 0, 6, 12)
        layout.setSpacing(11)

        self._sentence = QLabel(tr("errors.select_row"))
        self._sentence.setWordWrap(True)
        self._sentence.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self._sentence.setSizePolicy(QSizePolicy.Policy.Preferred,
                                     QSizePolicy.Policy.MinimumExpanding)
        self._sentence.setStyleSheet(
            f"background:{CARD}; border:1px solid {LINE};"
            f"border-left:3px solid {ACCENT}; padding:13px 16px;"
            "border-radius:7px; font-family:'GFS Didot','Palatino Linotype',serif;"
            "font-size:17px; line-height:180%;")
        layout.addWidget(self._sentence)

        self._current_title = heading(tr("review.current"))
        layout.addWidget(self._current_title)
        self._current = QLabel("")
        self._current.setWordWrap(True)
        self._current.setSizePolicy(QSizePolicy.Policy.Preferred,
                                    QSizePolicy.Policy.MinimumExpanding)
        layout.addWidget(self._current)

        layout.addWidget(separator())

        # The heart of the page: what the program proposes, beside what is written now,
        # for this case and for no other.
        self._proposal_title = heading(tr("review.proposal"))
        layout.addWidget(self._proposal_title)
        self._proposal = QLabel("")
        self._proposal.setWordWrap(True)
        self._proposal.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self._proposal.setSizePolicy(QSizePolicy.Policy.Preferred,
                                     QSizePolicy.Policy.MinimumExpanding)
        layout.addWidget(self._proposal)

        decide_row = QHBoxLayout()
        self._accept = primary_button(tr("review.accept"))
        self._accept.setToolTip(tr("review.accept.hint"))
        self._accept.clicked.connect(self._accept_proposal)
        self._accept.setEnabled(False)
        self._reject = ghost_button(tr("review.reject"))
        self._reject.setToolTip(tr("review.reject.hint"))
        self._reject.clicked.connect(self._reject_proposal)
        self._reject.setEnabled(False)
        decide_row.addWidget(self._accept)
        decide_row.addWidget(self._reject)
        decide_row.addStretch(1)
        layout.addLayout(decide_row)

        layout.addWidget(separator())

        self._by_hand_title = heading(tr("review.by_hand"))
        layout.addWidget(self._by_hand_title)

        self._new_lemma = greek_line_edit("")
        self._new_postag = QLineEdit()
        self._new_postag.setPlaceholderText(tr("review.postag.hint"))
        self._new_relation = QLineEdit()
        self._new_relation.setPlaceholderText(tr("review.relation.hint"))
        self._new_lemma_field = LabeledField(tr("review.new_lemma"), self._new_lemma)
        self._new_postag_field = LabeledField(tr("review.new_postag"), self._new_postag)
        self._new_relation_field = LabeledField(tr("review.new_relation"),
                                                self._new_relation)
        layout.addWidget(self._new_lemma_field)
        layout.addWidget(self._new_postag_field)
        layout.addWidget(self._new_relation_field)

        # Who decided and why. Without these two fields the register says what has
        # changed and nothing else, and a review by several hands can be neither
        # discussed nor redone. The name stays written from one correction to the next;
        # the reason is emptied each time because it is specific to the case.
        self._decided_by = QLineEdit()
        self._decided_by.setPlaceholderText(tr("review.decided_by.hint"))
        self._reason = QLineEdit()
        self._reason.setPlaceholderText(tr("review.reason.hint"))
        self._decided_by_field = LabeledField(tr("review.decided_by"), self._decided_by)
        self._reason_field = LabeledField(tr("review.reason"), self._reason)
        layout.addWidget(self._decided_by_field)
        layout.addWidget(self._reason_field)

        self._save = primary_button(tr("review.save"))
        self._save.clicked.connect(self._save_correction)
        self._save.setEnabled(False)
        layout.addWidget(self._save)

        self._save_status = QLabel("")
        self._save_status.setObjectName("hint")
        self._save_status.setWordWrap(True)
        layout.addWidget(self._save_status)
        layout.addStretch(1)
        return panel

    # ── Tab 2: the dictionary of forms ─────────────────────────────────
    def _build_dictionary_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self._dict_card = Card(tr("review.dict.title"))
        self._dict_intro = paragraph(tr("review.dict.intro"), "hint")
        self._dict_card.add(self._dict_intro)

        # The format, in full and on the screen. It is the answer to the question “which
        # file does it want as input?”, and must be beside the field, not inside the
        # code.
        self._dict_format = QLabel(tr("review.dict.format"))
        self._dict_format.setWordWrap(True)
        self._dict_format.setTextFormat(Qt.TextFormat.RichText)
        self._dict_format.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self._dict_format.setStyleSheet(
            "background:#fbfaf7; border:1px solid #e6e0d6; border-radius:6px;"
            "padding:14px 16px;")
        self._dict_card.add(self._dict_format)

        template_row = QHBoxLayout()
        self._dict_template = primary_button(tr("review.dict.template"))
        self._dict_template.setToolTip(tr("review.dict.template.hint"))
        self._dict_template.clicked.connect(self._save_template)
        template_row.addWidget(self._dict_template)
        template_row.addStretch(1)
        self._dict_card.add_layout(template_row)
        layout.addWidget(self._dict_card)

        chooser = QHBoxLayout()
        self._dict_path = QLineEdit()
        self._dict_path.setPlaceholderText(tr("review.dict.placeholder"))
        self._dict_path.setReadOnly(True)
        self._dict_browse = ghost_button(tr("review.dict.choose"))
        self._dict_clear = ghost_button(tr("review.dict.clear"))
        self._dict_browse.clicked.connect(self._choose_dictionary)
        self._dict_clear.clicked.connect(self._clear_dictionary)
        chooser.addWidget(self._dict_path, 1)
        chooser.addWidget(self._dict_browse)
        chooser.addWidget(self._dict_clear)
        holder = QWidget()
        holder.setLayout(chooser)
        self._dict_field = LabeledField(tr("review.dict.file"), holder)
        layout.addWidget(self._dict_field)

        self._dict_report = notice(tr("review.dict.none"), "info")
        layout.addWidget(self._dict_report)

        self._dict_preview_title = heading(tr("review.dict.preview"))
        layout.addWidget(self._dict_preview_title)
        self._dict_preview = DataTable(min_height=200)
        layout.addWidget(self._dict_preview, 1)

        save_row = QHBoxLayout()
        self._dict_save_mine = ghost_button(tr("review.dict.save_mine"))
        self._dict_save_mine.setToolTip(tr("review.dict.save_mine.hint"))
        self._dict_save_mine.clicked.connect(self._save_my_dictionary)
        save_row.addWidget(self._dict_save_mine)
        save_row.addStretch(1)
        layout.addLayout(save_row)
        self._dict_save_hint = paragraph(tr("review.dict.save_mine.hint"), "hint")
        layout.addWidget(self._dict_save_hint)
        return page

    # ── Tab 3: the register of decisions ───────────────────────────────
    def _build_decisions_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self._decisions_hint = paragraph(tr("review.decisions.hint"), "hint")
        layout.addWidget(self._decisions_hint)

        self._decisions_empty = notice(tr("review.decisions.none"), "info")
        layout.addWidget(self._decisions_empty)

        self._decisions_table = DataTable(min_height=320)
        layout.addWidget(self._decisions_table, 1)

        row = QHBoxLayout()
        self._remove_button = ghost_button(tr("review.remove"))
        self._remove_button.clicked.connect(self._remove_correction)
        row.addWidget(self._remove_button)
        row.addStretch(1)
        layout.addLayout(row)
        return page

    # ── The application to the corpus ──────────────────────────────────
    def _build_apply_card(self) -> QWidget:
        self._apply_card = Card(tr("review.apply.title"))
        self._apply_hint = paragraph(tr("review.apply.hint"), "hint")
        self._apply_card.add(self._apply_hint)
        self._apply_summary = QLabel("")
        self._apply_summary.setObjectName("hint")
        self._apply_summary.setWordWrap(True)
        self._apply_card.add(self._apply_summary)
        row = QHBoxLayout()
        self._apply = primary_button(tr("review.apply"))
        self._apply.clicked.connect(self._apply_now)
        row.addWidget(self._apply)
        row.addStretch(1)
        self._apply_card.add_layout(row)
        return self._apply_card

    # ── Language ───────────────────────────────────────────────────────
    def retranslate(self) -> None:
        self._locked.setText(tr("step.needs_analysis"))
        for index, key in enumerate(("review.tab.cases", "review.tab.dictionary",
                                     "review.tab.decisions")):
            self._tabs.setTabText(index, tr(key))

        self._cases_hint.setText(tr("review.cases.hint"))
        self._rule_caption.setText(tr("errors.filter_rule"))
        self._only_proposals.setText(tr("review.cases.only_proposals"))
        self._only_undecided.setText(tr("review.cases.only_undecided"))
        self._cases_empty.setText(tr("review.cases.none"))
        self._current_title.setText(tr("review.current"))
        self._proposal_title.setText(tr("review.proposal"))
        self._accept.setText(tr("review.accept"))
        self._accept.setToolTip(tr("review.accept.hint"))
        self._reject.setText(tr("review.reject"))
        self._reject.setToolTip(tr("review.reject.hint"))
        self._by_hand_title.setText(tr("review.by_hand"))
        self._new_postag.setPlaceholderText(tr("review.postag.hint"))
        self._new_relation.setPlaceholderText(tr("review.relation.hint"))
        self._new_lemma_field.set_label(tr("review.new_lemma"))
        self._new_postag_field.set_label(tr("review.new_postag"))
        self._new_relation_field.set_label(tr("review.new_relation"))
        self._decided_by.setPlaceholderText(tr("review.decided_by.hint"))
        self._reason.setPlaceholderText(tr("review.reason.hint"))
        self._decided_by_field.set_label(tr("review.decided_by"))
        self._reason_field.set_label(tr("review.reason"))
        self._save.setText(tr("review.save"))

        self._dict_card.set_title(tr("review.dict.title"))
        self._dict_intro.setText(tr("review.dict.intro"))
        self._dict_format.setText(tr("review.dict.format"))
        self._dict_template.setText(tr("review.dict.template"))
        self._dict_template.setToolTip(tr("review.dict.template.hint"))
        self._dict_path.setPlaceholderText(tr("review.dict.placeholder"))
        self._dict_browse.setText(tr("review.dict.choose"))
        self._dict_clear.setText(tr("review.dict.clear"))
        self._dict_field.set_label(tr("review.dict.file"))
        self._dict_preview_title.setText(tr("review.dict.preview"))
        self._dict_save_mine.setText(tr("review.dict.save_mine"))
        self._dict_save_mine.setToolTip(tr("review.dict.save_mine.hint"))
        self._dict_save_hint.setText(tr("review.dict.save_mine.hint"))

        self._decisions_hint.setText(tr("review.decisions.hint"))
        self._decisions_empty.setText(tr("review.decisions.none"))
        self._remove_button.setText(tr("review.remove"))

        self._apply_card.set_title(tr("review.apply.title"))
        self._apply_hint.setText(tr("review.apply.hint"))
        self._apply.setText(tr("review.apply"))
        self._gold_ready.set_title(tr("review.gold_ready.title"))
        self._open_gold.setText(tr("review.gold_ready.open"))
        if self._current_row is None:
            self._sentence.setText(tr("errors.select_row"))
        self._describe_dictionary()
        super().retranslate()

    # ── State ──────────────────────────────────────────────────────────
    def refresh(self) -> None:
        has_findings = self.state.has_findings
        self._locked.setVisible(not has_findings)
        self._tabs.setVisible(has_findings)
        self._apply_card.setVisible(has_findings)
        if not has_findings:
            self._gold_ready.setVisible(False)
            return

        self._populate_rule_filter()
        self._filter_cases()
        manual = self._load_manual()
        self._show_decisions(manual)
        self._describe_dictionary()
        self._update_apply_summary(manual)
        self._refresh_gold_section(self.state.token_diff, manual)

    def _refresh_gold_section(self, difference: pd.DataFrame,
                              manual: pd.DataFrame) -> None:
        """Shows the pointer to step 10 only when a gold really exists.

        “Really exists” means two things together: that at least one word has changed,
        and that the change has been applied to the corpus. A correction that has been
        written and not yet applied is not a gold, it is an intention.
        """
        changed = 0 if difference is None else len(difference)
        decisions = 0 if manual is None else len(manual)
        ready = changed > 0 or decisions > 0
        self._gold_ready.setVisible(ready)
        if ready:
            self._gold_ready_body.setText(
                tr("review.gold_ready.body").format(n=max(changed, decisions)))

    # ── The register of decisions, on disk ─────────────────────────────
    def _manual_path(self) -> Path | None:
        if not self.state.run_id:
            return None
        from greek_corpus_pipeline.storage import run_dir
        return run_dir(self.state.workspace, self.state.run_id) / "correzioni_manuali.csv"

    def _manual_stamp(self) -> tuple:
        """A cheap fingerprint of the register, so that a save invalidates it."""
        path = self._manual_path()
        if path is None or not path.exists():
            return ()
        stat = path.stat()
        return (stat.st_mtime_ns, stat.st_size)

    def _load_manual(self) -> pd.DataFrame:
        path = self._manual_path()
        from greek_corpus_pipeline.gold import MANUAL_COLUMNS, ensure_manual_columns
        if path is None or not path.exists():
            return pd.DataFrame(columns=MANUAL_COLUMNS)
        try:
            return ensure_manual_columns(
                pd.read_csv(path, dtype=str, keep_default_na=False))
        except Exception:                              # noqa: BLE001
            return pd.DataFrame(columns=MANUAL_COLUMNS)

    def _accepted_decisions(self) -> pd.DataFrame:
        """The decisions to apply: all except those refused.

        A register file without the “stato” (status) column counts all its rows as
        accepted: a register written without that column can only hold accepted
        decisions.
        """
        manual = self._load_manual()
        if manual.empty or "status" not in manual.columns:
            return manual
        return manual[_text(manual["status"]).ne(REJECTED)]

    def _write_manual(self, frame: pd.DataFrame) -> None:
        path = self._manual_path()
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False, encoding="utf-8-sig")

    # ── The cases ──────────────────────────────────────────────────────
    def _populate_rule_filter(self) -> None:
        from greek_corpus_pipeline.rule_catalog import rule_name
        from ..i18n import T
        findings = self.state.findings
        if findings.empty or "rule_id" not in findings.columns:
            return
        current = self._rule_filter.currentData()
        counts = self.state.cached(
            "review_rule_counts",
            lambda: findings["rule_id"].value_counts(), findings)
        self._rule_filter.blockSignals(True)
        self._rule_filter.clear()
        self._rule_filter.addItem(tr("errors.filter_all"), "")
        for rule_id, count in counts.items():
            label = rule_name(str(rule_id), T.language)
            self._rule_filter.addItem(
                f"{label}  ({number(int(count))})", str(rule_id))
        index = self._rule_filter.findData(current)
        self._rule_filter.setCurrentIndex(index if index >= 0 else 0)
        self._rule_filter.blockSignals(False)

    def _arrow(self, frame: pd.DataFrame, current: str, suggested: str) -> pd.Series:
        """The column “as it is now → as it would be”, empty where there is no proposal.

        It is the central request of the revision: the proposal is not accepted blindly,
        it is looked at beside the value that it replaces.
        """
        if suggested not in frame.columns:
            return _blank(frame)
        proposed = _text(frame[suggested])
        now = _text(frame[current]) if current in frame.columns else _blank(frame)
        shown = now.where(now.ne(""), "—") + ARROW + proposed
        return shown.where(proposed.ne("") & proposed.ne(now), "")

    def _filter_cases(self) -> None:
        findings = self.state.findings
        if findings is None or findings.empty:
            return
        from ..i18n import T as _lang

        key = (id(findings), self._rule_filter.currentData(),
               self._only_proposals.isChecked(), self._only_undecided.isChecked(),
               self._manual_stamp(), _lang.language)
        if self._cases_key == key:
            self._cases_table.set_dataframe(self._cases_view)
            self._cases_table.select_first()
            return

        subset = findings
        chosen = self._rule_filter.currentData()
        if chosen and "rule_id" in subset.columns:
            subset = subset[subset["rule_id"].astype(str) == str(chosen)]

        keys = _key_series(subset)
        manual = self._load_manual()
        decisions: dict[str, str] = {}
        if not manual.empty:
            status = (_text(manual["status"]) if "status" in manual.columns
                      else _blank(manual))
            status = status.where(status.ne(""), "accettata")
            decisions = dict(zip(_key_series(manual), status))

        postag = self._arrow(subset, "postag", "suggested_postag")
        lemma = self._arrow(subset, "lemma", "suggested_lemma")
        relation = self._arrow(subset, "relation", "suggested_relation")
        proposed = postag.ne("") | lemma.ne("") | relation.ne("")
        decided = keys.map(decisions).fillna("")

        if self._only_proposals.isChecked():
            subset, postag, lemma, relation, decided, keys = (
                subset[proposed], postag[proposed], lemma[proposed],
                relation[proposed], decided[proposed], keys[proposed])
        if self._only_undecided.isChecked():
            undecided = decided.eq("")
            subset, postag, lemma, relation, decided, keys = (
                subset[undecided], postag[undecided], lemma[undecided],
                relation[undecided], decided[undecided], keys[undecided])

        view = pd.DataFrame(index=subset.index)
        view["forma"] = (_text(subset["form"]) if "form" in subset.columns
                         else _blank(subset))
        if "rule_id" in subset.columns:
            from greek_corpus_pipeline.rule_catalog import rule_name
            view["anomalia"] = subset["rule_id"].astype(str).map(
                lambda rid: rule_name(rid, _lang.language))
        # “What does not fit” is already on the previous page, beside the sentence:
        # repeating it here would widen the table without adding anything.
        view["etichetta_proposta"] = postag
        view["lemma_proposto"] = lemma
        view["relazione_proposta"] = relation
        view["decisione"] = decided.map(
            lambda state: value_label(state) if state else "")
        for column in ("document_id", "sentence_id", "token_id", "rule_id"):
            if column in subset.columns:
                view[column] = subset[column]

        # The selected case must be found again in full — present values and proposed
        # values — and the row that the table hands over carries only what is read: the
        # original finding stays here, indexed.
        self._cases = subset.set_index(keys)
        self._cases_key = key
        self._cases_view = view.reset_index(drop=True)
        self._cases_table.set_dataframe(self._cases_view)
        self._cases_empty.setVisible(self._cases_view.empty)
        self._cases_table.select_first()
        self._cases_count.setText(tr(
            "review.cases.count", number(len(self._cases_view)),
            number(int(decided.ne('').sum()))))

    def _raw_case(self, row) -> pd.Series | None:
        """The whole finding behind the selected row."""
        if row is None or self._cases is None or self._cases.empty:
            return None
        key = _key_of(row)
        if key not in self._cases.index:
            return None
        found = self._cases.loc[key]
        if isinstance(found, pd.DataFrame):
            rule = str(row.get("rule_id", ""))
            same = found[found["rule_id"].astype(str) == rule] \
                if "rule_id" in found.columns and rule else found
            found = (same if not same.empty else found).iloc[0]
        return found

    def _select_case(self, row) -> None:
        from greek_corpus_pipeline.agdt_schema import describe_postag, describe_relation
        from ..i18n import T

        raw = self._raw_case(row)
        self._current_row = raw
        for field in (self._new_lemma, self._new_postag, self._new_relation):
            field.clear()
        self._save_status.clear()
        self._save.setEnabled(raw is not None)
        self._reject.setEnabled(raw is not None)
        if raw is None:
            self._sentence.setText(tr("errors.select_row"))
            self._current.setText("")
            self._proposal.setText("")
            self._accept.setEnabled(False)
            return

        self._editor_area.verticalScrollBar().setValue(0)
        self._sentence.setText(_sentence_with_marker(raw, self.state.tokens))
        self._current.setText(
            f"<b>{raw.get('form', '')}</b> · lemma <i>{raw.get('lemma', '')}</i><br>"
            f"<span style='font-family:monospace'>{raw.get('postag', '')}</span> — "
            f"{describe_postag(raw.get('postag'), T.language)}<br>"
            f"{raw.get('relation', '')} — "
            f"{describe_relation(raw.get('relation'), T.language)}")

        proposal = self._proposal_lines(raw)
        self._proposal.setText(
            "<br>".join(proposal) if proposal
            else f"<i>{tr('review.proposal.none')}</i>")
        self._accept.setEnabled(bool(proposal))

        existing = self._existing_correction(raw)
        if existing is not None:
            self._new_lemma.setText(str(existing.get("corrected_lemma", "") or ""))
            self._new_postag.setText(str(existing.get("corrected_postag", "") or ""))
            self._new_relation.setText(str(existing.get("corrected_relation", "") or ""))
            state = str(existing.get("status", "") or "accettata")
            when = str(existing.get("decided_at", "") or "")
            note = tr("review.already_corrected") + "  " + value_label(state)
            if when:
                note += "  ·  " + tr("review.decided", when)
            self._save_status.setText(note)

    def _suggestions(self, row) -> list[tuple[str, str, str, str]]:
        """What the program proposes, for this case and for no other.

        One quadruple per level: which field, what it is called, what is written now,
        what would be proposed. A proposed value equal to what is already there is not a
        proposal and does not appear.
        """
        found = []
        for field, label_key, suggested_key in (
                ("postag", "errors.suggest.postag", "suggested_postag"),
                ("lemma", "errors.suggest.lemma", "suggested_lemma"),
                ("relation", "errors.suggest.relation", "suggested_relation")):
            proposed = _one(row.get(suggested_key))
            now = _one(row.get(field))
            if not proposed or proposed == now:
                continue
            found.append((field, tr(label_key), now, proposed))
        return found

    def _proposal_lines(self, row) -> list[str]:
        lines = []
        for _field, label, now, proposed in self._suggestions(row):
            lines.append(
                f"{label}: <span style='font-family:monospace'>{now or '—'}</span>"
                f" &nbsp;→&nbsp; <b style='font-family:monospace'>{proposed}</b>")
        return lines

    def _existing_correction(self, row) -> dict | None:
        manual = self._load_manual()
        if manual.empty:
            return None
        match = manual[_key_series(manual).eq(_key_of(row))]
        return match.iloc[-1].to_dict() if not match.empty else None

    # ── The decisions, one at a time ───────────────────────────────────
    def _record_decision(self, *, lemma: str, postag: str, relation: str,
                         status: str, note: str) -> None:
        row = self._current_row
        if row is None or self._manual_path() is None:
            return
        from greek_corpus_pipeline.gold import ensure_manual_columns, manual_record

        record = manual_record(
            dict(row), lemma=lemma, postag=postag, relation=relation,
            decided_by=self._decided_by.text().strip(),
            reason=self._reason.text().strip(), status=status)
        existing = ensure_manual_columns(self._load_manual())
        if not existing.empty:
            existing = existing[_key_series(existing).ne(_key_of(row))]
            record = pd.concat([existing, record], ignore_index=True)
        self._write_manual(record)
        self._show_decisions(record)
        self._update_apply_summary(record)
        self._reason.clear()
        self.logMessage.emit(tr(
            "review.log_saved", row.get("form"),
            lemma or postag or relation or value_label(status)))
        # First move on to the next case, then write the outcome: the reverse order
        # would write the confirmation and delete it at once, because changing row
        # clears the panel.
        self._advance()
        self._save_status.setText(note + "  " + tr("review.saved_count", len(record)))

    def _accept_proposal(self) -> None:
        row = self._current_row
        if row is None:
            return
        values = {"postag": "", "lemma": "", "relation": ""}
        for field, _label, _now, proposed in self._suggestions(row):
            values[field] = proposed
        if not any(values.values()):
            self._save_status.setText(tr("review.no_proposal_to_accept"))
            return
        self._record_decision(lemma=values["lemma"], postag=values["postag"],
                              relation=values["relation"], status="accettata",
                              note=tr("review.accepted"))

    def _reject_proposal(self) -> None:
        if self._current_row is None:
            return
        self._record_decision(lemma="", postag="", relation="",
                              status=REJECTED, note=tr("review.rejected"))

    def _save_correction(self) -> None:
        row = self._current_row
        if row is None:
            return
        lemma = self._new_lemma.text().strip()
        postag = self._new_postag.text().strip()
        relation = self._new_relation.text().strip()
        if not (lemma or postag or relation):
            self._save_status.setText(tr("review.nothing_written"))
            return
        # A label written by hand must have nine characters. A proposal of the program
        # need not: if a rule proposes a longer label, refusing to save it would mean
        # not being able to accept it at all.
        proposed = {value for _field, _label, _now, value in self._suggestions(row)}
        if postag and len(postag) != 9 and postag not in proposed:
            self._save_status.setText(tr("review.postag_length"))
            return
        self._record_decision(lemma=lemma, postag=postag, relation=relation,
                              status="accettata", note=tr("review.saved"))

    def _advance(self) -> None:
        """Rebuilds the list and stays where it was, that is on the next case.

        With “only those not yet decided” switched on, the case just decided disappears
        and at the same position there is the next one: one decides in a row without
        touching the mouse.
        """
        position = 0
        try:
            indexes = self._cases_table._view.selectionModel().selectedRows()
            position = indexes[0].row() if indexes else 0
        except Exception:                              # noqa: BLE001
            position = 0
        self._cases_key = None
        self._filter_cases()
        rows = len(self._cases_view)
        if not rows:
            return
        try:
            self._cases_table._view.selectRow(min(position, rows - 1))
        except Exception:                              # noqa: BLE001
            self._cases_table.select_first()

    def _remove_correction(self) -> None:
        row = self._decisions_table.selected_row()
        path = self._manual_path()
        if row is None or path is None or not path.exists():
            return
        manual = self._load_manual()
        manual = manual[_key_series(manual).ne(_key_of(row))]
        self._write_manual(manual)
        self._show_decisions(manual)
        self._update_apply_summary(manual)
        self._cases_key = None
        self._filter_cases()

    def _show_decisions(self, manual: pd.DataFrame) -> None:
        """The register as it is read: before and after, who, when, why."""
        if manual is None or manual.empty:
            self._decisions_table.set_dataframe(pd.DataFrame())
            self._decisions_empty.setVisible(True)
            return
        self._decisions_empty.setVisible(False)
        view = pd.DataFrame(index=manual.index)
        view["forma"] = _text(manual.get("form", _blank(manual)))
        status = _text(manual.get("status", _blank(manual)))
        view["stato"] = status.where(status.ne(""), "accettata").map(value_label)
        for target, source in (
                ("lemma vecchio", "previous_lemma"), ("lemma nuovo", "corrected_lemma"),
                ("etichetta vecchia", "previous_postag"),
                ("etichetta nuova", "corrected_postag"),
                ("relazione vecchia", "previous_relation"),
                ("relazione nuova", "corrected_relation"),
                ("chi", "decided_by"), ("quando", "decided_at"), ("perché", "reason")):
            if source in manual.columns:
                view[target] = _text(manual[source])
        for column in ("document_id", "sentence_id", "token_id", "rule_id"):
            if column in manual.columns:
                view[column] = manual[column]
        self._decisions_table.set_dataframe(view.reset_index(drop=True))

    # ── The dictionary of forms ────────────────────────────────────────
    def _choose_dictionary(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("review.dict.file"), "", "CSV (*.csv);;*")
        if not path:
            return
        from greek_corpus_pipeline.corrections import read_form_dictionary
        try:
            entries, report = read_form_dictionary(path)
        except Exception as error:                     # noqa: BLE001
            self._dictionary_path = ""
            self._dictionary_entries = pd.DataFrame()
            self._dict_path.clear()
            self._dict_preview.set_dataframe(pd.DataFrame())
            self._dict_report.setText(tr("review.dict.error", error))
            self.logMessage.emit(tr("review.dict.error", error))
            self._update_apply_summary(self._load_manual())
            return
        self._dictionary_path = path
        self._dictionary_entries = entries
        self._dict_path.setText(path)
        self._dict_preview.set_dataframe(entries)
        self._describe_dictionary(report)
        self._update_apply_summary(self._load_manual())
        self.logMessage.emit(tr(
            "review.dict.read", report.entries, report.with_lemma,
            report.with_postag))

    def _clear_dictionary(self) -> None:
        self._dictionary_path = ""
        self._dictionary_entries = pd.DataFrame()
        self._coverage_key = None
        self._coverage = None
        self._dict_path.clear()
        self._dict_preview.set_dataframe(pd.DataFrame())
        self._describe_dictionary()
        self._update_apply_summary(self._load_manual())

    def _describe_dictionary(self, report=None) -> None:
        """What this file will do, said before it is applied.

        The count of the entries is read at once; how many of them really touch the
        corpus is a comparison with hundreds of thousands of words and has to be
        computed elsewhere, otherwise the window stays still for two seconds as soon as
        the file has been chosen.
        """
        if self._dictionary_entries is None or self._dictionary_entries.empty:
            self._dict_report.setText(tr("review.dict.none"))
            return
        from greek_corpus_pipeline.corrections import LEMMA_COLUMN, POSTAG_COLUMN

        entries = self._dictionary_entries
        if report is None:
            text = tr("review.dict.read", len(entries),
                      int(entries[LEMMA_COLUMN].ne("").sum()),
                      int(entries[POSTAG_COLUMN].ne("").sum()))
        else:
            text = tr("review.dict.read", report.entries, report.with_lemma,
                      report.with_postag)
            if report.skipped_rows:
                text += tr("review.dict.skipped", report.skipped_rows)
            if report.duplicate_forms:
                text += tr("review.dict.duplicates", report.duplicate_forms)
        self._dict_report.setText(text)
        if not self.state.has_corpus:
            return

        signature = (id(self.state.tokens), len(self.state.tokens),
                     id(entries), len(entries))
        if self._coverage_key == signature and self._coverage is not None:
            self._dict_report.setText(text + "\n" + self._coverage_line())
            return

        tokens = self.state.tokens

        def compute():
            from greek_corpus_pipeline.corrections import dictionary_coverage
            return dictionary_coverage(tokens, entries)

        def show(coverage) -> None:
            self._coverage_key = signature
            self._coverage = coverage
            self._dict_report.setText(text + "\n" + self._coverage_line())

        # Below the threshold the count is immediate and is done at once: a result that
        # arrives from another thread is discarded if in the meantime the page is no
        # longer in view, and on a small corpus there is no reason to risk not seeing it
        # at all.
        if len(tokens) <= SMALL_CORPUS:
            show(compute())
        else:
            self.compute_in_background("review-dictionary-coverage", compute, show)

    def _coverage_line(self) -> str:
        """How much the dictionary touches the corpus, in the current language.

        The count is kept as it is — an object, not a sentence — so that a change of
        language rewrites it without having to recompute it.
        """
        coverage = self._coverage
        if coverage is None:
            return ""
        return tr("review.dict.coverage", coverage.matched_entries,
                  coverage.unmatched_entries, coverage.tokens_matched,
                  coverage.tokens_lemma_changed, coverage.tokens_postag_changed)

    def _save_template(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, tr("review.dict.template"), "dizionario_di_forme.csv", "CSV (*.csv)")
        if not path:
            return
        from greek_corpus_pipeline.corrections import write_form_dictionary_template
        written = write_form_dictionary_template(path)
        self._dict_report.setText(tr("review.dict.template.saved", written))
        self.logMessage.emit(tr("review.dict.template.saved", written))

    def _save_my_dictionary(self) -> None:
        """The accepted decisions, in the same format that this page reads."""
        manual = self._accepted_decisions()
        if manual is None or manual.empty:
            QMessageBox.information(self, tr("review.dict.title"),
                                    tr("review.dict.nothing_to_save"))
            return
        from greek_corpus_pipeline.corrections import (
            DICTIONARY_COLUMNS, write_form_dictionary,
        )
        rows, ambiguous = [], 0
        for form, chunk in manual.groupby("form", sort=True):
            lemmas = sorted({v for v in _text(chunk["corrected_lemma"]) if v})
            tags = sorted({v for v in _text(chunk["corrected_postag"]) if v})
            if len(lemmas) > 1 or len(tags) > 1:
                # A dictionary assigns one value per form: a form corrected in two
                # different ways does not fit, and that must be said instead of choosing
                # at random.
                ambiguous += 1
                continue
            if not lemmas and not tags:
                continue
            rows.append({"form": form, "postag": tags[0] if tags else "",
                         "lemma": lemmas[0] if lemmas else ""})
        if not rows:
            QMessageBox.information(self, tr("review.dict.title"),
                                    tr("review.dict.nothing_to_save"))
            return
        path, _ = QFileDialog.getSaveFileName(
            self, tr("review.dict.save_mine"), "dizionario_mio.csv", "CSV (*.csv)")
        if not path:
            return
        written = write_form_dictionary(
            pd.DataFrame(rows, columns=list(DICTIONARY_COLUMNS)), path)
        message = tr("review.dict.saved_mine", len(rows), written)
        if ambiguous:
            message += tr("review.dict.ambiguous", ambiguous)
        self._dict_report.setText(message)
        self.logMessage.emit(message)

    # ── Applying the corrections ───────────────────────────────────────
    def _update_apply_summary(self, manual: pd.DataFrame | None = None) -> None:
        if manual is None:
            manual = self._load_manual()
        if manual is None or manual.empty:
            accepted = 0
        elif "status" in manual.columns:
            accepted = int(_text(manual["status"]).ne(REJECTED).sum())
        else:
            accepted = int(len(manual))
        entries = 0 if self._dictionary_entries is None \
            else int(len(self._dictionary_entries))
        if not accepted and not entries:
            self._apply_summary.setText(tr("review.apply.nothing"))
        else:
            self._apply_summary.setText(
                tr("review.apply.summary", accepted, entries))
        self._apply.setEnabled(bool(accepted or entries))

    def _apply_now(self) -> None:
        """Writes the decisions taken into the corrected corpus, and nothing else.

        No rule is applied by itself: the set of automatic rules passed to the engine is
        empty, and stays empty. What enters the corpus is only what the user has
        accepted case by case and the dictionary that the user has loaded.
        """
        if not self.state.run_id:
            return
        accepted = self._accepted_decisions()
        entries = (self._dictionary_entries if self._dictionary_entries is not None
                   else pd.DataFrame())
        if (accepted is None or accepted.empty) and entries.empty:
            QMessageBox.information(self, tr("review.apply.title"),
                                    tr("review.apply.nothing"))
            return
        self.run_work(
            apply_corrections, self.state.workspace, self.state.run_id,
            set(), accepted, entries, self.state.filter_options,
            False, False, label=tr("review.apply"), export_conllu_flag=False)
