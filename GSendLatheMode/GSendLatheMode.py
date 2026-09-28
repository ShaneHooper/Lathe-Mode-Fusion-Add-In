"""G-SEND Lathe Mode - the free, standalone taste of G-SEND.IO.

Just the Lathe Mode sketch tool from the full add-in (right-click a
sketch centerline in Design and dimensions to it become diameters, the
way a lathe print reads), plus an Upgrade button that opens the page to
buy the full G-SEND.IO.

The Lathe Mode code is vendored BYTE-FOR-BYTE from the full add-in
(lib/lathe_sketch.py and fusion/lathe_sketch_mode.py); a repo test pins
the copies identical, so improvements happen in the full add-in and get
re-copied here. That includes the command ids and the sketch attribute -
identical on purpose, so a sketch marked in the free add-in keeps
working seamlessly after an upgrade, and vice versa.

Because the ids are shared, both add-ins running at once would fight
over them. run() defers: if the full G-SEND.IO already registered the
Lathe Mode command, this add-in installs nothing and says so in the log.
"""

import traceback

try:
    import adsk.core
except Exception:  # pragma: no cover - only hit outside Fusion
    adsk = None

ADDIN_NAME = "G-SEND Lathe Mode"

#: The full add-in's Lathe Mode command id. Present at run() means the
#: full G-SEND.IO owns the feature on this machine - defer to it.
FULL_ADDIN_CMD_ID = "gsendio_lathe_mode"

_ui = None
_installed = False


def _log(message):
    try:
        adsk.core.Application.get().log("%s: %s" % (ADDIN_NAME, message))
    except Exception:
        pass


def run(_context):
    global _ui, _installed
    try:
        app = adsk.core.Application.get()
        _ui = app.userInterface

        if _ui.commandDefinitions.itemById(FULL_ADDIN_CMD_ID):
            _log("full G-SEND.IO is running - the free add-in defers to it "
                 "and installs nothing")
            return

        from .fusion import lathe_sketch_mode
        lathe_sketch_mode.start(app, _ui)

        from .fusion import upgrade
        upgrade.start(app, _ui)

        _installed = True
        _log("running (free add-in)")
    except Exception:
        _log("run failed\n" + traceback.format_exc())


def stop(_context):
    global _installed
    try:
        if not _installed or _ui is None:
            return
        try:
            from .fusion import lathe_sketch_mode
            lathe_sketch_mode.uninstall(_ui)
        except Exception:
            _log("lathe mode uninstall failed\n" + traceback.format_exc())
        try:
            from .fusion import upgrade
            upgrade.uninstall(_ui)
        except Exception:
            _log("upgrade uninstall failed\n" + traceback.format_exc())
        _installed = False
    except Exception:
        _log("stop failed\n" + traceback.format_exc())
