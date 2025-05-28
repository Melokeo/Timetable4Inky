# Timetable4Inky

Source code for drawing daily schedules on an e-ink screen.

Running example on [M.ICU](https://melokeo.icu/timetable)

**Development environment**

- Raspberry Pi zero 2w (Raspberry Pi OS 32-bit (Bookworm))
- Pimoroni Inky Impression 7.3" (2025) \[e-ink\]
- Python 3.12
- Written on Win11

**Scripts**

- `routines.py` is where the user defines what to display
- `taskTemplates.py` defines task presets; each valid task should have an entry here then can be referenced in `routines.py`
- `draw.py` contains Renderer classes that draws image output
- `scheduler.py` calls Renderers to update display on certain timepoints
- `display.py` is for connecting with the Inky Impression e-ink screen
- `uploader.py` auto uploads drawn image to a server defined in `cfg/upload_config.json`
- `coords.py` are tedious layout coords
- `style.py` contains text styles used in drawing; needs clean-up
- `resources/` include background image, logos, etc.

**Dependencies**

```bash
python3.12 -m pip install numpy pillow requests lunar_python inky
python3.12 -m pip install openai icalendar
```

p.s. numpy builds super slowly.

For full support of Pillow: 

```bash
sudo apt install libjpeg-dev zlib1g-dev libpng-dev libfreetype6-dev liblcms2-dev \
libopenjp2-7-dev libtiff-dev libwebp-dev tcl-dev tk-dev
```

---

**Running as service**

Assume the project is dropped at `/home/pi/Timetable4Inky`

```bash
sudo nano /etc/systemd/system/inky.service
```

```ini
[Unit]
Description=My Python Scheduler
After=network.target

[Service]
ExecStart=/usr/local/bin/python3.12 /home/pi/Timetable4Inky/scheduler.py
WorkingDirectory=/home/pi/Timetable4Inky
Restart=always
User=pi
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1  ; ensures log output

[Install]
WantedBy=multi-user.target
```

if using venv, replace execstart with:

```ini
ExecStart=/home/pi/Timetable4Inky/venv/bin/python /home/pi/Timetable4Inky/scheduler.py
```

Run service:

```bash
sudo systemctl daemon-reexec & sudo systemctl daemon-reload
sudo systemctl enable myscheduler & sudo systemctl start myscheduler
```

Check stat & log:

```bash
sudo systemctl status inky
journalctl -u inky -f
```
