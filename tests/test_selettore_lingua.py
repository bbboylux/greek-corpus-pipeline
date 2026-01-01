# -*- coding: utf-8 -*-
"""The language menu must show the language that the interface is written in, from the moment the window opens.

The program starts in English (the language of the translator when nobody has chosen another), and the menu lists
Italian first. If the menu showed its first entry whatever the language, a person who sees "Italiano" and chooses
"Italiano" would obtain nothing, because choosing the entry that is already selected sends no signal: the first
gesture would be lost and the window would look broken. Here the real window is opened in each language, the menu is
read, and the language is changed with the menu in both directions.
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
from PyQt6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def application():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def opens(application, tmp_path):
    """A function that opens the real window with the translator set to a language, and closes it afterwards."""
    from gui_qt.i18n import T
    from gui_qt.main_window import MainWindow
    windows = []

    def open_window(language: str):
        T.set_language(language)
        workspace = tmp_path / f"workspace-{len(windows)}"
        workspace.mkdir()
        window = MainWindow(workspace)
        windows.append(window)
        return window

    yield open_window
    for window in windows:
        window.close()
    T.set_language("it")


def choose(window, code: str) -> None:
    """The gesture of the person: the entry of the menu that carries this language code."""
    menu = window._language
    index = menu.findData(code)
    assert index >= 0, f"{code} is not in the language menu"
    menu.setCurrentIndex(index)


def shown(window) -> str:
    return window._subtitle.text()


@pytest.mark.parametrize("language, name", [("en", "English"), ("it", "Italiano")])
def test_the_menu_shows_the_language_in_which_the_window_opens(opens, language, name):
    from gui_qt.i18n import LANGUAGES, T
    window = opens(language)
    assert T.language == language
    assert window._language.currentData() == language
    assert window._language.currentText() == name == LANGUAGES[language]


def test_the_application_opens_in_english_and_the_menu_says_so(opens):
    """What a person sees at the start of the real program: the translator's own default."""
    from gui_qt.i18n import Translator
    default = Translator().language
    window = opens(default)
    assert default == "en"
    assert window._language.currentText() == "English"
    assert shown(window).startswith("Analysis and quality control")


def test_the_first_choice_in_the_menu_changes_the_language_in_both_directions(opens):
    from gui_qt.i18n import T
    window = opens("en")
    # the person opens the menu, sees "English" selected, and chooses "Italiano": one gesture is enough
    choose(window, "it")
    assert T.language == "it" and shown(window).startswith("Analisi e controllo")
    assert window._language.currentText() == "Italiano"
    choose(window, "en")
    assert T.language == "en" and shown(window).startswith("Analysis and quality control")
    choose(window, "it")
    assert T.language == "it" and shown(window).startswith("Analisi e controllo")


def test_choosing_again_the_entry_that_is_on_display_changes_nothing(opens):
    from gui_qt.i18n import T
    window = opens("it")
    choose(window, "it")
    assert T.language == "it" and shown(window).startswith("Analisi e controllo")
    window = opens("en")
    choose(window, "en")
    assert T.language == "en" and shown(window).startswith("Analysis and quality control")


def test_the_initial_selection_does_not_run_the_change_of_language(opens, monkeypatch):
    """Showing the language in the menu is not a change of language: it must not retranslate the pages."""
    from gui_qt import main_window
    calls = []
    original = main_window.MainWindow._change_language
    monkeypatch.setattr(main_window.MainWindow, "_change_language",
                        lambda self: calls.append(1) or original(self))
    opens("it")
    opens("en")
    assert calls == []
