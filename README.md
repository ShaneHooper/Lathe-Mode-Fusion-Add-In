# G-SEND Lathe Mode - Fusion 360 add-in

**Draw lathe parts in diameters, the way the print reads.**

A free Fusion 360 add-in from [G-SEND.IO](https://g-send.io). Right-click a
sketch line in the Design workspace and choose **G-SEND.IO: Lathe Mode**.
That line becomes your spindle centerline, and from then on dimensions to it
are real diameter dimensions: type the print's number, the geometry lands at
half, and the dim shows the diameter symbol. Right-click any parallel wall
line for a one-click **Dimension to Centerline**.

No more doubling radii in your head, and no more right-clicking every single
dimension into a diameter by hand.

## Install

1. Close Fusion 360.
2. Copy the `GSendLatheMode` folder from this repository into:

   ```
   %APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns
   ```

   (Paste that line into the File Explorer address bar and press Enter to
   jump straight there.)
3. Start Fusion 360. The add-in loads automatically. If it does not, open
   UTILITIES > ADD-INS > Scripts and Add-Ins, select GSendLatheMode on the
   Add-Ins tab, tick "Run on Startup" and click Run.

Or grab the installer from the [latest release](../../releases/latest)
when one is published: run `GSendLatheMode-Setup.exe`, click Install, start
Fusion 360.

## Using it

1. In a sketch (Design workspace), draw your centerline.
2. **Right-click it > G-SEND.IO: Lathe Mode.** It becomes a construction
   line, and any dimensions you had already placed to it convert to diameter
   dims without moving your geometry.
3. Dimension any line parallel to the centerline. The number you type is the
   **diameter**.
4. Or **right-click a parallel line > G-SEND.IO: Dimension to Centerline**
   for the one-click version.
5. Right-click the centerline again to turn the mode off.

The mode never appears in the Manufacture workspace, and sketches you mark
keep working if you later upgrade to the full G-SEND.IO.

## The monthly reminder

Once a month, about twenty seconds after Fusion starts, the add-in asks
whether you want to see what the full G-SEND.IO adds. Yes opens
[g-send.io](https://g-send.io); No closes it and nothing asks again for
another 30 days. A fresh install is not asked until it has been in use
for a month.

The date of the last prompt lives in one small file,
`%APPDATA%\G-SEND.IO\lathe_mode_reminder.json`. Delete it to start the
clock over.

## Uninstall

Close Fusion 360 and delete
`%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\GSendLatheMode`.
The only other thing the add-in writes is the reminder file above.

## Layout

```
GSendLatheMode/
  GSendLatheMode.manifest      Fusion add-in manifest (id, version)
  GSendLatheMode.py            entry point: run() / stop()
  fusion/lathe_sketch_mode.py  the Lathe Mode commands and sketch handling
  fusion/upgrade.py            the Upgrade to G-SEND.IO button and menu row
  fusion/reminder.py           the once-a-month upgrade prompt
  lib/lathe_sketch.py          pure geometry helpers (no Fusion imports)
  lib/upgrade_reminder.py      when the monthly prompt is due (no Fusion imports)
  resources/gsendio/           the G-SEND icon at 16, 32 and 64 px
  README.txt                   the install notes shipped inside the folder
```

Lathe Mode is the same code that ships inside the full G-SEND.IO add-in.
The two share command ids on purpose, so a sketch marked in the free add-in
keeps working after an upgrade, and if the full G-SEND.IO add-in is running
this one notices and installs nothing.

## The full G-SEND.IO

Lathe Mode is the free taste. The full **G-SEND.IO** adds the G-code editor
and IDE, one-button lathe setup creation from your model, CAM templates,
speeds and feeds, simulators, and machine send/receive over RS-232.

**[g-send.io](https://g-send.io)**, or click **Upgrade to G-SEND.IO** right
inside the add-in.

## Tests

The Fusion-free parts have plain unittest coverage:

```
python -m unittest discover tests
```

## License

Apache 2.0. See [LICENSE](LICENSE).
