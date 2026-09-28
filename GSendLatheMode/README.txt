G-SEND: LATHE MODE ADD-IN
=========================

Free lathe sketching tool for Autodesk Fusion 360, from G-SEND.IO.
Right-click a sketch centerline in the Design workspace and dimensions
to it become diameters, the way a lathe print reads.


HOW TO INSTALL
--------------

Option A - the installer (easiest):
  1. Close Fusion 360.
  2. Run GSendLatheMode-Setup.exe and click Install.
  3. Start Fusion 360. The tool loads automatically.

Option B - this zip, by hand:
  1. Close Fusion 360.
  2. Copy the whole GSendLatheMode folder (the folder this README is
     in) into:
       %APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns
     (Paste that line into the File Explorer address bar and press
     Enter to jump straight there.)
  3. Start Fusion 360. If it does not load automatically, open
     UTILITIES > ADD-INS > Scripts and Add-Ins, select GSendLatheMode
     on the Add-Ins tab, tick "Run on Startup" and click Run.


HOW TO USE
----------

In a sketch, right-click the line that is your spindle centerline and
choose "G-SEND.IO: Lathe Mode (Diameter Mode)". From then on,
dimensions to that line are real diameter dimensions: type the print's
number, the geometry lands at half, and the dim shows the diameter
symbol. Right-click the centerline again to turn it off.


HOW TO UNINSTALL
----------------

  1. Close Fusion 360.
  2. Delete this folder:
       %APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\GSendLatheMode
  3. The only other thing it writes is the once-a-month reminder's
     date, in %APPDATA%\G-SEND.IO\lathe_mode_reminder.json. Delete
     that too if you like.

(You can also stop it without uninstalling: in Fusion, UTILITIES >
ADD-INS > Scripts and Add-Ins > GSendLatheMode > Stop, and untick
"Run on Startup".)


MORE
----

The full G-SEND.IO app adds the G-code editor, lathe and mill
simulators, Send/Receive (DNC) and more - see G-SEND.IO, or use the
Upgrade button in the add-in.
