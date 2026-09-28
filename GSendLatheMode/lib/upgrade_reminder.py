"""When to show the once-a-month "upgrade to G-SEND.IO" prompt.

Pure Python: no Fusion imports, so it can be tested with plain unittest.
The Fusion half (fusion/reminder.py) asks :func:`next_action` on every
add-in start and does what it says.

The rules:

* The prompt shows at most once every :data:`INTERVAL` (30 days).
* A fresh install is NOT prompted. The first run records the install date
  and the first prompt comes one interval later - somebody who installed
  the add-in five minutes ago has not had a chance to like it yet.
* The timestamp is recorded BEFORE the dialog opens, so a crash or a
  killed Fusion mid-dialog cannot turn the monthly prompt into an every-
  launch prompt.
* A timestamp from the future (a clock that was set back) counts as due,
  so a bad clock cannot mute the prompt forever.

State is one small JSON file, ``lathe_mode_reminder.json``, in the
``G-SEND.IO`` folder under ``%APPDATA%`` - the same folder the full
product uses, a different file. Delete it to start the clock over; to see
the prompt right away, set ``installed_utc`` in it to a date more than 30
days back.
"""

import json
import os
from datetime import datetime, timedelta, timezone

#: How often the prompt may show.
INTERVAL = timedelta(days=30)

STATE_FOLDER = "G-SEND.IO"
STATE_BASENAME = "lathe_mode_reminder.json"

#: What :func:`next_action` can answer.
FIRST_RUN = "first_run"   # record the install date, show nothing
SHOW = "show"             # an interval has passed - prompt
WAIT = "wait"             # prompted recently - stay quiet


def state_path(appdata=None):
    """Where the state file lives. ``appdata`` overrides ``%APPDATA%``
    (for tests); with neither, the user's home folder."""
    base = appdata or os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, STATE_FOLDER, STATE_BASENAME)


def _parse(stamp):
    """An aware UTC datetime from an ISO string, or ``None`` for anything
    missing or malformed - a corrupt stamp reads as "never", which is the
    direction that costs one extra prompt rather than none forever."""
    try:
        parsed = datetime.fromisoformat(str(stamp))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def load_state(path):
    """``{"installed": datetime|None, "last_shown": datetime|None}``.
    A missing, unreadable or wrong-shaped file is an empty state."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except Exception:
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    return {
        "installed": _parse(raw.get("installed_utc")),
        "last_shown": _parse(raw.get("last_shown_utc")),
    }


def save_state(path, installed=None, last_shown=None):
    """Write the two stamps. Whole-file write to a sibling then rename, so
    a crash mid-write leaves the old file rather than half of a new one."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    payload = {
        "installed_utc": installed.isoformat() if installed else None,
        "last_shown_utc": last_shown.isoformat() if last_shown else None,
    }
    scratch = path + ".tmp"
    with open(scratch, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    os.replace(scratch, path)


def next_action(state, now, interval=INTERVAL):
    """:data:`FIRST_RUN`, :data:`SHOW` or :data:`WAIT` for this launch.

    The clock starts at the install stamp and restarts at every prompt;
    whichever is later is the anchor. No install stamp at all means this
    is the first run.
    """
    anchor = state.get("last_shown") or state.get("installed")
    if anchor is None:
        return FIRST_RUN
    if state.get("installed") and state.get("last_shown"):
        anchor = max(state["installed"], state["last_shown"])
    if anchor > now:
        return SHOW
    if now - anchor >= interval:
        return SHOW
    return WAIT


def decide_and_record(path, now=None, interval=INTERVAL):
    """The one call the Fusion half makes: read the state, decide, and
    record whatever this launch changes. Returns the action.

    * FIRST_RUN writes the install stamp.
    * SHOW writes the shown stamp - before the caller opens any dialog.
    * WAIT writes nothing.
    """
    now = now or datetime.now(timezone.utc)
    state = load_state(path)
    action = next_action(state, now, interval)
    if action == FIRST_RUN:
        save_state(path, installed=now, last_shown=None)
    elif action == SHOW:
        save_state(path, installed=state["installed"] or now, last_shown=now)
    return action
