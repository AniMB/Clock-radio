import json
import os
import sys
import framebuf
import time

from machine import *
from utime import *
from _thread import *
from config.resources import *
from web_connectivity.web import WebServer
from config.resources import _lock
from network import WLAN, AP_IF
from libraries.display import *   # expects: oled, SCREEN_WIDTH, SCREEN_HEIGHT
from libraries.radio import Radio




import micropython
micropython.alloc_emergency_exception_buf(256)

# -------------------- RTC --------------------
rtc = RTC()

# -------------------- Button press policy --------------------
BUTTON_HOLD_MS = 3000  # long press threshold
_DEBOUNCE_MS   = 60

_btn_down_ms   = None
_btn_short_req = False
_btn_long_req  = False

# -------------------- Draw and JSON throttles --------------------
JSON_READ_PERIOD_MS  = 100
JSON_WRITE_PERIOD_MS = 250

_last_json_read_ms   = 0
_last_json_write_ms  = 0
_json_dirty          = False

_update_tick_due     = False
_last_drawn          = None
_oled_dirty          = False

# Yield policy to keep web thread responsive
_yield_count         = 0

# -------------------- Flags for modes --------------------
_snoozeflag = False
_alarmflag  = False
_Radioflag  = False

# =========================================================
#                        JSON
# =========================================================
class JsonHandler:
    def __init__(self):
        self.__filename = "web_data.json"
        self.json_object = {
            "alarm_hour": 0,
            "alarm_minute": 0,
            "alarm_ampm": 0,     # 0/1 or "AM"/"PM"
            "freq1": 101.9,
            "freq2": 101.9,
            "freq3": 101.9,
            "volume": 50,
            "nowplaying": 1,
            "use24Hour": 1,
            "mute": 0,
            "Time": "12:00:00",
            "time_ampm": 0,
            "snooze": 5,
            "cancelAlarm": 0
        }

    def read_json(self) -> bool:
        if _lock.acquire():
            try:
                with open(self.__filename, "r") as file:
                    data = json.load(file)
                self.json_object.clear()
                self.json_object.update(data)
                return True
            except Exception as e:
                # Keep it quiet in hot path
                # print(f"Error reading from {self.__filename}: {e}")
                return False
            finally:
                _lock.release()
        else:
            # print("Lock busy on read")
            return False

    def write_json(self) -> bool:
        if _lock.acquire():
            try:
                with open(self.__filename, "w") as file:
                    json.dump(self.json_object, file)
                return True
            except Exception as e:
                # print(f"Error writing to {self.__filename}: {e}")
                return False
            finally:
                _lock.release()
        else:
            # print("Lock busy on write")
            return False

# =========================================================
#                        Time
# =========================================================
def increment_and_update_time(value_dict):
    try:
        timestr = value_dict.get("Time", "00:00:00").strip()
        h, m, s = map(int, timestr.split(":"))
        s += 1
        if s >= 60:
            s = 0
            m += 1
            if m >= 60:
                m = 0
                h += 1
                if h >= 24:
                    h = 0
        value_dict["Time"] = f"{h:02}:{m:02}:{s:02}"
        if value_dict.get("use24Hour", 1) == 0:
            ampm = "AM" if h < 12 else "PM"
            hh = h % 12 or 12
            time_str = f"{hh:02}:{m:02}:{s:02}"
        else:
            ampm = ""
            time_str = f"{h:02}:{m:02}:{s:02}"
        return time_str, ampm
    except Exception as e:
        # print(f"Error incrementing time: {e}")
        return value_dict.get("Time", "00:00:00"), ""

# =========================================================
#                        Hardware
# =========================================================
button = Pin(0, Pin.IN, Pin.PULL_UP)

handle_json = JsonHandler()
if not handle_json.read_json():
    handle_json.write_json()
value_dict = handle_json.json_object

_, _, _, _, h, m, s, _ = rtc.datetime()
value_dict["Time"]=f"{h:02}:{m:02}:{s:02}"

handle_json.write_json()

# clamp nowplaying to 1..3
_idx = int(value_dict.get("nowplaying", 1))
if _idx < 1 or _idx > 3:
    _idx = 1

fm_radio = Radio(
    float(value_dict.get(f"freq{_idx}", 100.0)),
    int(value_dict.get("volume", 50)),
    int(value_dict.get("mute", 0))
)

# =========================================================
#                        Drawing
# =========================================================
def draw_clock(time_str, ampm):
    global _last_drawn, _update_tick_due, _oled_dirty
    stamp = (time_str, ampm)
    if stamp == _last_drawn:
        return
    _last_drawn = stamp
    _update_tick_due = False

    oled.fill(0)
    oled.text(time_str, 0, 0)
    if ampm:
        oled.text(ampm, 80, 0)
    _oled_dirty = True

def _show_volume(vol, mute):
    global _oled_dirty
    bar_h = 5
    y0 = SCREEN_HEIGHT - bar_h
    oled.fill_rect(0, y0, SCREEN_WIDTH, bar_h, 0)
    try:
        vol = int(vol)
    except Exception:
        vol = 0
    if vol < 0:
        vol = 0
    if vol > 100:
        vol = 100
    fill_w = 0 if int(mute) else int((vol / 100.0) * SCREEN_WIDTH)
    oled.fill_rect(0, y0, fill_w, bar_h, 1)
    oled.rect(0, y0, SCREEN_WIDTH, bar_h, 1)
    _oled_dirty = True

# =========================================================
#                        Timer and Button IRQ
# =========================================================
def on_timeout(t):
    # IRQ safe
    global _update_tick_due
    _update_tick_due = True

timer = Timer(-1)
timer.init(period=1000, mode=Timer.PERIODIC, callback=on_timeout)

def _button_irq(pin):
    global _btn_down_ms, _btn_short_req, _btn_long_req
    now = ticks_ms()
    if pin.value() == 0:  # pressed
        if _btn_down_ms is None:
            _btn_down_ms = now
    else:  # released
        if _btn_down_ms is not None:
            dur = ticks_diff(now, _btn_down_ms)
            _btn_down_ms = None
            if dur >= BUTTON_HOLD_MS:
                _btn_long_req = True
            elif dur >= _DEBOUNCE_MS:
                _btn_short_req = True

button.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=_button_irq, hard=True)

# =========================================================
#                        Alarm
# =========================================================
class Alarm:
    alarm_h = 0
    alarm_m = 0

    def __init__(self):
        # remember the last (hour, minute) we triggered in to avoid retrigger spam
        self._last_triggered_min = None

    @staticmethod
    def to_24h(hour: int, minute: int, am_pm: str) -> tuple:
        hour = int(hour); minute = int(minute)
        tag = str(am_pm).strip().upper()
        if tag not in ("AM", "PM"):
            raise ValueError("am_pm must be 'AM' or 'PM'")
        if not (1 <= hour <= 12):
            raise ValueError("hour 1..12")
        if not (0 <= minute <= 59):
            raise ValueError("minute 0..59")
        if tag == "AM":
            h24 = 0 if hour == 12 else hour
        else:
            h24 = 12 if hour == 12 else hour + 12
        return h24, minute

    def _normalize_alarm_from_dict(self, value_dict):
        """
        Normalize alarm fields to 24h regardless of display mode.
        If we have AM/PM and hour looks 12h (1..12), convert.
        Otherwise assume it's already 24h.
        """
        h = int(value_dict.get("alarm_hour", 0))
        m = int(value_dict.get("alarm_minute", 0))
        ampm = value_dict.get("alarm_ampm", None)

        # Accept int 0/1 or string AM/PM
        if isinstance(ampm, int):
            ampm = "PM" if ampm else "AM"

        if 1 <= h <= 12 and ampm in ("AM", "PM"):
            try:
                h, m = self.to_24h(h, m, ampm)
            except Exception:
                pass  # fall back to given values on error

        return h, m

    def sync_from_dict(self, value_dict):
        self.snooze_minutes = int(value_dict.get("snooze", 5))
        self.alarm_enabled  = not bool(int(value_dict.get("cancelAlarm", 0)))

        # Normalize alarm to 24h unconditionally when we can infer AM/PM
        self.alarm_hour, self.alarm_minute = self._normalize_alarm_from_dict(value_dict)

        Alarm.alarm_h = self.alarm_hour
        Alarm.alarm_m = self.alarm_minute
        # do not reset self._last_triggered_min here; it is a per-minute guard

    def is_alarm(self, value_dict) -> bool:
        """
        Returns True exactly once when current (h,m) equals the scheduled alarm time.
        If we were snoozing, clear the snooze flag at the moment we reach the time.
        """
        if not self.alarm_enabled:
            return False

        h, m, _ =  value_dict["Time"].strip().split(":")

        h,m=int(h),int(m)
        now_min = (int(h),int( m))

        if (self.alarm_hour == h) and (self.alarm_minute == m):
            # if we were snoozing, it's time to wake up again
            global _snoozeflag
            if _snoozeflag:
                _snoozeflag = False

            # trigger only once per minute
            if self._last_triggered_min != now_min:
                self._last_triggered_min = now_min
                return True
            else:
                return False
        else:
            # reset guard when minute moves away from the alarm time
            if self._last_triggered_min == now_min:
                # still in same minute but not the alarm minute; keep guard
                pass
            return False

    def on_snooze(self):
        """
        Short press: stop ringing and schedule next ring after snooze_minutes.
        """
        global _snoozeflag, _alarmflag
        if not _alarmflag:
            return
        _snoozeflag = True
        _alarmflag  = False
        try:
            fm_radio.SetMute(True)
            fm_radio.ProgramRadio()
        except Exception:
            pass

      

        h,m=self.alarm_hour, self.alarm_minute
        total = h * 60 + m + int(self.snooze_minutes)
        self.alarm_hour   = (total // 60) % 24
        self.alarm_minute = total % 60

        # allow a new trigger when snooze time arrives
        self._last_triggered_min = None

    def stop_alarm(self):
        """
        Long press: fully stop, disarm, and allow future arming.
        """
        global _snoozeflag, _alarmflag
        _snoozeflag = False
        _alarmflag  = False
        self.alarm_enabled = False
        self._last_triggered_min = None
        try:
            fm_radio.SetMute(True)
            fm_radio.ProgramRadio()
        except Exception:
            pass

alarm = Alarm()

def on_stop(value_dict):
    global alarm, _json_dirty
    alarm.stop_alarm()
    value_dict["cancelAlarm"] = 1  # persist disarm
    _json_dirty = True
    alarm = Alarm()

# =========================================================
#                        Main loop
# =========================================================
def pico_runner():
    global _snoozeflag, _Radioflag, _alarmflag
    global _last_json_read_ms, _last_json_write_ms, _json_dirty
    global _update_tick_due, _oled_dirty, _yield_count

    # Ensure JSON exists
    if not handle_json.read_json():
        handle_json.write_json()
    value_dict = handle_json.json_object

    while True:
        now = ticks_ms()

        # Throttled JSON read
        if ticks_diff(now, _last_json_read_ms) >= JSON_READ_PERIOD_MS:
            handle_json.read_json()
            value_dict = handle_json.json_object
            _last_json_read_ms = now

        # Consume button requests
        global _btn_short_req, _btn_long_req
        if _btn_long_req and _alarmflag:
            _btn_long_req = False
            on_stop(value_dict)
        elif _btn_short_req and _alarmflag:
            _btn_short_req = False
            alarm.on_snooze()
        elif _btn_short_req and _Radioflag:
            _btn_short_req = False
            _Radioflag = False
            # turn radio OFF (mute)
            fm_radio.SetMute(1)
            fm_radio.ProgramRadio()

        elif _btn_short_req and not _Radioflag:
            _btn_short_req = False
            _Radioflag = True
            # turn radio ON: tune and unmute immediately
            idx  = max(1, min(3, int(value_dict.get("nowplaying", 1))))
            freq = float(value_dict.get(f"freq{idx}", 100.0))
            fm_radio.SetFrequency(freq)
            fm_radio.SetVolume(value_dict.get("volume", 50))
            fm_radio.SetMute(0)
            fm_radio.ProgramRadio()



        # Sync alarm when not snoozing
        if not _snoozeflag:
            alarm.sync_from_dict(value_dict)

        # 1 Hz clock tick
        if _update_tick_due:
            _update_tick_due = False
            time_str, ampm = increment_and_update_time(value_dict)
            draw_clock(time_str, ampm)
            _json_dirty = True

        # Trigger alarm (after the latest tick)
        if alarm.is_alarm(value_dict):
            _alarmflag = True
            _Radioflag = False
            print("alarm triggered")
            fm_radio.SetFrequency(100.1)
            fm_radio.SetVolume(100)
            fm_radio.SetMute(0)
            fm_radio.ProgramRadio()


        # Radio UI and tuning only when showing radio and not ringing
        if _Radioflag and not _alarmflag:
            idx  = max(1, min(3, int(value_dict.get("nowplaying", 1))))
            freq = float(value_dict.get(f"freq{idx}", 100.0))

            # Only reprogram radio when something actually changed
            need = False
            if int(value_dict.get("mute", 0))   != int(fm_radio.Mute):   need = True
      
            desired_hw = (int(value_dict.get("volume", 50)) * 15 + 50) // 100  # rounded
            if desired_hw != int(fm_radio.Volume):
                need = True
            if abs(freq - float(fm_radio.Frequency)) > 1e-3:             need = True

            if need:
                fm_radio.SetMute(value_dict.get("mute", 0))
                fm_radio.SetVolume(value_dict.get("volume", 50))
                fm_radio.SetFrequency(freq)
                fm_radio.ProgramRadio()

            oled.fill_rect(0, 10, SCREEN_WIDTH, 10, 0)
            oled.text("Now:", 0, 10)
            oled.text("{:.1f}MHz".format(freq), 40, 10)
            _oled_dirty = True
        else:
            if _Radioflag:   # cleared this cycle
                _Radioflag = False
                oled.fill_rect(0, 10, SCREEN_WIDTH, 10, 0)
                _oled_dirty = True

        # Volume bar
        _show_volume(value_dict["volume"], value_dict["mute"])

        # Flush OLED only if it changed
        if _oled_dirty:
            _oled_dirty = False
            oled.show()

        # Throttled JSON write
        if _json_dirty and ticks_diff(now, _last_json_write_ms) >= JSON_WRITE_PERIOD_MS:
            if handle_json.write_json():
                _json_dirty = False
                _last_json_write_ms = now

        # Cooperative yield so web thread runs
        if _alarmflag or _Radioflag:
            sleep_ms(0)
        else:
            _yield_count = (_yield_count + 1) & 31
            if _yield_count == 0:
                sleep_ms(1)
            else:
                sleep_ms(0)

def main():
    ssid = '007'
    password = '212173314'
    ap = WLAN(AP_IF)
    ap.config(essid=ssid, password=password)
    ap.active(True)
    while ap.active() == False:
        pass
    print('Connection is successful')
    print(ap.ifconfig())

    Worker = WebServer()
    start_new_thread(Worker.runner, ())
    pico_runner()

if __name__ == "__main__":
    main()
