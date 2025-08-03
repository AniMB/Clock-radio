# Smart Clock‑Radio

Smart Clock‑Radio marries a classic FM tuner with modern IoT convenience. Powered by a Raspberry Pi Pico W and written entirely in MicroPython, it pairs a precision RTC, vibrant OLED, and tactile hardware controls with a Flask web dashboard accessible from any browser. Tune stations, set alarms, pull network time, and manage volume or favourites from your phone or laptop while real‑time updates appear instantly on the display.

![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi%20Pico%20W-brightgreen) ![License](https://img.shields.io/badge/License-MIT-blue)

---

## ✨ Key Features

* **OLED display** shows current time (12 h/24 h), tuned frequency, and volume bar.
* **Single push‑button** toggles radio on/off for quick control.
* **Headphone jack** for private listening, backed by a PAM8302 amplifier.
* **Web dashboard** (Flask) lets you

  * Set the clock or pull network time from anywhere in the world.
  * Toggle 12 h ↔ 24 h format.
  * Adjust volume or mute.
  * Configure alarms with a custom snooze interval.
  * Manage favourite station presets.
* **JSON configuration** (`database/web_data.json`) stores persistent settings thread‑safely.
* **Comprehensive tests & demo videos** live in the repo for reproducibility.

---

## 🛠️ Hardware Bill of Materials

| Qty | Part                                | Notes                   |
| --- | ----------------------------------- | ----------------------- |
| 1   | Raspberry Pi Pico W                 | Microcontroller & Wi‑Fi |
| 1   | 1.3" OLED (SPI)                     | 128×64 pixels           |
| 1   | RDA5807M FM tuner module            | I²C interface           |
| 1   | Momentary push‑button               | Radio power and snooze  |
| 1   | 3.5 mm headphone jack + LM386 amp   | Stereo speaker out      |
| —   | Misc. resistors, caps, wire         |                         |

---

## 📂 Repository Structure

```
├── firmware/                 # MicroPython source code
│   ├── mi69.py               # Hardware control firmware (also reproduced here)
│   ├── json_handler.py       # Thread‑safe JSON read/write
│   ├── drivers/              # OLED, rotary encoder modules
│   └── …
├── web/                      # Flask dashboard
│   ├── app.py
│   ├── templates/
│   └── static/
├── database/
│   └── web_data.json         # Runtime configuration & state
├── docs/
│   ├── test‑plan.md
│   └── code‑of‑ethics.md
├── media/                    # Demo videos & screenshots
├── LICENSE
└── README.md                 # You’re here 📖
```

---

## 🚀 Getting Started

1. **Clone** the repository:

   ```bash
   git clone https://github.com/<your‑username>/smart‑clock‑radio.git
   cd smart‑clock‑radio
   ```
2. **Flash MicroPython** to your Pico W (see [official guide](https://micropython.org/download/rp2-pico-w/)).
3. **Install Python deps** for the web dashboard:

   ```bash
   pip install -r web/requirements.txt
   ```
4. **Deploy firmware**:

   * Copy the contents of `firmware/` to the Pico using Thonny, rshell, or ampy.
5. **Run dashboard locally** (optional):

   ```bash
   cd web
   python app.py
   ```

   Visit `http://<pico‑ip>:5000` from any device on the same network.

---

## ⚙️ Configuration File (`web_data.json`)

The Pico reads/writes all runtime settings from `database/web_data.json`.

* `alarm_hour`, `alarm_minute`, `alarm_ampm` – next alarm time
* `freq1`‑`freq3` – favourite FM presets
* `volume` (0‑100) – master volume
* `use24Hour` (0/1) – time format
* `mute` (0/1) – audio mute status
* `snooze` – snooze duration in minutes

Changes made through the web UI or hardware controls are persisted automatically.

---

## 🧪 Testing & Demonstration

All source code, test scripts, and demonstration videos are housed in this repository. The main firmware (`firmware/main.py`) is reproduced in the report, while verification assets and video walkthroughs live under `docs/` and `media/`. Each file contains header comments with purpose, author, and revision date for full traceability.

---

## 🤝 Contributing

Pull requests are welcome! Please open an issue first to discuss major changes.

1. Fork the project.
2. Create your feature branch (`git checkout -b feature/AmazingFeature`).
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the branch (`git push origin feature/AmazingFeature`).
5. Open a pull request.

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.

---

## 💬 Acknowledgements

This project was developed as part of the **Clock‑Radio** course project at the University of Victoria. Special thanks to teammates and instructors for guidance and support.
