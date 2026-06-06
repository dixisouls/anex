"""Weave bootstrap: init once per process unless WEAVE_DISABLED=1."""

import weave

from backend.config import WEAVE_DISABLED, WEAVE_PROJECT

_inited = False


def init_weave() -> None:
    global _inited
    if _inited or WEAVE_DISABLED:
        return
    weave.init(WEAVE_PROJECT)
    _inited = True
