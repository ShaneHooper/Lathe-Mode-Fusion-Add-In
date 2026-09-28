"""The upgrade path from G-SEND Lathe Mode (free) to full G-SEND.IO.

Two surfaces, one command: a button in Utilities > Add-Ins, and a row in
the same sketch marking menu the Lathe Mode rows live in - the person
most likely to want the full product is the one already right-clicking
sketch lines. Executing either opens the purchase page in the browser.

Lite-only module: nothing here exists in the full add-in, and nothing
here touches the vendored Lathe Mode code.
"""

import os
import traceback
import webbrowser

import adsk.core

#: Where the Upgrade button sends people. One place to change when the
#: store page moves.
UPGRADE_URL = "https://g-send.io"

CMD_ID = "gsendlite_upgrade"
BUTTON_NAME = "Upgrade to G-SEND.IO"
TOOLTIP = ("G-SEND Lathe Mode is the free taste. The full G-SEND.IO adds "
           "the G-code editor, lathe setup creation, CAM templates, "
           "speeds and feeds, and machine send/receive.")

#: The Utilities > Add-Ins panel every add-in may place buttons in.
PANEL_ID = "SolidScriptsAddinsPanel"

RESOURCE_FOLDER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "resources", "gsendio")

_handlers = []
_menu_handler = None


def _log(message):
    try:
        adsk.core.Application.get().log("GSendLatheMode upgrade: %s" % message)
    except Exception:
        pass


class _CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            on_execute = _ExecuteHandler()
            args.command.execute.add(on_execute)
            _handlers.append(on_execute)
        except Exception:
            _log("command created failed\n" + traceback.format_exc())


class _ExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            webbrowser.open(UPGRADE_URL)
        except Exception:
            _log("could not open the upgrade page\n" + traceback.format_exc())


class _MarkingMenuHandler(adsk.core.MarkingMenuEventHandler):
    """Append the Upgrade row wherever the Lathe Mode rows appear: a
    sketch line right-clicked in Design. Fires alongside (after) the
    vendored handler; each handler only adds its own rows."""

    def notify(self, args):
        try:
            app = adsk.core.Application.get()
            ui = app.userInterface
            workspace = ui.activeWorkspace
            if not workspace or workspace.id != "FusionSolidEnvironment":
                return
            import adsk.fusion
            if adsk.fusion.Sketch.cast(app.activeEditObject) is None:
                return
            event_args = adsk.core.MarkingMenuEventArgs.cast(args)
            line = None
            for entity in event_args.selectedEntities or []:
                line = adsk.fusion.SketchLine.cast(entity)
                if line:
                    break
            if not line:
                return
            cmd_def = ui.commandDefinitions.itemById(CMD_ID)
            menu = event_args.linearMarkingMenu
            if cmd_def and menu and not menu.controls.itemById(CMD_ID):
                menu.controls.addCommand(cmd_def)
        except Exception:
            _log("marking menu failed\n" + traceback.format_exc())


def start(app, ui):
    """Wire the upgrade surfaces up. Called from the entry, guarded there."""
    global _menu_handler
    cmd_def = ui.commandDefinitions.itemById(CMD_ID)
    if not cmd_def:
        cmd_def = ui.commandDefinitions.addButtonDefinition(
            CMD_ID, BUTTON_NAME, TOOLTIP, RESOURCE_FOLDER)
    else:
        try:
            cmd_def.resourceFolder = RESOURCE_FOLDER
        except Exception:
            pass
    on_created = _CommandCreatedHandler()
    cmd_def.commandCreated.add(on_created)
    _handlers.append(on_created)

    try:
        panel = ui.allToolbarPanels.itemById(PANEL_ID)
        if panel and not panel.controls.itemById(CMD_ID):
            panel.controls.addCommand(cmd_def)
    except Exception:
        _log("toolbar button failed\n" + traceback.format_exc())

    _menu_handler = _MarkingMenuHandler()
    ui.markingMenuDisplaying.add(_menu_handler)
    _handlers.append(_menu_handler)


def uninstall(ui):
    global _menu_handler
    try:
        if _menu_handler is not None:
            ui.markingMenuDisplaying.remove(_menu_handler)
    except Exception:
        pass
    _menu_handler = None
    try:
        panel = ui.allToolbarPanels.itemById(PANEL_ID)
        control = panel.controls.itemById(CMD_ID) if panel else None
        if control:
            control.deleteMe()
    except Exception:
        pass
    try:
        cmd_def = ui.commandDefinitions.itemById(CMD_ID)
        if cmd_def:
            cmd_def.deleteMe()
    except Exception:
        pass
