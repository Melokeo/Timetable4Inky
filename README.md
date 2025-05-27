# Timetable4Inky
Source code for drawing daily schedules on a Pimoroni Inky Impression screen
- `routines.py` is where the user defines what to display
- `taskTemplates.py` defines task presets; each valid task should have an entry here then can be referenced in `routines.py`
- `draw.py` contains Renderer classes that draws image output
- `scheduler.py` calls Renderers to update display on certain timepoints
- `display.py` is for connecting with the Inky Impression e-ink screen
- `uploader.py` auto uploads drawn image to a server defined in `cfg/upload_config.json`
- `coords.py` are tedious layout coords
- `style.py` contains text styles used in drawing; needs clean-up
- `resources/` include background image, logos, etc.

A running example can be watched at https://melokeo.icu/timetable
