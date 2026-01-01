# -*- coding: utf-8 -*-
"""A rebuilt widget must not leave the previous version lying around.

The defect is invisible to a test that reads the strings: the old labels still
exist, are children of the same widget and answer to ``text()``.  It is seen
only on a screen, where they end up drawn one over the other and nothing can
be read any more.  The case in point is a change of language on the page of
the revised corpus.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
for candidate in (ROOT, ROOT / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtWidgets import QApplication, QLabel  # noqa: E402


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


def _etichette_visibili(radice) -> list[str]:
    """The labels that would be drawn if the root were on screen.

    ``isHidden()`` is not enough: it hides only the widget on which it was called, and
    the children of a hidden widget keep saying that they are not hidden.
    ``isVisibleTo`` looks at the whole chain of parents, which is what the Qt painter
    does too.
    """
    return [q.text() for q in radice.findChildren(QLabel) if q.isVisibleTo(radice)]


def test_la_griglia_dei_numeri_non_sovrappone_due_lingue(application):
    from gui_qt.widgets import MetricGrid

    griglia = MetricGrid()
    from gui_qt.i18n import tr
    griglia.set_metrics({tr("gold.metric.tokens"): 10, tr("gold.metric.changed"): 2})
    prima = _etichette_visibili(griglia)
    griglia.set_metrics({tr("gold.metric.manual"): 3})
    dopo = _etichette_visibili(griglia)

    assert len(dopo) == 2, f"old cards are still visible: {dopo}"  # value + name
    assert not set(dopo) & set(prima), \
        "a card from the previous version is still drawn"
    griglia.deleteLater()
    application.processEvents()


def test_l_elenco_chiave_valore_non_sovrappone_due_lingue(application):
    from gui_qt.widgets import KeyValueList

    elenco = KeyValueList()
    from gui_qt.i18n import tr
    elenco.set_items({tr("variation.plane.morfologia"): 5,
                      tr("variation.plane.contesto"): 7})
    prima = _etichette_visibili(elenco)
    elenco.set_items({tr("variation.plane.lemmi"): 1})
    dopo = _etichette_visibili(elenco)

    assert len(dopo) == 2, f"old rows are still visible: {dopo}"
    assert not set(dopo) & set(prima), \
        "a row from the previous version is still drawn"
    elenco.deleteLater()
    application.processEvents()


def test_le_schede_dei_numeri_si_ricostruiscono_al_cambio_di_lingua(application):
    """The real case: same key, two languages, one card per key."""
    from gui_qt.i18n import T
    from gui_qt.widgets import MetricGrid

    lingua = T.language
    try:
        griglia = MetricGrid()
        from gui_qt.i18n import tr
        T.language = "it"
        griglia.set_metrics({tr("gold.metric.tokens"): 16191})
        italiane = _etichette_visibili(griglia)
        T.language = "en"
        griglia.set_metrics({tr("gold.metric.tokens"): 16191})
        inglesi = _etichette_visibili(griglia)
    finally:
        T.language = lingua

    assert "Record importati" in italiane
    assert "Imported records" in inglesi
    assert "Record importati" not in inglesi, \
        "the Italian label stayed under the English one"
    assert "16.191" in italiane and "16,191" in inglesi, \
        "the number does not follow the language"
    griglia.deleteLater()
    application.processEvents()
