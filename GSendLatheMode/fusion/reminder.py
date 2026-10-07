"""The once-a-month "see the full G-SEND.IO" page.

Lite-only module, like upgrade.py: nothing here exists in the full add-in.

On add-in start, lib/upgrade_reminder.py decides whether a visit is due
(first run records the install date and opens nothing; then at most once
every 30 days). When it is, the user's default browser opens on
UPGRADE_URL - no dialog first (Shane, 10/6/26: "every 30 days it opens
up their default internet browser and sends them to the website").

The page opens a few seconds AFTER startup rather than during it: Fusion
is still building its own UI while run-on-startup add-ins load, and the
browser stealing focus from a half-drawn Fusion is the worst moment to do
it. The delay is a background timer that fires a Fusion custom event, and
the custom event's handler runs on Fusion's main thread, which is the
only thread the API may be called from.
"""

import threading
import traceback
import webbrowser

import adsk.core

from ..lib import upgrade_reminder
from .upgrade import UPGRADE_URL

CUSTOM_EVENT_ID = "gsendlite_upgrade_reminder"

#: Seconds after the add-in starts before the page opens.
DELAY_SECONDS = 20

_custom_event = None
_event_handler = None
_timer = None
_handlers = []


def _log(message):
    try:
        adsk.core.Application.get().log("GSendLatheMode reminder: %s" % message)
    except Exception:
        pass


def _open_page():
    """Open the page in the default browser. The state was recorded before
    the timer was armed, so whatever happens here cannot re-arm it for
    tomorrow."""
    if not webbrowser.open(UPGRADE_URL):
        _log("the browser did not open %s" % UPGRADE_URL)


class _ReminderHandler(adsk.core.CustomEventHandler):
    def notify(self, args):
        try:
            _open_page()
        except Exception:
            _log("opening the page failed\n" + traceback.format_exc())


def start(app, ui):
    """Decide, and if a visit is due, arm the delayed browser open. Called
    from the entry, guarded there."""
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
