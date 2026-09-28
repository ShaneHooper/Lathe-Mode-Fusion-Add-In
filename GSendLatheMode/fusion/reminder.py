"""The once-a-month "upgrade to G-SEND.IO" prompt.

Lite-only module, like upgrade.py: nothing here exists in the full add-in.

On add-in start, lib/upgrade_reminder.py decides whether a prompt is due
(first run records the install date and shows nothing; then at most once
every 30 days). When it is, the dialog opens a few seconds AFTER startup
rather than during it: Fusion is still building its own UI while
run-on-startup add-ins load, and a modal thrown into that is the kind of
thing that gets an add-in disabled. The delay is a background timer that
fires a Fusion custom event, and the custom event's handler runs on
Fusion's main thread, which is the only thread the API may be called from.

The dialog is a plain Yes/No message box. Yes opens the same page the
Upgrade button opens; No closes it, and nothing asks again for a month.
"""

import threading
import traceback
import webbrowser

import adsk.core

from ..lib import upgrade_reminder
from .upgrade import UPGRADE_URL

CUSTOM_EVENT_ID = "gsendlite_upgrade_reminder"

#: Seconds after the add-in starts before the prompt opens.
DELAY_SECONDS = 20

TITLE = "G-SEND Lathe Mode"
MESSAGE = (
    "Thanks for using G-SEND Lathe Mode.\n\n"
    "The full G-SEND.IO adds the G-code editor, one-button lathe setup "
    "creation from your model, CAM templates, speeds and feeds, lathe and "
    "mill simulators, and machine send/receive.\n\n"
    "Open g-send.io to see what it does?")

_custom_event = None
_event_handler = None
_timer = None
_handlers = []


def _log(message):
    try:
        adsk.core.Application.get().log("GSendLatheMode reminder: %s" % message)
    except Exception:
        pass


def _show(ui):
    """The dialog itself. The state was recorded before the timer was
    armed, so whatever happens here cannot re-arm it for tomorrow."""
    result = ui.messageBox(
        MESSAGE, TITLE,
        adsk.core.MessageBoxButtonTypes.YesNoButtonType,
        adsk.core.MessageBoxIconTypes.QuestionIconType)
    if result == adsk.core.DialogResults.DialogYes:
        webbrowser.open(UPGRADE_URL)


class _ReminderHandler(adsk.core.CustomEventHandler):
    def notify(self, args):
        try:
            _show(adsk.core.Application.get().userInterface)
        except Exception:
            _log("prompt failed\n" + traceback.format_exc())


def start(app, ui):
    """Decide, and if a prompt is due, arm the delayed dialog. Called from
    the entry, guarded there."""
    global _custom_event, _event_handler, _timer
    action = upgrade_reminder.decide_and_record(upgrade_reminder.state_path())
    _log("reminder check: %s" % action)
    if action != upgrade_reminder.SHOW:
        return
    try:
        app.unregisterCustomEvent(CUSTOM_EVENT_ID)
    except Exception:
        pass
    _custom_event = app.registerCustomEvent(CUSTOM_EVENT_ID)
    _event_handler = _ReminderHandler()
    _custom_event.add(_event_handler)
    _handlers.append(_event_handler)

    def fire():
        try:
            app.fireCustomEvent(CUSTOM_EVENT_ID)
        except Exception:
            _log("could not fire the reminder event\n" + traceback.format_exc())

    _timer = threading.Timer(DELAY_SECONDS, fire)
    _timer.daemon = True
    _timer.start()


def uninstall(app):
    global _custom_event, _event_handler, _timer
    try:
        if _timer is not None:
            _timer.cancel()
    except Exception:
        pass
    _timer = None
    try:
        if _custom_event is not None and _event_handler is not None:
            _custom_event.remove(_event_handler)
    except Exception:
        pass
    try:
        app.unregisterCustomEvent(CUSTOM_EVENT_ID)
    except Exception:
        pass
    _custom_event = None
    _event_handler = None
