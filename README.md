# ⏰ Clock Radio – MicroPython Smart Clock System

**`mi69.py`** is the main script of an embedded, Wi-Fi-enabled FM radio and smart clock interface built on **MicroPython**. It combines a **real-time clock**, **OLED UI**, **FM tuner**, and **web connectivity** into a single-threaded yet responsive application, suitable for microcontrollers like the Raspberry Pi Pico W.

---

## 🚦 Architecture Overview

```
             ┌────────────┐
             │   Button   │◄────────────┐
             └────┬───────┘             │
                  ▼                     │
             ┌─────────────┐     Debounce, Hold Detection
             │    Main     │─────────────┘
             │   (mi69.py) │
             └────┬────────┘
        ┌─────────┴─────────┐
        ▼                   ▼
┌────────────┐       ┌────────────┐
│  Display   │       │   Radio    │
│ (OLED + UI)│       │  (FM chip) │
└────┬───────┘       └────┬───────┘
     ▼                    ▼
 ┌──────────┐      ┌────────────┐
 │ Web Time │      │ Web Server │◄──── Access via browser
 └──────────┘      └────────────┘
```

---

## 🧠 Code Modules

### `mi69.py` – Main Control Loop

- Initializes components (RTC, FM radio, OLED, Button, Web).
- Sets up **interrupt-safe button handling** (short vs. long press).
- Periodically updates:
  - Display (clock, station, volume)
  - State file (`web_data.json`)
- Starts the **HTTP server in a separate thread**.

#### Core Mechanics

- `oled_dirty`, `json_dirty` flags minimize redundant writes
- `utime.ticks_ms()` is used to throttle updates
- JSON I/O and OLED are **locked via a thread-safe `_lock`**
- Long press (>3 sec) and debounce logic built-in

---

### `libraries/display.py` – OLED Drawing

Encapsulates all drawing on the OLED display using `framebuf`:

- `display_clock_time(rtc.datetime())`
- `display_radio_freq(101.9)`
- `display_volume(5)`

Also handles font scaling, screen clearing, and line placement.

---

### `libraries/radio.py` – FM Radio Control

Controls an FM tuner (likely via I2C/SPI). Key methods:

- `set_freq(freq)`: set frequency (MHz)
- `seek_up() / seek_down()`: scan for stations
- `set_volume(level)`: 0–15 volume levels

Keeps state internally for restoring or syncing with UI/web.

---

### `config/resources.py` – Global Shared State

Contains:

- Button pin definitions
- Flags: `oled_dirty`, `json_dirty`, `btn_short_req`, etc.
- Constants: debounce delay, hold time threshold
- A global `_lock` used by both threads

This is the “RAM” for the system shared across all modules.

---

### `web_connectivity/web.py` – HTTP Server

A simple HTTP server that runs on a new thread:

- Serves a web interface (to be extended)
- API routes:
  - `GET /status`: Return JSON state
  - `POST /set_time`, `POST /set_volume`, etc.
- Reads/writes `web_data.json` using the shared `_lock`

This lets users control and monitor the device remotely.

---

### `web_data.json` – State File

JSON-encoded structure for UI and web server to share state.

```json
{
  "volume": 5,
  "frequency": 101.9,
  "time": "12:34:56",
  "alarm_enabled": false
}
```

Used for persistence and as a synchronization bridge.

---

## 🧵 Concurrency & Thread Safety

- Uses MicroPython’s `_thread` module for background web server
- Ensures safety via `_lock` for:
  - JSON file access
  - OLED updates

```python
from _thread import start_new_thread
start_new_thread(WebServer().start, ())
```

---

## 🔋 Efficiency Considerations

- OLED and JSON updates are **rate-limited** using `ticks_ms()`
- Button reads are **debounced**
- Threads are **lightweight**, preventing blocking I/O
- Display refreshes only on changes

---

## 🚀 Future Extensions

- 📆 Alarm scheduling + snooze logic
- 🌐 NTP time sync
- 📱 Better web UI with sliders & buttons
- 📻 Station presets & memory
- 🔌 BLE or MQTT integration

---

## 📎 Developer Notes

- Clear modularity: `main`, `display`, `radio`, `web`, `resources`
- Code follows **embedded-safe design** (no dynamic memory abuse)
- Minimal, fast and effective for real-time low-power devices

---

## 🧠 Summary

This project is a highly educational template for combining hardware control, UI, web connectivity, and concurrency in **MicroPython**. It’s a complete working system for embedded devices with many real-world use cases.

---

