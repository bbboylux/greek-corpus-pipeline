# -*- coding: utf-8 -*-
"""How many processors the program takes, and when it decides.

One place, and one reason for it to exist: the numerical libraries decide the
size of their thread pool **the first time they are imported**, reading the
environment. Setting ``OMP_NUM_THREADS`` after importing numpy has no
effect — measured, not deduced:

    >>> import numpy, os, threadpoolctl
    >>> threadpoolctl.threadpool_info()[0]["num_threads"]
    2
    >>> os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    >>> threadpoolctl.threadpool_info()[0]["num_threads"]
    2

Therefore :func:`limita_thread` must be called **before** any import of
numpy, pandas, torch or stanza, that is, in the first lines of ``app_qt.py``.

The policy is not "all processors minus one". On a laptop with eight logical
processors — four physical ones with SMT — seven computing threads per
library, multiplied by the number of libraries trying at the same time, keep
the machine at 100% and heat it up without the work finishing appreciably
sooner. A few minutes more and a usable machine are worth more than a few
minutes less and a frozen one.
"""
from __future__ import annotations

import os

#: The ceiling: no higher than this, however many processors there are.
TETTO = 4

#: The variables that the numerical libraries read at import time.
VARIABILI = (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
)


def thread_consigliati(processori: int | None = None) -> int:
    """How many computing threads per library, on this machine.

    Half of the logical processors, never more than :data:`TETTO`, never fewer than one.
    On 2 it gives 1, on 4 it gives 2, on 8 it gives 4, on 32 it gives 4.
    """
    n = processori if processori is not None else (os.cpu_count() or 2)
    return max(1, min(TETTO, n // 2))


def limita_thread(processori: int | None = None) -> int:
    """Write the environment variables, if they are not already set. Return the value.

    It respects an explicit choice by whoever uses the program: if the variable
    already exists in the environment it is not touched.
    """
    quanti = thread_consigliati(processori)
    for variabile in VARIABILI:
        os.environ.setdefault(variabile, str(quanti))
    return quanti


def limita_torch() -> int | None:
    """The limit inside torch as well, which has two pools and not just one.

    ``set_num_threads`` governs the threads within a single operation;
    ``set_num_interop_threads`` those between operations, and its default value is
    another half processor per processor. Without the second, limiting the first
    still lets the total grow.

    Return the number applied, or ``None`` if torch is not installed.
    """
    quanti = thread_consigliati()
    try:
        import torch                                   # noqa: PLC0415
    except Exception:                                  # noqa: BLE001
        return None
    try:
        torch.set_num_threads(quanti)
    except Exception:                                  # noqa: BLE001
        pass
    try:
        # It can be set only once, and only before the first parallel work: if it is
        # too late, torch raises and there is nothing to be done.
        torch.set_num_interop_threads(1)
    except Exception:                                  # noqa: BLE001
        pass
    return quanti
